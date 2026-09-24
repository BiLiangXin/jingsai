"""Export S01 final/partial aggregate evidence; never copy sample rows or weights.

Stdlib only. This tool does not train, import project modules, or read source data.
It reads only named campaign JSON/JSONL files and streams checkpoint bytes for
SHA256 verification. A new destination outside the campaign and repository is
required. Run after the campaign has exited, not while evidence is being written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

EXPECTED_SOURCE = "66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd"
MODE = "PREAUTHORIZED_BY_CURRENT_USER_INSTRUCTION"
SEEDS = (17, 29, 43)
ARCHS = ("B-T", "B-A", "B-V", "B-CAT", "C0", "R0", "R1", "R2", "R1-CAP")
NORMALIZERS = ("identity", "zscore")
CONFIG_IDS = {a + "-" + n for a in ARCHS for n in NORMALIZERS} | {"LATE-identity", "LATE-zscore", "PRIOR"}
TERMINAL = {"COMPLETED", "FAILED", "RESOURCE_CAP_STOP"}
PEARSON_REASONS = {"insufficient_n", "zero_target_variance", "zero_prediction_variance"}


class ExportError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ExportError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def hash_string(value, *, commit=False, nullable=False):
    if value is None and nullable:
        return None
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}" if commit else r"[a-f0-9]{64}", value), "Invalid digest")
    return value


def integer(value, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum and (maximum is None or value <= maximum), "Invalid integer")
    return value


def number(value, low=None, high=None):
    require(type(value) in (int, float) and math.isfinite(value), "Nonfinite or nonnumeric aggregate")
    require((low is None or value >= low) and (high is None or value <= high), "Aggregate out of range")
    return value


def timestamp(value, *, nullable=False):
    if value is None and nullable:
        return None
    require(isinstance(value, str), "Invalid timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Naive timestamp")
    return parsed.isoformat()


def no_redirect(path):
    for p in (path, *path.parents):
        if p.exists():
            require(not p.is_symlink() and not (getattr(p.lstat(), "st_file_attributes", 0) & 0x400), "Redirected path rejected")


def finite_tree(value):
    if isinstance(value, dict):
        for item in value.values():
            finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            finite_tree(item)
    elif isinstance(value, float):
        require(math.isfinite(value), "Nonfinite input JSON")


def read_json(path):
    no_redirect(path)
    require(path.is_file() and path.stat().st_size <= 32 * 2**20, "Missing or oversized evidence JSON")
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ExportError("Nonfinite input JSON")))
    finite_tree(value)
    require(isinstance(value, dict), "Evidence must be a JSON object")
    return value, {"sha256": sha(raw), "size": len(raw)}


def file_hash(path):
    no_redirect(path)
    require(path.is_file(), "Missing checkpoint evidence")
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Evidence changed while hashing")
    return {"sha256": h.hexdigest(), "size": before.st_size}


def score(value):
    require(isinstance(value, dict) and {"macro_F1", "MAE"} <= value.keys(), "Missing selection scores")
    return {"macro_F1": number(value["macro_F1"], 0, 1), "MAE": number(value["MAE"], 0, 6)}


def clean_metrics(value):
    out = score(value)
    out.update(Accuracy=number(value["Accuracy"], 0, 1), weighted_F1=number(value["weighted_F1"], 0, 1), n=integer(value["n"], 1))
    pearson, reason = value["Pearson"], value["Pearson_reason"]
    if pearson is None:
        require(reason in PEARSON_REASONS, "Null Pearson requires a recognized explicit reason")
    else:
        number(pearson, -1 - 1e-12, 1 + 1e-12)
        require(reason is None, "Finite Pearson must have null reason")
    out.update(Pearson=pearson, Pearson_reason=reason)
    cm = value["confusion"]
    require(isinstance(cm, list) and len(cm) == 3 and all(isinstance(row, list) and len(row) == 3 for row in cm), "Three-class confusion matrix required")
    cm = [[integer(n) for n in row] for row in cm]
    require(sum(map(sum, cm)) == out["n"], "Confusion/count mismatch")
    per_class = value["per_class"]
    require(isinstance(per_class, list) and len(per_class) == 3, "Fixed three-class report required")
    clean_classes = []
    for k, row in enumerate(per_class):
        require(row["class"] == k, "Class order changed")
        tp, support, predicted = cm[k][k], sum(cm[k]), sum(c[k] for c in cm)
        expected = {"precision": tp / predicted if predicted else 0., "recall": tp / support if support else 0., "F1": 2 * tp / (support + predicted) if support + predicted else 0.}
        checked = {key: number(row[key], 0, 1) for key in expected}
        require(integer(row["support"]) == support and all(math.isclose(checked[key], target, rel_tol=1e-10, abs_tol=1e-12) for key, target in expected.items()), "Class aggregate mismatch")
        clean_classes.append({"class": k, "class_name": ("Negative", "Neutral", "Positive")[k], "support": support, **checked})
    require(math.isclose(out["Accuracy"], sum(cm[k][k] for k in range(3)) / out["n"], abs_tol=1e-12), "Accuracy mismatch")
    require(math.isclose(out["macro_F1"], sum(r["F1"] for r in clean_classes) / 3, abs_tol=1e-12), "Macro-F1 mismatch")
    require(math.isclose(out["weighted_F1"], sum(r["F1"] * r["support"] for r in clean_classes) / out["n"], abs_tol=1e-12), "Weighted-F1 mismatch")
    out.update(confusion=cm, per_class=clean_classes)
    return out


def sanitized_failure(value):
    if value is None:
        return None
    require(isinstance(value, str), "Invalid failure record")
    prefix = value.split(":", 1)[0]
    kind = prefix if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}(?:Error|Exception)", prefix) else "UNKNOWN_EXCEPTION_TYPE"
    lower = value.lower()
    categories = (("wall-time cap", "WALLTIME_CAP"), ("storage cap", "STORAGE_CAP"), ("gpu global memory guard", "GPU_MEMORY_GUARD"), ("out of memory", "OUT_OF_MEMORY"), ("fingerprint changed", "SOURCE_FINGERPRINT_MISMATCH"), ("nonfinite", "NONFINITE_NUMERIC"), ("authorization", "AUTHORIZATION_OR_SAFETY_GATE"), ("preflight", "AUTHORIZATION_OR_SAFETY_GATE"))
    category = next((label for text, label in categories if text in lower), "OTHER_EXECUTION_ERROR")
    return {"exception_type": kind, "category": category, "private_message_sha256": sha(value.encode()), "message_exported": False}


def verify_preregistration(rows):
    require(isinstance(rows, list) and len(rows) == 39, "Exactly 39 preregistered fits required")
    expected = {(a, n, s) for a in ARCHS[:4] for n in NORMALIZERS for s in SEEDS} | {(a, "common_preselected", s) for a in ARCHS[4:] for s in SEEDS}
    require({(r["architecture"], r["normalizer"], r["seed"]) for r in rows} == expected, "Preregistration population mismatch")
    require(len({r["trial_id"] for r in rows}) == 39, "Duplicate registered trial")
    for row in rows:
        require(re.fullmatch(r"[A-Za-z0-9-]{1,80}", row["trial_id"]) is not None, "Unsafe trial identifier")
        require(row["status"] == "NOT_RUN" and row["metrics"] is None, "Historical preregistration must remain NOT_RUN/null")
        require(sha(canonical(row["config"])) == row["config_hash"], "Preregistration config digest mismatch")
    require(all(r["architecture"] in ARCHS[:4] for r in rows[:24]), "Baseline order changed")
    require([r["architecture"] for r in rows[24:30]] == ["C0"] * 3 + ["R0"] * 3, "Mechanism order changed")


def provenance(value, source_hash, binding):
    require(isinstance(value, dict) and value["protocol_freeze"] == "R01-FREEZE-01", "Wrong protocol provenance")
    require(value["source_sha256"] == source_hash == EXPECTED_SOURCE, "Wrong source provenance")
    require(value["code_commit"] == binding["commit"] and value["execution_config_hash"] == binding["execution_config_sha256"], "Execution provenance mismatch")
    return {"code_commit": hash_string(value["code_commit"], commit=True), "source_sha256": EXPECTED_SOURCE, "execution_config_sha256": hash_string(value["execution_config_hash"]), "protocol_freeze": "R01-FREEZE-01"}


def baseline_export(value, source_hash, binding):
    provenance(value["provenance"], source_hash, binding)
    require(value["common_normalizer"] in NORMALIZERS and value["B_star"] in CONFIG_IDS, "Invalid baseline lock")
    expected_ids = {a + "-" + n for a in ARCHS[:4] for n in NORMALIZERS} | {"LATE-identity", "LATE-zscore", "PRIOR"}
    require(set(value["baseline_clean_reports"]) == expected_ids, "Incomplete baseline comparison set")
    reports = {}
    for cid, seeds in value["baseline_clean_reports"].items():
        require(set(seeds) == {str(s) for s in SEEDS}, "Missing prespecified baseline seed")
        reports[cid] = {s: {"clean": clean_metrics(row["clean"]), "parameters": integer(row["parameters"])} for s, row in seeds.items()}
    ranked = []
    for row in value["ranked"]:
        require(row["id"] in expected_ids, "Invalid ranked baseline identifier")
        ranked.append({"id": row["id"], "F": number(row["F"], 0, 1), "MAE": number(row["MAE"], 0, 6), "clean_F": number(row["clean_F"], 0, 1), "clean_MAE": number(row["clean_MAE"], 0, 6), "parameters": integer(row["parameters"])})
    require(len(ranked) == 11 and len({r["id"] for r in ranked}) == 11 and ranked[0]["id"] == value["B_star"], "Baseline ranking/lock mismatch")
    return {"common_normalizer": value["common_normalizer"], "B_star": value["B_star"], "ranked": ranked, "baseline_clean_reports": reports, "additional_model_fits": 0, "PRIOR_seed_rows_are_the_same_deterministic_reference": True, "LATE_reuses_the_corresponding_unimodal_models": True}


def export_campaign(campaign, destination, registry, watchdog_receipt=None):
    campaign, destination, registry = Path(campaign).absolute(), Path(destination).absolute(), Path(registry).absolute()
    for path in (campaign, destination, registry):
        no_redirect(path)
    campaign, destination, registry = campaign.resolve(), destination.resolve(), registry.resolve()
    repository = registry.parent.parent
    require(campaign.is_dir() and not campaign.is_relative_to(repository), "Campaign must be an existing external directory")
    require(not destination.exists() and not destination.is_relative_to(campaign) and not destination.is_relative_to(repository), "A new external export directory is required")
    registered, registry_evidence = read_json(registry)
    rows = registered["s01_preregistered_fits"]
    verify_preregistration(rows)
    evidence = [{"kind": "CANONICAL_PREREGISTRATION", **registry_evidence}]
    warnings = []
    files = {}
    for name in ("campaign.json", "campaign_status.json", "source_verification.json", "baseline_lock.json", "selection.json"):
        if (campaign / name).exists():
            files[name], ref = read_json(campaign / name)
            evidence.append({"kind": name[:-5].upper(), **ref})
    require("campaign.json" in files, "No durable campaign authorization binding; cannot fabricate a launched campaign")
    c = files["campaign.json"]
    require(c["preregistered"] == rows, "Campaign and canonical preregistration differ")
    binding = c["authorization"]["binding"]
    require(binding["authorization_mode"] == MODE, "Wrong authorization mode")
    campaign_id = binding["campaign_id"]
    require(isinstance(campaign_id, str) and re.fullmatch(r"S01-[A-Za-z0-9-]{8,100}", campaign_id), "Unsafe campaign identifier")
    budget = integer(c["execution_fit_budget"], 24, 30)
    require(budget in (24, 30) and binding["execution_fit_budget"] == budget, "Invalid campaign budget")
    require(c["deferred_trial_ids"] == [r["trial_id"] for r in rows[budget:]], "Deferred set mismatch")
    safe_binding = {"campaign_id": campaign_id, "authorization_mode": MODE, "code_commit": hash_string(binding["commit"], commit=True), "execution_config_sha256": hash_string(binding["execution_config_sha256"]), "authorized_manifest_sha256": hash_string(binding["authorized_manifest_sha256"]), "execution_fit_budget": budget, "resource_walltime_cap_hours": number(binding["resource_walltime_cap_hours"], 0), "per_fit_walltime_cap_hours": number(binding["per_fit_walltime_cap_hours"], 0), "latest_compute_finish": timestamp(binding["latest_compute_finish"])}
    source = files.get("source_verification.json")
    if source is not None:
        require(source["sha256"] == EXPECTED_SOURCE and source["splits_used"] == ["train", "valid"] and source["test_used"] is False and source["special_sets_opened"] is False, "Unsafe source scope")
        source_out = {"sha256": EXPECTED_SOURCE, "train_count": integer(source["train_count"], 1), "valid_count": integer(source["valid_count"], 1), "splits_used": ["train", "valid"], "test_used": False, "special_sets_opened": False}
    else:
        source_out = None
    by_id = {r["trial_id"]: r for r in rows}
    state = {r["trial_id"]: "NOT_RUN" for r in rows}
    events, raw_events, starts, ends = [], [], {}, {}
    if (campaign / "events.jsonl").exists():
        no_redirect(campaign / "events.jsonl")
        raw = (campaign / "events.jsonl").read_bytes()
        require(len(raw) <= 2**20, "Oversized event ledger")
        evidence.append({"kind": "PRIVATE_EVENTS", "sha256": sha(raw), "size": len(raw)})
        for line in raw.decode("utf-8").splitlines():
            event = json.loads(line)
            finite_tree(event)
            trial_id, current = event["trial_id"], event["status"]
            require(trial_id in by_id and trial_id in {r["trial_id"] for r in rows[:budget]}, "Event outside selected campaign")
            previous = state[trial_id]
            require(event["previous_status"] == previous and ((previous == "NOT_RUN" and current == "RUNNING") or (previous == "RUNNING" and current in TERMINAL)), "Invalid event transition or retry")
            require(event["retry_count"] == 0, "Unexpected retry")
            state[trial_id] = current
            out = {"trial_id": trial_id, "previous_status": previous, "status": current, "timestamp": timestamp(event["timestamp"]), "retry_count": 0}
            if current == "RUNNING":
                row = by_id[trial_id]
                require(event["architecture"] == row["architecture"] and event["seed"] == row["seed"] and event["normalizer"] in NORMALIZERS, "Event identity mismatch")
                resolved = dict(row["config"], normalizer=event["normalizer"])
                require(event["config_hash"] == sha(canonical(resolved)), "Resolved config digest mismatch")
                require(event["code_commit"] == binding["commit"] and event["source_sha256"] == EXPECTED_SOURCE, "Event provenance mismatch")
                out.update(architecture=event["architecture"], normalizer=event["normalizer"], seed=event["seed"], config_hash=event["config_hash"], code_commit=event["code_commit"], source_sha256=EXPECTED_SOURCE)
                starts[trial_id] = event
            else:
                out["runtime_seconds"] = number(event["runtime_seconds"], 0)
                ends[trial_id] = event
                if current == "COMPLETED":
                    out.update(selected_epoch=integer(event["selected_epoch"], 1, 100), checkpoint_sha256=hash_string(event["checkpoint_sha256"]), metrics={"clean": clean_metrics(event["metrics"]["clean"]), "attempted96": score(event["metrics"]["attempted96"])})
                else:
                    require(event.get("metrics") is None, "Failed attempt cannot claim final metrics")
                    out.update(metrics=None, failure=sanitized_failure(event["failure_reason"]))
            events.append(out)
            raw_events.append(event)
    records = []
    optimizer_markers = 0
    for index, row in enumerate(rows):
        trial_id, status = row["trial_id"], state[row["trial_id"]]
        trial_dir = campaign / trial_id
        out = {"trial_id": trial_id, "architecture": row["architecture"], "seed": row["seed"], "registered_normalizer": row["normalizer"], "normalizer": starts[trial_id]["normalizer"] if trial_id in starts else None, "preregistered_config_sha256": row["config_hash"], "resolved_config_sha256": starts[trial_id]["config_hash"] if trial_id in starts else None, "code_commit": binding["commit"] if trial_id in starts else None, "source_sha256": EXPECTED_SOURCE if trial_id in starts else None, "selected_for_campaign": index < budget, "status": status, "terminal_event_recorded": status in TERMINAL, "metrics": None, "selected_epoch": None, "evaluated_epochs": None, "checkpoint_sha256": None, "runtime_seconds": None, "started_at": timestamp(starts[trial_id]["timestamp"]) if trial_id in starts else None, "finished_at": timestamp(ends[trial_id]["timestamp"]) if trial_id in ends else None, "failure": sanitized_failure(ends[trial_id].get("failure_reason")) if trial_id in ends else None, "optimizer_entry_marker": False, "evidence": []}
        if status == "NOT_RUN":
            require(not trial_dir.exists(), "Unregistered execution artifacts for NOT_RUN fit")
            out["not_run_reason"] = "DEFERRED_BY_PRESELECTED_BUDGET" if index >= budget else "CAMPAIGN_ENDED_BEFORE_THIS_FIT"
            records.append(out)
            continue
        if status == "RUNNING":
            warnings.append({"trial_id": trial_id, "code": "NO_TERMINAL_EVENT_RECORDED"})
        if trial_id in ends:
            out["runtime_seconds"] = number(ends[trial_id]["runtime_seconds"], 0)
        marker = trial_dir / "optimizer_started.json"
        if marker.exists():
            data, ref = read_json(marker)
            require(data["data_kind"] == "OFFICIAL_TRAIN_VALID" and data["architecture"] == row["architecture"] and data["seed"] == row["seed"], "Invalid optimizer marker")
            timestamp(data["started_at"])
            out["optimizer_entry_marker"] = True
            optimizer_markers += 1
            out["evidence"].append({"kind": "OPTIMIZER_ENTRY", **ref})
        checkpoints = {}
        for kind in ("best", "last"):
            p = trial_dir / (kind + ".pt")
            if p.exists():
                checkpoints[kind] = file_hash(p)
        out["preserved_checkpoints"] = checkpoints
        epochs = trial_dir / "epoch_events.jsonl"
        out["completed_epoch_records"] = 0
        if epochs.exists():
            out["evidence"].append({"kind": "PRIVATE_EPOCH_HISTORY", **file_hash(epochs)})
            epoch_rows = [json.loads(line) for line in epochs.read_text(encoding="utf-8").splitlines()]
            for epoch, epoch_row in enumerate(epoch_rows, 1):
                finite_tree(epoch_row)
                require(epoch_row["epoch"] == epoch and epoch_row["data_kind"] == "OFFICIAL_TRAIN_VALID", "Invalid epoch history")
                clean_metrics(epoch_row["clean"])
                score(epoch_row["objective_score"])
            out["completed_epoch_records"] = len(epoch_rows)
        out["successful_optimizer_step_proven"] = "YES" if out["completed_epoch_records"] else "UNKNOWN" if out["optimizer_entry_marker"] else "NO_EVIDENCE"
        evaluation = trial_dir / "evaluation.json"
        if evaluation.exists():
            value, ref = read_json(evaluation)
            out["evidence"].append({"kind": "PRIVATE_EVALUATION", **ref})
            if status != "COMPLETED":
                warnings.append({"trial_id": trial_id, "code": "PRIVATE_EVALUATION_WITHOUT_COMPLETED_EVENT_NOT_PROMOTED"})
                records.append(out)
                continue
            require(value["evidence"] == "VERIFIED_OFFICIAL_VALID_RESULT" and value["trial_id"] == trial_id and value["architecture"] == row["architecture"] and value["seed"] == row["seed"] and value["normalizer"] == out["normalizer"], "Evaluation identity mismatch")
            provenance(value["provenance"], EXPECTED_SOURCE if source else None, binding)
            require(value["config_hash"] == out["resolved_config_sha256"], "Evaluation config mismatch")
            require("best" in checkpoints and checkpoints["best"]["sha256"] == value["checkpoint_sha256"] == ends[trial_id]["checkpoint_sha256"], "Selected checkpoint SHA256 mismatch")
            metrics = {"clean": clean_metrics(value["clean"]), "attempted96": score(value["attempted96"])}
            require(source is not None and metrics["clean"]["n"] == source["valid_count"], "Clean metric population differs from verified VALID source count")
            require(metrics == next(e["metrics"] for e in events if e["trial_id"] == trial_id and e["status"] == "COMPLETED"), "Event/evaluation aggregate mismatch")
            out.update(metrics=metrics, selected_epoch=integer(value["selected_epoch"], 1, 100), evaluated_epochs=integer(value["evaluated_epochs"], 1, 100), checkpoint_sha256=value["checkpoint_sha256"], parameters=integer(value["parameters"]), fit_runtime_seconds=number(value["runtime_seconds"], 0), fit_started_at=timestamp(value["started_at"]), fit_finished_at=timestamp(value["finished_at"]), evidence_level="VERIFIED")
            require(out["selected_epoch"] <= out["evaluated_epochs"] and out["selected_epoch"] == ends[trial_id]["selected_epoch"], "Epoch selection mismatch")
        else:
            require(status != "COMPLETED", "COMPLETED event lacks evaluation")
        records.append(out)
    counts = {key: sum(e["status"] == key for e in events) for key in ("RUNNING", "COMPLETED", "FAILED", "RESOURCE_CAP_STOP")}
    counts.update(NOT_RUN=sum(r["status"] == "NOT_RUN" for r in records), INCOMPLETE_WITHOUT_TERMINAL_EVENT=sum(r["status"] == "RUNNING" for r in records))
    final = files.get("campaign_status.json")
    if final is not None:
        require(final["campaign_id"] == campaign_id and final["execution_fit_budget"] == budget and final["claimed"] is True, "Final campaign binding mismatch")
        require(final["status"] in {"COMPLETED", "FAILED", "PARTIAL_RESOURCE_STOP"}, "Unexpected final campaign status")
        require(final["counts"] == {k: counts[k] for k in ("RUNNING", "COMPLETED", "FAILED", "RESOURCE_CAP_STOP")}, "Final event counts mismatch")
        require(final["official_data_training_performed"] == bool(optimizer_markers), "Training marker/count mismatch")
        final_status, runtime, error = final["status"], number(final["runtime_seconds"], 0), sanitized_failure(final["error"])
        if final_status == "COMPLETED":
            require(counts["COMPLETED"] == budget and not counts["FAILED"] and not counts["RESOURCE_CAP_STOP"] and not counts["INCOMPLETE_WITHOUT_TERMINAL_EVENT"], "Campaign falsely claims completion")
    else:
        require(watchdog_receipt is not None, "Missing final status requires an explicit completed watchdog receipt")
        receipt, receipt_hash = read_json(Path(watchdog_receipt))
        require(receipt["campaign_id"] == campaign_id and receipt["watchdog_fired"] is True and receipt["automatic_retry"] is False and type(receipt["exit_code"]) is int and receipt["stop_reason"] == "TOTAL_OR_ABSOLUTE_WALLTIME_CAP", "Invalid watchdog completion evidence")
        finished = dt.datetime.fromisoformat(timestamp(receipt["finished_at"]))
        started = dt.datetime.fromisoformat(timestamp(receipt["started_at"]))
        runtime = number((finished - started).total_seconds(), 0)
        final_status, error = "PARTIAL_RESOURCE_STOP", {"exception_type": "EXTERNAL_WATCHDOG", "category": "WALLTIME_CAP", "message_exported": False}
        evidence.append({"kind": "PRIVATE_WATCHDOG_RECEIPT", **receipt_hash})
        warnings.append({"code": "NO_DURABLE_FINAL_CAMPAIGN_STATUS_EXTERNAL_WATCHDOG_CONFIRMS_STOP"})
    baseline = baseline_export(files["baseline_lock.json"], EXPECTED_SOURCE if source else None, binding) if "baseline_lock.json" in files else None
    if baseline is not None:
        require(all(row["status"] == "COMPLETED" for row in records[:24]), "Baseline lock requires all 24 baseline fits completed")
        require(all(row["clean"]["n"] == source["valid_count"] for seeds in baseline["baseline_clean_reports"].values() for row in seeds.values()), "Baseline population differs from verified VALID source count")
    selection = None
    if "selection.json" in files:
        value = files["selection.json"]
        provenance(value["provenance"], EXPECTED_SOURCE if source else None, binding)
        require(baseline is not None and value["B_star"] == baseline["B_star"] and value["common_normalizer"] == baseline["common_normalizer"] and value["executed_budget"] == budget, "Selection/baseline mismatch")
        decision = value["decision"]
        require(decision["configuration"] in CONFIG_IDS and decision["seed"] == 17 and decision["reason"] in {"WINNER_FIXED_SEED_GUARD_PASS", "CLEAN_REFERENCE_FALLBACK"}, "Invalid final selection")
        chosen = decision["configuration"]
        allowed_selection = {baseline["B_star"]}
        if budget == 30:
            allowed_selection.update(a + "-" + baseline["common_normalizer"] for a in ("C0", "R0"))
        require(chosen in allowed_selection, "Recorded selection is outside authorized B*/C0/R0 comparison")
        if chosen in {"PRIOR", "LATE-identity", "LATE-zscore"}:
            require(chosen == baseline["B_star"], "Zero-fit reference can be selected only as verified B*")
        else:
            selected_rows = [row for row in records if row["status"] == "COMPLETED" and row["normalizer"] is not None and row["architecture"] + "-" + row["normalizer"] == chosen]
            require({row["seed"] for row in selected_rows} == set(SEEDS) and len(selected_rows) == 3,
                    "Recorded selection requires all three completed authorized seeds including seed17")
            require(all(row["selected_for_campaign"] and row["checkpoint_sha256"] is not None for row in selected_rows),
                    "Selected model must have verified checkpoint evidence within authorized campaign")
        require(counts["COMPLETED"] == budget, "Selection file exists before selected campaign fully completed")
        selection = {"configuration": decision["configuration"], "seed": 17, "reason": decision["reason"], "selection_recomputed_by_exporter": False}
    require(final_status != "COMPLETED" or selection is not None, "Completed campaign lacks locked selection")
    configuration_summary = []
    completed = [r for r in records if r["status"] == "COMPLETED"]
    for cid in sorted({r["architecture"] + "-" + r["normalizer"] for r in completed}):
        group = [r for r in completed if r["architecture"] + "-" + r["normalizer"] == cid]
        if {r["seed"] for r in group} != set(SEEDS):
            configuration_summary.append({"configuration": cid, "status": "INCOMPLETE_SEED_SET", "completed_seeds": sorted(r["seed"] for r in group), "mean_metrics": None})
            continue
        aggregate = {objective: {key: {"mean": math.fsum(r["metrics"][objective][key] for r in group) / 3, "seed_sd_ddof1": statistics.stdev(r["metrics"][objective][key] for r in group)} for key in ("macro_F1", "MAE")} for objective in ("clean", "attempted96")}
        configuration_summary.append({"configuration": cid, "status": "ALL_THREE_PRESPECIFIED_SEEDS_COMPLETED", "seeds": list(SEEDS), "mean_metrics": aggregate})
    summary = {"schema_version": 1, "stage": "S01", "data_kind": "OFFICIAL_TRAIN_VALID", "evidence_level": "VERIFIED", "authorization": safe_binding, "S01_EXECUTION_STATUS": final_status, "AUTHORIZATION_MODE": MODE, "USER_CONFIRMATION_REQUIRED": "NO", "EXECUTION_FIT_BUDGET": budget, "REGISTERED_FITS": 39, "EXECUTED_FITS": counts["RUNNING"], "COMPLETED_FITS": counts["COMPLETED"], "FAILED_FITS": counts["FAILED"], "RESOURCE_CAP_STOP_FITS": counts["RESOURCE_CAP_STOP"], "INCOMPLETE_FITS_WITHOUT_TERMINAL_EVENT": counts["INCOMPLETE_WITHOUT_TERMINAL_EVENT"], "COMMON_NORMALIZER": baseline["common_normalizer"] if baseline else "NOT_RESOLVED", "B_STAR": baseline["B_star"] if baseline else None, "OFFICIAL_MODEL_EXPERIMENTS": "RUN" if optimizer_markers else "NOT_RUN", "OFFICIAL_DATA_TRAINING_PERFORMED": "YES" if optimizer_markers else "NO", "VALID_METRICS_AVAILABLE": "YES" if completed else "NO", "TEST_USED_FOR_SELECTION": "NO", "ATTACHMENT3_4_INSPECTED": "NO", "ATTACHMENT3_MASK_AVAILABILITY": "UNKNOWN", "runtime_seconds": runtime, "failure": error, "source_verification": source_out, "counts": counts, "optimizer_entry_markers": optimizer_markers, "training_evidence_basis": "Durable marker immediately before optimizer entry; marker alone does not certify successful step completion.", "selection": selection, "warnings": warnings, "private_evidence_fingerprints": evidence, "limitations": ["Only TRAIN learning and VALID selection/evaluation; no TEST or attachment inference.", "The same VALID set is used repeatedly for checkpoint/configuration selection; selection optimism remains.", "Across-seed standard deviations are descriptive; no significance or unbiased-generalization claim.", "Attempted96 aggregates preserve random replicate -> equal-weight nominal condition -> seed order from the executed protocol.", "No sample-level records, labels, IDs, predictions, mask arrays/fingerprints, normalizer coefficients, checkpoint weights, or private paths are exported.", "No additional selection, retries, lucky-seed search, or model fitting is performed by this exporter."]}
    payloads = {"SUMMARY.json": summary, "FITS.json": {"schema_version": 1, "campaign_id": campaign_id, "registered_fits": 39, "fits": records}, "EVENTS.json": {"schema_version": 1, "campaign_id": campaign_id, "events": events}, "CONFIGURATION_SUMMARY.json": {"schema_version": 1, "aggregation_order": ["random_replicate", "equal_weight_nominal_condition", "seed"], "scope": "Derived descriptives only; no new model selection", "configurations": configuration_summary}, "BASELINE_AND_SELECTION.json": {"schema_version": 1, "campaign_id": campaign_id, "baseline": baseline, "selection": selection}}
    for value in payloads.values():
        finite_tree(value)
    destination.mkdir(parents=True)
    exported = []
    for name, value in payloads.items():
        raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()
        with (destination / name).open("xb") as stream:
            stream.write(raw)
        exported.append({"path": name, "sha256": sha(raw), "size": len(raw)})
    manifest = {"schema_version": 1, "campaign_id": campaign_id, "exporter_sha256": sha(Path(__file__).read_bytes()), "files": exported, "self_excluded": "MANIFEST.json", "private_inputs_exported": False}
    (destination / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in exported:
        raw = (destination / item["path"]).read_bytes()
        require(len(raw) == item["size"] and sha(raw) == item["sha256"], "Export round-trip verification failed")
    require({p.name for p in destination.iterdir()} == set(payloads) | {"MANIFEST.json"}, "Unexpected export member")
    return {"status": "EXPORTED_AGGREGATE_EVIDENCE", "campaign_id": campaign_id, "members_verified": len(exported), "manifest_sha256": sha((destination / "MANIFEST.json").read_bytes()), "campaign_status": final_status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--destination", required=True)
    default_registry = Path.cwd() / "docs" / "EXPERIMENT_REGISTER.json"
    parser.add_argument("--registry", default=str(default_registry), help="Canonical preregistration JSON; read only")
    parser.add_argument("--watchdog-receipt", help="Optional actual completed outer-watchdog receipt, required if final campaign status is absent")
    args = parser.parse_args()
    try:
        result = export_campaign(args.campaign, args.destination, args.registry, args.watchdog_receipt)
    except (ExportError, OSError, ValueError, KeyError, TypeError) as exc:
        # Never print raw exception messages or paths to public-facing stdout.
        print(json.dumps({"status": "EXPORT_REJECTED", "exception_type": type(exc).__name__, "detail_sha256": sha(str(exc).encode())}))
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
