"""Export terminated S02 aggregate evidence; never run models or read source data."""
from __future__ import annotations
import argparse
import csv
import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics
import types

SEEDS = (17, 29, 43)
RECIPES = ("M1", "M2", "M3", "M4")
POST = {v + "-bN-" + tag: dict(id=v + "-bN-" + tag, variant=v, beta=b)
        for v in ("W0", "W1", "W2") for b, tag in zip((-.4, -.2, 0., .2, .4), ("m04", "m02", "zero", "p02", "p04"))}
FIT_IDS = {f"{r}-s{s}": (r, s) for r in RECIPES for s in SEEDS}
BASE = "S01-B-CAT-zscore"
SOURCE = "66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd"
REFERENCE = "1cd4b73bb748284b4941625d92be89522771eff8a11e4044547e5f513ea62495"
SELECTION = "e799e1563e1763300648364b25b66743d63c757f0ed618173e158938ebd34db4"
TERMINAL = ("COMPLETED", "BLOCKED", "PARTIAL_RESOURCE_STOP")
PHASES = ("SOURCE", "RESOURCE_PREFLIGHT", "POSTPROCESS", "TRAIN", "FIT_PREFLIGHT", "FIT", "SELECTION", "WINNER_RESTORE")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())


def path_guard(path):
    for p in (path, *path.parents):
        if p.exists():
            require(not p.is_symlink() and not getattr(p.lstat(), "st_file_attributes", 0) & 0x400,
                    "Redirected path rejected")


def fingerprint(path, limit=None):
    path_guard(path)
    require(path.is_file() and (limit is None or path.stat().st_size <= limit), "Missing or oversized evidence")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    return dict(sha256=h.hexdigest(), size=path.stat().st_size)


def load(path):
    stamp = fingerprint(path, 32 * 2**20)
    raw = path.read_bytes()
    require(sha(raw) == stamp["sha256"], "Evidence changed during read")
    return json.loads(raw.decode("utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON"))), stamp


def number(value, lo=0., hi=None):
    require(type(value) in (int, float) and math.isfinite(value) and value >= lo and
            (hi is None or value <= hi), "Invalid finite aggregate number")
    return value


def integer(value, lo=0):
    require(type(value) is int and value >= lo, "Invalid count")
    return value


def digest(value, length=64):
    require(isinstance(value, str) and re.fullmatch("[a-f0-9]{" + str(length) + "}", value), "Invalid digest")
    return value


def timestamp(value):
    require(isinstance(value, str) and datetime.datetime.fromisoformat(value).tzinfo is not None, "Timestamp requires timezone")
    return value


def score(value):
    return dict(macro_F1=number(value["macro_F1"], 0, 1), MAE=number(value["MAE"], 0, 6))


def clean_score(value, population=None):
    result = dict(Accuracy=number(value["Accuracy"], 0, 1), **score(value))
    result["Pearson"] = value["Pearson"]
    result["Pearson_reason"] = value.get("Pearson_reason")
    if result["Pearson"] is None:
        require(result["Pearson_reason"] in ("insufficient_n", "zero_target_variance", "zero_prediction_variance"), "Null Pearson reason required")
    else:
        number(result["Pearson"], -1 - 1e-12, 1 + 1e-12)
        require(result["Pearson_reason"] is None, "Finite Pearson reason must be null")
    if population is not None:
        require(integer(value["n"], 1) == population, "Clean population mismatch")
        result["n"] = population
    return result


def module_at(path, expected):
    raw = path.read_bytes()
    path_guard(path)
    require(sha(raw) == expected, "Public reference implementation changed")
    mod = types.ModuleType("s02_export_" + path.stem)
    exec(compile(raw, str(path), "exec"), mod.__dict__)
    return mod


def exception_category(error):
    if error is None:
        return None
    require(isinstance(error, str), "Invalid error record")
    category = error.split(":", 1)[0]
    return category if re.fullmatch("[A-Za-z][A-Za-z0-9_]{0,70}", category) else "UNCLASSIFIED_ERROR"


def close(actual, expected, label):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), label + " keys mismatch")
        for key, value in expected.items():
            close(actual[key], value, label)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + " list mismatch")
        for a, b in zip(actual, expected):
            close(a, b, label)
    elif type(expected) is float:
        require(type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), label + " numeric mismatch")
    else:
        require(actual == expected and (expected is not None or actual is None), label + " mismatch")


def public_summary(value, selection):
    require(value["id"] in set(POST) | set(RECIPES) | {BASE}, "Unknown comparison candidate")
    rows = {int(seed): dict(status="COMPLETED", clean=clean_score(row["clean"]), attempted96=score(row["attempted96"]))
            for seed, row in value["per_seed"].items()}
    require(all(str(s) == str(seed) for seed, s in zip(value["per_seed"], rows)), "Noncanonical seed key")
    expected = selection.summarize_candidate(value["id"], rows, parameters=value["parameters"], inference_cost=value["inference_cost"])
    normalized = {**value, "per_seed": {int(s): r for s, r in value["per_seed"].items()}}
    close(normalized, expected, "Stored comparison")
    return expected


def seed_stats(rows, complete):
    if not complete:
        return None
    return {k: dict(mean=math.fsum(rows[s][k] for s in SEEDS) / 3,
                    seed_sd_ddof1=statistics.stdev(rows[s][k] for s in SEEDS)) for k in ("macro_F1", "MAE")}


def export(campaign, output, project):
    campaign, output, project = map(lambda p: Path(p).absolute(), (campaign, output, project))
    for p in (campaign, output, project):
        path_guard(p)
    campaign, output, project = campaign.resolve(), output.resolve(), project.resolve()
    require(not output.exists() and not output.is_relative_to(campaign) and not output.is_relative_to(project)
            and not campaign.is_relative_to(output), "New external export directory required")
    ref = module_at(project / "research/r01/reference.py", REFERENCE)
    selector = module_at(project / "src/mosei/s02/selection.py", SELECTION)
    evidence = []

    def read(relative, kind, identity=None):
        value, stamp = load(campaign / relative)
        evidence.append(dict(kind=kind, **({"id": identity} if identity else {}), **stamp))
        return value

    run = read("campaign.json", "CAMPAIGN")
    terminal = read("campaign_status.json", "TERMINAL_CAMPAIGN_STATUS")
    binding, config = run["binding"], run["config"]
    cid = binding["campaign_id"]
    require(isinstance(cid, str) and re.fullmatch("S02-[A-Za-z0-9-]{1,95}", cid), "Unsafe campaign identifier")
    require(config["campaign_id"] == cid and binding["config_hash"] == canonical(config) and terminal["binding"] == binding, "Campaign binding mismatch")
    commit, manifest = digest(binding["commit"], 40), digest(binding["manifest_sha256"])
    require(config["execution_fit_budget"] == terminal["fit_budget"] == 12 and config["postprocess_budget"] == terminal["postprocess_budget"] == 15,
            "Fixed campaign budgets changed")
    require(config["model_seeds"] == list(SEEDS) and config["recipes"] == list(RECIPES) and
            config["variants"] == ["W0", "W1", "W2"] and config["betas"] == [-.4, -.2, 0., .2, .4], "Fixed campaign grid changed")
    require(config["source_sha256"] == SOURCE and config["test_authorized"] is False and config["attachment3_4_authorized"] is False,
            "Source/split authorization mismatch")
    require(terminal["status"] in TERMINAL and terminal["authorization_status"] == "CONSUMED" and terminal["retry_budget"] == 0,
            "Terminated consumed zero-retry campaign required")
    require(terminal["phase"] in PHASES and (terminal["current"] is None or terminal["current"] in set(FIT_IDS) | set(POST)), "Unknown stop identity/phase")
    started, finished = timestamp(run["started"]), timestamp(terminal["finished"])
    require(datetime.datetime.fromisoformat(finished) >= datetime.datetime.fromisoformat(started), "Negative campaign time")
    require(type(terminal["promoted"]) is bool and terminal["current_champion"] in set(POST) | set(RECIPES) | {BASE}, "Invalid current champion")
    source = None
    if (campaign / "source_verification.json").exists():
        s = read("source_verification.json", "SOURCE_VERIFICATION")
        require(s["source_sha256"] == SOURCE and s["splits_used"] == ["train", "valid"] and s["test_used"] is False and
                s["special_sets_opened"] is False and s["test_fields_accessed"] is False, "Source verification scope mismatch")
        source = dict(source_sha256=SOURCE, train_count=integer(s["train_count"], 1), valid_count=integer(s["valid_count"], 1),
                      splits_used=["train", "valid"], test_used=False, special_sets_opened=False,
                      monolithic_pickle_deserialized=s["monolithic_pickle_deserialized"], test_fields_accessed=False)
        require(type(source["monolithic_pickle_deserialized"]) is bool, "Invalid source deserialization flag")
    states = {k: "NOT_RUN" for k in (*FIT_IDS, *POST)}
    end_events, public_events = {}, []
    events_path = campaign / "events.jsonl"
    if events_path.exists():
        stamp = fingerprint(events_path, 2**20);raw = events_path.read_bytes()
        require(sha(raw) == stamp["sha256"], "Events changed during read")
        evidence.append(dict(kind="DURABLE_EVENTS", **stamp))
        for line in raw.decode("utf-8").splitlines():
            event = json.loads(line);kind = event["kind"]
            require(kind in ("FIT", "POSTPROCESS", "CAMPAIGN_FAILURE"), "Unknown event kind")
            tid, status = event["id"], event["status"]
            if kind == "CAMPAIGN_FAILURE":
                require(status == terminal["status"] and event["phase"] == terminal["phase"] and tid == terminal["current"], "Failure termination mismatch")
                public_events.append(dict(kind=kind, id=tid, status=status, phase=event["phase"], exception_category=exception_category(event.get("error"))))
                continue
            require(tid in (FIT_IDS if kind == "FIT" else POST), "Unknown event trial")
            require((states[tid] == "NOT_RUN" and status == "RUNNING") or
                    (states[tid] == "RUNNING" and status in ("COMPLETED", "FAILED", "RESOURCE_CAP_STOP")), "Invalid event transition or retry")
            states[tid] = status
            public_events.append(dict(kind=kind, id=tid, status=status, exception_category=exception_category(event.get("error"))))
            if status == "COMPLETED":
                end_events[tid] = event
    require(sum(states[k] == "COMPLETED" for k in FIT_IDS) == terminal["fit_completed"] and
            sum(states[k] == "COMPLETED" for k in POST) == terminal["postprocess_completed"], "Terminal completed counts mismatch")
    if terminal["status"] == "COMPLETED":
        require(all(s == "COMPLETED" for s in states.values()), "Completed campaign has uncompleted candidates")
    for tid, status in list(states.items()):
        if status == "RUNNING":
            require(terminal["status"] != "COMPLETED" and terminal["current"] == tid, "Unexplained running trial at exit")
            states[tid] = "RESOURCE_CAP_STOP" if terminal["status"] == "PARTIAL_RESOURCE_STOP" else "FAILED"
    reports, rows, pairing, fits, posts = {}, {}, {}, [], []
    epoch_files, epoch_csv = {}, []

    def evaluation(value, identity, seed):
        require(source is not None and value["status"] == "COMPLETED", "Only source-verified completed evaluation accepted")
        population = source["valid_count"]
        result = dict(status="COMPLETED", seed=seed, clean=clean_score(value["clean"], population), attempted96=score(value["attempted96"]))
        checked = ref.aggregate({seed: value["condition_reports"]}, expected_seeds=(seed,))
        close(result["attempted96"], checked["per_seed"][seed], "Attempted96")
        for condition, views in value["condition_reports"].items():
            for rep, view in enumerate(views):
                require(integer(view["total_count"], 1) == population, "Condition/source population mismatch")
                eligible = integer(view["eligible_count"])
                require(eligible <= population and math.isclose(number(view["coverage"], 0, 1), eligible / population, abs_tol=1e-12), "Invalid coverage")
                score(view["attempted"])
                private = view["pairing"]
                stamp = (private["population"], private["eligibility"], private["view"], eligible, population)
                key = (condition, rep)
                require(key not in pairing or pairing[key] == stamp, "Cross-configuration mask/population pairing mismatch")
                pairing[key] = stamp
        sign = value["sign_disagreement_clean"]
        n, count = integer(sign["total_count"], 1), integer(sign["disagreement_count"])
        require(n == population and count <= n and math.isclose(number(sign["fraction"], 0, 1), count / n, abs_tol=1e-12), "Sign inconsistency aggregate mismatch")
        result["sign_disagreement_clean"] = dict(disagreement_count=count, total_count=n, fraction=count / n)
        result["sign_disagreement_attempted96"] = number(value["sign_disagreement_attempted96"], 0, 1)
        reports.setdefault(identity, {})[seed] = value["condition_reports"]
        rows.setdefault(identity, {})[seed] = result
        return result

    for tid, (recipe, seed) in FIT_IDS.items():
        row = dict(id=tid, recipe=recipe, seed=seed, status=states[tid], metrics=None, checkpoint_sha256=None,
                   last_checkpoint_sha256=None, config_sha256=None, selected_epoch=None, evaluated_epochs=None,
                   runtime_seconds=None, inference_seconds=None, optimizer_attempted=False,
                   optimizer_step_completion="NOT_OBSERVED", completed_epoch_events=0)
        folder = campaign / tid
        if folder.exists():
            path_guard(folder)
        if (folder / "optimizer_started.json").exists():
            marker = read(tid + "/optimizer_started.json", "OPTIMIZER_ATTEMPT_MARKER", tid)
            require(marker["recipe"] == recipe and marker["seed"] == seed and marker["data_kind"] == "OFFICIAL_TRAIN_VALID", "Optimizer marker identity mismatch")
            timestamp(marker["time"]);row["optimizer_attempted"] = True;row["optimizer_step_completion"] = "UNCERTAIN_WITHOUT_COMPLETED_EPOCH"
        if (folder / "epoch_events.jsonl").exists():
            stamp = fingerprint(folder / "epoch_events.jsonl", 2**20);raw = (folder / "epoch_events.jsonl").read_bytes()
            require(sha(raw) == stamp["sha256"], "Epoch evidence changed")
            epochs = [json.loads(line) for line in raw.decode().splitlines()]
            require([r["epoch"] for r in epochs] == list(range(1, len(epochs) + 1)) and len(epochs) <= 100, "Invalid epoch chronology")
            evidence.append(dict(kind="EPOCH_EVENTS", id=tid, **stamp));row["completed_epoch_events"] = len(epochs)
            if epochs:
                require(row["optimizer_attempted"], "Completed epochs missing optimizer marker")
                row["optimizer_step_completion"] = "AT_LEAST_ONE_COMPLETED_EPOCH"
            safe_epochs, trace = [], []
            for epoch in epochs:
                require(source is not None and epoch["train_metric_scope"] == "ONLINE_PRE_UPDATE_CURRENT_VIEW_DIAGNOSTIC_NOT_CHECKPOINT_EVALUATION",
                        "Unknown epoch metric scope")
                require(integer(epoch["train_samples"], 1) == source["train_count"], "Epoch train population mismatch")
                losses = {k: number(epoch["train_loss"][k], -1e-6 if k == "KD" else 0) for k in ("CE", "weighted_CE", "MAE", "KD", "total")}
                require(math.isclose(losses["total"], losses["weighted_CE"] + losses["MAE"] / 3 + losses["KD"], rel_tol=1e-5, abs_tol=1e-5), "Epoch loss components mismatch")
                clean = clean_score(epoch["clean"], source["valid_count"])
                online = clean_score(epoch["train_online_metrics"], source["train_count"])
                trace.append((clean["macro_F1"], clean["MAE"]))
                choice = ref.choose_checkpoint(trace)
                require(epoch["selected_epoch"] == choice["best_epoch"] and type(epoch["early_stop"]) is bool and
                        epoch["early_stop"] == (choice["stop_epoch"] is not None) and type(epoch["checkpoint_saved"]) is bool and
                        epoch["checkpoint_saved"] == (choice["best_epoch"] == epoch["epoch"]), "Epoch checkpoint trace mismatch")
                counts = {k: integer(epoch["corruption_counts"][k]) for k in ("rows", "clean_requested", "eligible", "ineligible")}
                require(counts["rows"] == source["train_count"] == counts["clean_requested"] + counts["eligible"] + counts["ineligible"], "Epoch corruption counts mismatch")
                require(epoch["learning_rate"] == .001, "Unexpected recorded learning rate")
                times = {k: number(epoch[k]) for k in ("train_seconds", "validation_seconds", "epoch_seconds", "total_elapsed_seconds")}
                require(times["epoch_seconds"] >= times["train_seconds"] + times["validation_seconds"] and
                        (not safe_epochs or times["total_elapsed_seconds"] > safe_epochs[-1]["total_elapsed_seconds"]), "Epoch timing chronology mismatch")
                safe = dict(epoch=epoch["epoch"], selected_epoch=epoch["selected_epoch"], early_stop=epoch["early_stop"],
                    checkpoint_saved=epoch["checkpoint_saved"], train_metric_scope=epoch["train_metric_scope"],
                    train_samples=epoch["train_samples"], train_loss=losses, train_online_metrics=online, clean_valid=clean,
                    valid_supervised_loss=number(epoch["valid_supervised_loss"]), learning_rate=.001, corruption_counts=counts, **times)
                safe_epochs.append(safe)
                flat = dict(trial_id=tid, recipe=recipe, seed=seed, fit_status=states[tid],
                            **{k: safe[k] for k in ("epoch", "selected_epoch", "early_stop", "checkpoint_saved", "train_metric_scope", "train_samples", "valid_supervised_loss", "learning_rate")}, **times)
                flat.update({"train_loss_" + k: v for k, v in losses.items()})
                flat.update({"train_online_" + k: v for k, v in online.items() if k != "n"})
                flat.update({"clean_valid_" + k: v for k, v in clean.items() if k != "n"})
                flat.update({"corruption_" + k: v for k, v in counts.items()})
                epoch_csv.append(flat)
            epoch_files["epochs/" + tid + ".json"] = dict(trial_id=tid, status=states[tid], rows=safe_epochs,
                scope="All durable completed epochs, including failed/partial fits; an interrupted incomplete epoch is not invented.")
        for name, field in (("best.pt", "checkpoint_sha256"), ("last.pt", "last_checkpoint_sha256")):
            if (folder / name).exists():
                stamp = fingerprint(folder / name);row[field] = stamp["sha256"]
                evidence.append(dict(kind="SELECTED_CHECKPOINT" if name == "best.pt" else "LAST_CHECKPOINT", id=tid, **stamp))
        cfg = None
        if (folder / "config.json").exists():
            cfg = read(tid + "/config.json", "FIT_CONFIG", tid)
            provenance = dict(code_commit=commit, source_sha256=SOURCE, execution_config_hash=binding["config_hash"],
                              protocol="S02-RES-01", authorization_manifest_sha256=manifest)
            require(cfg["provenance"] == provenance and cfg["config"]["recipe"] == recipe and cfg["config"]["seed"] == seed,
                    "Fit configuration provenance mismatch")
            expected_trial = dict(recipe=recipe, seed=seed, architecture=recipe, normalizer="zscore", execution_config_hash=binding["config_hash"],
                lr=.001, weight_decay=.0001, batch_size=32, clip_norm=1, max_epochs=100, checkpoint="clean_F_then_MAE",
                p_corrupt=.25 if recipe in ("M3", "M4") else 0., KD=.1 if recipe == "M4" else 0., tau=2)
            require(cfg["config"] == expected_trial, "Fixed fit configuration changed")
            row["config_sha256"] = canonical(cfg["config"])
        if states[tid] == "COMPLETED":
            value = read(tid + "/evaluation.json", "COMPLETED_EVALUATION", tid)
            require(cfg is not None, "Completed fit lacks configuration")
            verification = read(tid + "/source_verification.json", "FIT_SOURCE_VERIFICATION", tid)
            require(value["recipe"] == recipe and value["seed"] == seed and value["parameters"] == 77542, "Fit identity/capacity mismatch")
            require(verification == dict(before=SOURCE, after=SOURCE), "Completed fit source changed")
            provenance = dict(code_commit=commit, source_sha256=SOURCE, execution_config_hash=binding["config_hash"],
                              protocol="S02-RES-01", authorization_manifest_sha256=manifest)
            require(value["provenance"] == cfg["provenance"] == provenance and value["config_hash"] == canonical(cfg["config"]), "Fit provenance/config mismatch")
            require(cfg["config"]["recipe"] == recipe and cfg["config"]["seed"] == seed and cfg["config"]["normalizer"] == "zscore", "Fit config identity mismatch")
            require(row["checkpoint_sha256"] == value["checkpoint_sha256"] == end_events[tid]["checkpoint_sha256"] and
                    row["last_checkpoint_sha256"] == value["last_checkpoint_sha256"], "Actual checkpoint hash mismatch")
            row.update(metrics=evaluation(value, recipe, seed), config_sha256=digest(value["config_hash"]),
                       selected_epoch=integer(value["selected_epoch"], 1), evaluated_epochs=integer(value["evaluated_epochs"], 1),
                       runtime_seconds=number(value["runtime_seconds"]), inference_seconds=number(value["inference_seconds"]))
            require(row["optimizer_attempted"] and row["selected_epoch"] <= row["evaluated_epochs"] == row["completed_epoch_events"] <= 100,
                    "Completed epoch evidence mismatch")
            final_choice = ref.choose_checkpoint(trace)
            require(row["selected_epoch"] == final_choice["best_epoch"] and
                    row["evaluated_epochs"] == final_choice["evaluated_epochs"] and
                    ((final_choice["stop_epoch"] is not None and final_choice["stop_epoch"] == row["evaluated_epochs"])
                     or row["evaluated_epochs"] == 100), "Final checkpoint/stop trace mismatch")
            close(row["metrics"]["clean"], epoch_files["epochs/" + tid + ".json"]["rows"][row["selected_epoch"] - 1]["clean_valid"], "Selected clean checkpoint evaluation")
        elif (folder / "evaluation.json").exists():
            pending = read(tid + "/evaluation.json", "UNACCEPTED_EVALUATION", tid)
            require(pending["status"] in ("VALIDATION_COMPLETE_PENDING_SOURCE_CHECK", "COMPLETED"), "Uncompleted fit has inconsistent evaluation state")
        require(states[tid] != "NOT_RUN" or not folder.exists(), "Unrun fit has unexplained artifacts")
        fits.append(row)
    components = None
    private_components = None
    if (campaign / "component_restore_receipt.json").exists():
        private_components = read("component_restore_receipt.json", "COMPONENT_RESTORE_RECEIPT")
        require(set(private_components) == set(map(str, SEEDS)), "Incomplete restored component seed set")
        components = {}
        for seed in SEEDS:
            require(set(private_components[str(seed)]) == {"cat", "text"}, "Incomplete component pair")
            components[seed] = {}
            for name, component in private_components[str(seed)].items():
                cache = fingerprint(campaign / f"component_{name}_s{seed}.pt")
                require(cache["sha256"] == component["cache_sha256"], "Restored component cache changed")
                evidence.append(dict(kind="COMPONENT_CACHE", id=name + f"-s{seed}", **cache))
                prov = component["provenance"]
                require(prov["source_sha256"] == SOURCE and prov["protocol_freeze"] == "R01-FREEZE-01", "Original component source/protocol mismatch")
                components[seed][name] = dict(checkpoint_sha256=digest(component["checkpoint_sha256"]),
                    config_sha256=digest(component["config_hash"]), normalizer_sha256=digest(component["normalizer_hash"]),
                    parameters=integer(component["parameters"], 1), runtime_seconds=number(component["runtime_seconds"]),
                    original_code_commit=digest(prov["code_commit"], 40), source_sha256=SOURCE,
                    original_execution_config_sha256=digest(prov["execution_config_hash"]), protocol_freeze="R01-FREEZE-01",
                    private_cache_sha256=cache["sha256"], checkpoint_verification_scope="CAMPAIGN_RESTORE_RECEIPT")
    for pid, candidate in POST.items():
        per_seed = []
        for seed in SEEDS:
            relative = pid + f"/evaluation_s{seed}.json"
            if (campaign / relative).exists():
                require(states[pid] != "NOT_RUN", "Unrun postprocessing has evaluation")
                value = read(relative, "POSTPROCESS_EVALUATION", pid + f"-s{seed}")
                require(value["seed"] == seed and value["candidate"] == candidate, "Postprocessing identity mismatch")
                require(private_components is not None and value["component_provenance"] == private_components[str(seed)] and
                        value["execution_config_hash"] == binding["config_hash"] and value["code_commit"] == commit,
                        "Postprocessing component provenance mismatch")
                per_seed.append(evaluation(value, pid, seed))
            else:
                per_seed.append(dict(seed=seed, status="NOT_RUN", clean=None, attempted96=None,
                                     sign_disagreement_clean=None, sign_disagreement_attempted96=None))
        if states[pid] == "COMPLETED":
            require(all(r["status"] == "COMPLETED" for r in per_seed) and end_events[pid]["seeds"] == list(SEEDS), "Completed postprocessing lacks all seeds")
        posts.append(dict(**candidate, status=states[pid], per_seed=per_seed))
    comparison = None
    if (campaign / "comparison.json").exists():
        old = read("comparison.json", "RECORDED_COMPARISON")
        baseline = public_summary(old["baseline"], selector)
        require(baseline["id"] == BASE and baseline["complete"], "Missing complete original champion")
        require(components is not None and baseline["parameters"] == components[17]["cat"]["parameters"], "Baseline restored component mismatch")
        close(baseline["inference_cost"], math.fsum(components[s]["cat"]["runtime_seconds"] for s in SEEDS) / 3, "Baseline inference cost")
        for seed, control in rows.get("W0-bN-zero", {}).items():
            for scope, keys in (("clean", ("Accuracy", "macro_F1", "MAE", "Pearson")), ("attempted96", ("macro_F1", "MAE"))):
                for key in keys:
                    a, b = baseline["per_seed"][seed][scope][key], control[scope][key]
                    require((a is None and b is None) or (a is not None and b is not None and abs(a-b) <= 1e-7), "Restored baseline control mismatch")
        summaries = [public_summary(v, selector) for v in old["candidates"]]
        require(len({s["id"] for s in summaries}) == len(summaries), "Duplicate comparison candidate")
        expected_ids = {p for p in POST if states[p] == "COMPLETED"} | {r for r in RECIPES if r in rows or any(states[f"{r}-s{s}"] != "NOT_RUN" for s in SEEDS)}
        recorded_ids = {s["id"] for s in summaries}
        extras = recorded_ids - expected_ids
        require(expected_ids <= recorded_ids and len(extras) <= 1 and extras <= set(RECIPES) and
                all(not s["per_seed"] for s in summaries if s["id"] in extras), "Recorded comparison candidate set mismatch")
        for summary in summaries:
            cid2 = summary["id"]
            available_rows = rows.get(cid2, {})
            expected = selector.summarize_candidate(cid2, available_rows, parameters=summary["parameters"], inference_cost=summary["inference_cost"])
            close(summary, expected, "Comparison/evaluation")
            if cid2 in RECIPES:
                require(summary["parameters"] == 77542, "Compared model capacity changed")
                measured_costs = [f["inference_seconds"] for f in fits if f["recipe"] == cid2 and f["status"] == "COMPLETED"]
                close(summary["inference_cost"], math.fsum(measured_costs) / len(measured_costs) if measured_costs else None,
                      "Model inference cost")
            else:
                use_text = POST[cid2]["variant"] != "W0"
                parameters = components[17]["cat"]["parameters"] + (components[17]["text"]["parameters"] if use_text else 0)
                cost = math.fsum(components[s]["cat"]["runtime_seconds"] + (components[s]["text"]["runtime_seconds"] if use_text else 0) for s in SEEDS) / 3
                require(summary["parameters"] == parameters, "Postprocessing component capacity mismatch")
                close(summary["inference_cost"], cost, "Postprocessing component inference cost")
        closed = old["selection"]["reason"] != "COMPARISON_STILL_OPEN"
        require(not closed or all(v == "COMPLETED" for v in states.values()), "Premature closed comparison")
        selection = selector.choose_champion(baseline, summaries, comparison_complete=closed)
        close(old["selection"], selection, "Recorded selection")
        ranked = selector.robust_ranking(baseline, summaries);pareto = selector.clean_pareto([baseline, *summaries])
        close(old["robust_ranking"], ranked, "Robust ranking");close(old["clean_pareto"], pareto, "Clean Pareto")
        comparison = dict(baseline=baseline, baseline_evidence_scope="RESTORED_HISTORICAL_S01_SUMMARY_RECORDED_BY_CAMPAIGN",
                          candidates=summaries, selection=selection, robust_ranking=ranked, clean_pareto=pareto,
                          recomputed_from_existing_aggregate_records=True, new_selection_search_performed=False)
    require(comparison is not None or (terminal["status"] != "COMPLETED" and not any(s == "COMPLETED" for s in states.values())), "Missing comparison for completed work")
    registry = read("CURRENT_CHAMPION.json", "CURRENT_CHAMPION")
    require(registry["current_champion"] == terminal["current_champion"] and registry["seed"] == 17, "Champion pointer mismatch")
    if terminal["promoted"]:
        require(comparison and comparison["selection"]["promotion_proposed"] and comparison["selection"]["selected_id"] == registry["current_champion"], "Unverified promotion")
        require(terminal.get("promotion_requires_matching_atomic_pointer") is True and
                registry.get("terminal_status_sha256") == fingerprint(campaign / "campaign_status.json")["sha256"] and
                registry.get("comparison_sha256") == fingerprint(campaign / "comparison.json")["sha256"], "Promotion transaction incomplete or changed")
        restored = read("winner_restore.json", "WINNER_RESTORE")
        require(restored == dict(status="PASS", winner=registry["current_champion"], seed=17, exact_tensor_values_equal=True, full144_views=True), "Winner restore evidence mismatch")
    else:
        require(registry["current_champion"] == BASE, "Unpromoted campaign changed champion")
        require(terminal["status"] != "COMPLETED" or not comparison["selection"]["promotion_proposed"], "Completed campaign did not finalize required promotion")
    condition_files, factor_rows = {}, []
    for identity, grids in reports.items():
        seeds = tuple(s for s in SEEDS if s in grids)
        checked = ref.aggregate(grids, expected_seeds=seeds)
        complete = seeds == SEEDS and (identity in RECIPES or states[identity] == "COMPLETED")
        conditions = []
        for condition in ref.conditions():
            condition_id = ref.condition_id(condition);eligible, total = checked["coverage"][condition_id]
            per_seed = {s: score(checked["per_condition"][s][condition_id]) for s in seeds}
            conditions.append(dict(condition=condition_id, modality=condition[0], rate=condition[1], position=condition[2],
                replicates=3 if condition[2] == "random" else 1, eligible_count=eligible, total_count=total,
                coverage=eligible / total, CLEAN_ONCE_fallback_count=total - eligible, per_seed=per_seed,
                across_seeds=seed_stats(per_seed, complete)))
        for dimension in ("modality", "rate", "position"):
            for v in sorted({r[dimension] for r in conditions}):
                selected = [r for r in conditions if r[dimension] == v]
                per_seed = {s: {k: math.fsum(r["per_seed"][s][k] for r in selected) / len(selected) for k in ("macro_F1", "MAE")} for s in seeds}
                across = seed_stats(per_seed, complete)
                for s in seeds:
                    factor_rows.append(dict(configuration=identity, complete=complete, dimension=dimension, value=v,
                        nominal_conditions=len(selected), seed=s, mean_coverage=math.fsum(r["coverage"] for r in selected) / len(selected),
                        **per_seed[s], macro_F1_mean=None if across is None else across["macro_F1"]["mean"],
                        MAE_mean=None if across is None else across["MAE"]["mean"]))
        condition_files["conditions/" + identity + ".json"] = dict(configuration=identity,
            status="COMPLETE_THREE_SEED_SET" if complete else "INCOMPLETE_NOT_RANKED", completed_seeds=list(seeds),
            aggregation_order=["replicate", "equal_weight_nominal_condition", "seed"], nominal_conditions=96, views=144, conditions=conditions)
    counts = {s: sum(v == s for v in states.values()) for s in ("NOT_RUN", "COMPLETED", "FAILED", "RESOURCE_CAP_STOP")}
    summary = dict(schema_version=1, stage="S02", campaign_id=cid, status=terminal["status"],
        evidence_level="VERIFIED_AGGREGATE_EXPORT", code_commit=commit, source_sha256=SOURCE,
        execution_config_sha256=binding["config_hash"], authorization_manifest_sha256=manifest,
        frozen_reference_sha256=REFERENCE, selection_implementation_sha256=SELECTION,
        started=started, finished=finished, runtime_seconds=number(terminal["runtime_seconds"]),
        source_verification=source, restored_components=components, counts=counts, fit_budget=12, postprocess_budget=15,
        fits_completed=terminal["fit_completed"], postprocess_completed=terminal["postprocess_completed"],
        optimizer_attempted=any(r["optimizer_attempted"] for r in fits),
        at_least_one_training_epoch_completed=any(r["completed_epoch_events"] for r in fits),
        current_champion=registry["current_champion"], promoted=terminal["promoted"], fixed_final_seed=17,
        terminal_phase=terminal["phase"], exception_category=exception_category(terminal.get("error")),
        public_events=public_events, input_file_fingerprints=evidence, new_model_runs_performed_by_exporter=0,
        limitations=["VALID summaries retain checkpoint and configuration selection optimism.",
                     "Random mask replicates are averaged within conditions; conditions have equal weight; seeds are not independent sample-level replicates.",
                     "Incomplete configurations retain completed seed evidence without complete-seed mean ranking.",
                     "An optimizer-start marker establishes an attempted update, not a completed update; completed epoch events establish training progress.",
                     "Condition rate is a supported-coordinate fraction, not physical duration; eligibility coverage and CLEAN_ONCE fallback remain explicit.",
                     "Baseline summary is historical S01 evidence recorded after component restore; this exporter does not deserialize or rerun models.",
                     "Input file hashes are published; individual masks, population/pairing fingerprints, predictions, labels, IDs and coefficients are omitted."])
    files = {"SUMMARY.json": summary, "FITS.json": fits, "POSTPROCESS.json": posts, "COMPARISON.json": comparison,
             "EPOCH_CURVES.json": dict(total_completed_epoch_rows=len(epoch_csv), files=sorted(epoch_files),
                  train_scope="ONLINE_PRE_UPDATE_CURRENT_VIEW_DIAGNOSTIC_NOT_CHECKPOINT_EVALUATION",
                  valid_scope="CLEAN_CHECKPOINT_VALIDATION", partial_epoch_rows_invented=False),
             **condition_files, **epoch_files}
    encoded = {name: (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode() for name, value in files.items()}
    csvbuf = io.StringIO(newline="")
    fields = ["configuration", "complete", "dimension", "value", "nominal_conditions", "seed", "mean_coverage", "macro_F1", "MAE", "macro_F1_mean", "MAE_mean"]
    writer = csv.DictWriter(csvbuf, fields);writer.writeheader();writer.writerows(factor_rows)
    encoded["FACTOR_DESCRIPTIVES.csv"] = csvbuf.getvalue().encode()
    epoch_buffer = io.StringIO(newline="")
    epoch_fields = list(epoch_csv[0]) if epoch_csv else ["trial_id", "recipe", "seed", "fit_status", "epoch"]
    writer = csv.DictWriter(epoch_buffer, epoch_fields);writer.writeheader();writer.writerows(epoch_csv)
    encoded["EPOCH_CURVES.csv"] = epoch_buffer.getvalue().encode()
    # Explicit schemas above ensure input extensions and free-form errors never pass through.
    for raw in encoded.values():
        require(len(raw) <= 2**20 and not re.search(rb"[A-Za-z]:[\\/]|/Users/|/home/|Bearer\s+[A-Za-z0-9]", raw), "Unsafe/oversized public aggregate")
    manifest_value = dict(schema_version=1, campaign_id=cid, exporter_sha256=sha(Path(__file__).read_bytes()),
        files=[dict(path=name, sha256=sha(raw), size=len(raw)) for name, raw in sorted(encoded.items())], self_excluded="MANIFEST.json")
    output.mkdir(parents=True)
    for name, raw in encoded.items():
        p = output / name;p.parent.mkdir(exist_ok=True)
        with p.open("xb") as stream:
            stream.write(raw)
    (output / "MANIFEST.json").write_text(json.dumps(manifest_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for row in manifest_value["files"]:
        require(fingerprint(output / row["path"]) == {k: row[k] for k in ("sha256", "size")}, "Post-write manifest mismatch")
    require({p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()} == set(encoded) | {"MANIFEST.json"}, "Export member mismatch")
    return dict(status="EXPORTED", campaign_id=cid, fits_completed=terminal["fit_completed"],
                postprocess_completed=terminal["postprocess_completed"], verified_members=len(encoded), manifest_sha256=fingerprint(output / "MANIFEST.json")["sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project", default=str(Path.cwd()))
    args = parser.parse_args()
    try:
        print(json.dumps(export(args.campaign, args.output, args.project), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status="EXPORT_REJECTED", exception_category=type(exc).__name__, reason_sha256=sha(str(exc).encode()))))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
