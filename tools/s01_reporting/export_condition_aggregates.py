"""Export already-computed S01 condition aggregates; no source reads or model runs.

Run after campaign exit and the verified main aggregate export. Named completed-fit
evaluation JSON is read; selected checkpoint bytes are streamed only for SHA256.
The frozen stdlib reference validates 96 conditions, 144 views and paired masks.
Only aggregate counts and scores are exported; no pairing fingerprints are copied.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import statistics
import types
from pathlib import Path

REFERENCE_SHA256 = "1cd4b73bb748284b4941625d92be89522771eff8a11e4044547e5f513ea62495"
SOURCE_SHA256 = "66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd"
SEEDS = (17, 29, 43)
BASELINES = ("B-T", "B-A", "B-V", "B-CAT")
ALLOWED = BASELINES + ("C0", "R0")
NORMALIZERS = ("identity", "zscore")
KEYS = ("macro_F1", "MAE")


class ConditionExportError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ConditionExportError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def no_redirect(path):
    for p in (path, *path.parents):
        if p.exists():
            require(not p.is_symlink() and not getattr(p.lstat(), "st_file_attributes", 0) & 0x400, "Redirected path rejected")


def load(path, limit=32 * 2**20):
    no_redirect(path)
    require(path.is_file() and path.stat().st_size <= limit, "Missing or oversized JSON evidence")
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ConditionExportError("Nonfinite JSON")))
    return data, {"sha256": sha(raw), "size": len(raw)}


def number(value, lo=0, hi=None):
    require(type(value) in (int, float) and math.isfinite(value) and value >= lo and (hi is None or value <= hi), "Invalid aggregate numeric value")
    return value


def integer(value, lo=0):
    require(type(value) is int and value >= lo, "Invalid count")
    return value


def scores(value):
    return {"macro_F1": number(value["macro_F1"], 0, 1), "MAE": number(value["MAE"], 0, 6)}


def reference_at(path):
    no_redirect(path)
    raw = path.read_bytes()
    require(sha(raw) == REFERENCE_SHA256, "Reference differs from frozen R01 implementation")
    module = types.ModuleType("frozen_r01_condition_export_reference")
    # Compile fixed, hash-verified source directly, without writing bytecode caches.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    require(len(module.conditions()) == 96, "Frozen condition count changed")
    return module


def mean_score(values):
    require(bool(values), "Empty aggregate")
    return {key: math.fsum(value[key] for value in values) / len(values) for key in KEYS}


def across_seed(per_seed, complete):
    if not complete:
        return None
    require(set(per_seed) == set(SEEDS), "All three seeds required for across-seed summary")
    return {key: {"mean": math.fsum(per_seed[s][key] for s in SEEDS) / 3,
                  "seed_sd_ddof1": statistics.stdev(per_seed[s][key] for s in SEEDS)} for key in KEYS}


def csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def checkpoint_hash(path):
    no_redirect(path)
    require(path.is_file(), "Selected checkpoint bytes missing")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Selected checkpoint changed during verification")
    return {"sha256": digest.hexdigest(), "size": before.st_size}


def match_evidence(rows, kind, actual):
    matched = [r for r in rows if r.get("kind") == kind]
    require(len(matched) == 1 and all(matched[0].get(key) == actual[key] for key in ("sha256", "size")), "Main export input fingerprint mismatch")


def verified_main(main_export):
    main_export = Path(main_export).absolute()
    no_redirect(main_export)
    main_export = main_export.resolve()
    manifest, manifest_ref = load(main_export / "MANIFEST.json")
    expected = {"SUMMARY.json", "FITS.json", "EVENTS.json", "CONFIGURATION_SUMMARY.json", "BASELINE_AND_SELECTION.json"}
    require(isinstance(manifest.get("files"), list) and len(manifest["files"]) == 5 and {r.get("path") for r in manifest["files"]} == expected, "Wrong main export member set")
    require({p.name for p in main_export.iterdir()} == expected | {"MANIFEST.json"}, "Unexpected main export member")
    payloads = {}
    for row in manifest["files"]:
        value, actual = load(main_export / row["path"])
        require(row["sha256"] == actual["sha256"] and row["size"] == actual["size"], "Main export manifest verification failed")
        payloads[row["path"]] = value
    summary = payloads["SUMMARY.json"]
    require(summary["evidence_level"] == "VERIFIED" and summary["data_kind"] == "OFFICIAL_TRAIN_VALID" and summary["S01_EXECUTION_STATUS"] in ("COMPLETED", "FAILED", "PARTIAL_RESOURCE_STOP"), "Main export lacks verified terminal campaign evidence")
    fits = payloads["FITS.json"]
    require(summary["REGISTERED_FITS"] == fits["registered_fits"] == 39 and len(fits["fits"]) == 39 and len({r["trial_id"] for r in fits["fits"]}) == 39, "Main fit registry count mismatch")
    cid = summary["authorization"]["campaign_id"]
    require(manifest["campaign_id"] == fits["campaign_id"] == payloads["EVENTS.json"]["campaign_id"] == cid, "Main campaign identity mismatch")
    completed = {r["trial_id"]: r for r in fits["fits"] if r["status"] == "COMPLETED"}
    require(summary["COMPLETED_FITS"] == len(completed), "Main completed count mismatch")
    for event_status, summary_key in (("RUNNING", "EXECUTED_FITS"), ("COMPLETED", "COMPLETED_FITS"), ("FAILED", "FAILED_FITS"), ("RESOURCE_CAP_STOP", "RESOURCE_CAP_STOP_FITS")):
        require(sum(e["status"] == event_status for e in payloads["EVENTS.json"]["events"]) == summary[summary_key], "Main event count mismatch")
    return summary, completed, manifest_ref


def export_conditions(campaign, destination, reference, main_export, watchdog_receipt=None):
    campaign, destination, reference = (Path(x).absolute() for x in (campaign, destination, reference))
    for p in (campaign, destination, reference):
        no_redirect(p)
    campaign, destination, reference = (x.resolve() for x in (campaign, destination, reference))
    repository = reference.parents[2]
    require(campaign.is_dir() and not campaign.is_relative_to(repository), "Campaign must be outside repository")
    require(not destination.exists() and not destination.is_relative_to(campaign) and not destination.is_relative_to(repository), "New external destination required")
    ref = reference_at(reference)
    main, main_completed, main_manifest_ref = verified_main(main_export)
    campaign_data, campaign_evidence = load(campaign / "campaign.json")
    binding = campaign_data["authorization"]["binding"]
    require(binding["authorization_mode"] == "PREAUTHORIZED_BY_CURRENT_USER_INSTRUCTION", "Unknown authorization mode")
    require(binding["execution_fit_budget"] == campaign_data["execution_fit_budget"] and binding["execution_fit_budget"] in (24, 30), "Invalid campaign budget")
    campaign_id = binding["campaign_id"]
    require(isinstance(campaign_id, str) and ref.re.fullmatch(r"S01-[A-Za-z0-9-]{8,100}", campaign_id), "Invalid campaign identifier")
    for field, length in (("commit", 40), ("execution_config_sha256", 64)):
        require(ref.re.fullmatch(r"[a-f0-9]{" + str(length) + r"}", binding[field]), "Invalid binding digest")
    require(main["authorization"]["campaign_id"] == campaign_id and main["authorization"]["code_commit"] == binding["commit"] and main["authorization"]["execution_config_sha256"] == binding["execution_config_sha256"] and main["EXECUTION_FIT_BUDGET"] == binding["execution_fit_budget"], "Main/current campaign binding mismatch")
    private_inputs = main["private_evidence_fingerprints"]
    match_evidence(private_inputs, "CAMPAIGN", campaign_evidence)
    source, source_ref = load(campaign / "source_verification.json")
    match_evidence(private_inputs, "SOURCE_VERIFICATION", source_ref)
    require(source == main["source_verification"] and source["sha256"] == SOURCE_SHA256 and source["splits_used"] == ["train", "valid"] and source["test_used"] is False and source["special_sets_opened"] is False, "Source verification/scope mismatch")
    valid_count = integer(source["valid_count"], 1)
    integer(source["train_count"], 1)
    if (campaign / "campaign_status.json").is_file():
        terminal, terminal_ref = load(campaign / "campaign_status.json")
        match_evidence(private_inputs, "CAMPAIGN_STATUS", terminal_ref)
        require(terminal["status"] == main["S01_EXECUTION_STATUS"] and terminal["campaign_id"] == campaign_id and terminal["claimed"] is True and terminal["counts"] == {s: main["counts"][s] for s in ("RUNNING", "COMPLETED", "FAILED", "RESOURCE_CAP_STOP")}, "Terminal campaign evidence mismatch")
    else:
        require(watchdog_receipt is not None, "Missing campaign termination requires actual watchdog receipt")
        terminal, terminal_ref = load(Path(watchdog_receipt))
        match_evidence(private_inputs, "PRIVATE_WATCHDOG_RECEIPT", terminal_ref)
        require(main["S01_EXECUTION_STATUS"] == "PARTIAL_RESOURCE_STOP" and terminal["campaign_id"] == campaign_id and terminal["watchdog_fired"] is True and terminal["automatic_retry"] is False and type(terminal["exit_code"]) is int and terminal["stop_reason"] == "TOTAL_OR_ABSOLUTE_WALLTIME_CAP", "Invalid terminal watchdog evidence")
        require(datetime.datetime.fromisoformat(terminal["finished_at"]).tzinfo is not None, "Watchdog lacks finished timestamp")
    prereg = campaign_data["preregistered"]
    require(len(prereg) == 39 and len({r["trial_id"] for r in prereg}) == 39, "Expected 39 registered fits")
    allowed_rows = {r["trial_id"]: r for r in prereg[:binding["execution_fit_budget"]]}
    states = {t: "NOT_RUN" for t in allowed_rows}
    events_path = campaign / "events.jsonl"
    no_redirect(events_path)
    require(events_path.is_file() and events_path.stat().st_size <= 2**20, "Missing or oversized event ledger")
    raw_events = events_path.read_bytes()
    match_evidence(private_inputs, "PRIVATE_EVENTS", {"sha256": sha(raw_events), "size": len(raw_events)})
    events = [json.loads(line) for line in raw_events.decode("utf-8").splitlines()]
    evidence = [{"kind": "VERIFIED_MAIN_EXPORT_MANIFEST", **main_manifest_ref}, {"kind": "CAMPAIGN", **campaign_evidence}, {"kind": "PRIVATE_SOURCE_VERIFICATION", **source_ref}, {"kind": "PRIVATE_TERMINATION_EVIDENCE", **terminal_ref}, {"kind": "PRIVATE_EVENTS", "sha256": sha(raw_events), "size": len(raw_events)}]
    end_events = {}
    for event in events:
        tid, status = event["trial_id"], event["status"]
        require(tid in states and event["previous_status"] == states[tid] and event["retry_count"] == 0, "Invalid event or retry")
        require((states[tid] == "NOT_RUN" and status == "RUNNING") or (states[tid] == "RUNNING" and status in ("COMPLETED", "FAILED", "RESOURCE_CAP_STOP")), "Invalid event transition")
        states[tid] = status
        if status == "COMPLETED":
            end_events[tid] = event
    require(set(end_events) == set(main_completed), "Main/current completed fit set differs")
    grids, evaluations = {}, {}
    pairing_reference = {}
    population = None
    condition_ids = {ref.condition_id(c): c for c in ref.conditions()}
    for tid, event in end_events.items():
        row = allowed_rows[tid]
        require(ref.re.fullmatch(r"[A-Za-z0-9-]{1,80}", tid), "Unsafe trial identifier")
        value, file_evidence = load(campaign / tid / "evaluation.json")
        verified_fit = main_completed[tid]
        match_evidence(verified_fit["evidence"], "PRIVATE_EVALUATION", file_evidence)
        require(value["trial_id"] == tid and value["architecture"] == row["architecture"] and value["seed"] == row["seed"], "Evaluation identity mismatch")
        architecture, normalizer, seed = value["architecture"], value["normalizer"], value["seed"]
        require(architecture in ALLOWED and normalizer in NORMALIZERS and seed in SEEDS, "Unauthorized architecture or seed")
        require(value["evidence"] == "VERIFIED_OFFICIAL_VALID_RESULT", "Nonofficial evaluation cannot be presented as official")
        provenance = value["provenance"]
        require(provenance["code_commit"] == binding["commit"] and provenance["source_sha256"] == SOURCE_SHA256 and provenance["execution_config_hash"] == binding["execution_config_sha256"] and provenance["protocol_freeze"] == "R01-FREEZE-01", "Evaluation provenance mismatch")
        cfg = dict(row["config"], normalizer=normalizer)
        cfg_digest = sha(json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())
        require(value["config_hash"] == cfg_digest, "Resolved configuration mismatch")
        require(value["checkpoint_sha256"] == event["checkpoint_sha256"] and value["selected_epoch"] == event["selected_epoch"], "Selected checkpoint evidence mismatch")
        checkpoint_ref = checkpoint_hash(campaign / tid / "best.pt")
        require(checkpoint_ref["sha256"] == value["checkpoint_sha256"] == verified_fit["checkpoint_sha256"] and checkpoint_ref == verified_fit["preserved_checkpoints"]["best"], "Actual selected checkpoint/main export mismatch")
        require(verified_fit["architecture"] == architecture and verified_fit["normalizer"] == normalizer and verified_fit["seed"] == seed and verified_fit["resolved_config_sha256"] == cfg_digest and verified_fit["selected_epoch"] == value["selected_epoch"] and scores(verified_fit["metrics"]["clean"]) == scores(value["clean"]) and scores(verified_fit["metrics"]["attempted96"]) == scores(value["attempted96"]), "Main fit/evaluation aggregate mismatch")
        require(integer(value["clean"]["n"], 1) == valid_count == verified_fit["metrics"]["clean"]["n"], "Clean population differs from verified VALID source count")
        cid = architecture + "-" + normalizer
        require(seed not in grids.setdefault(cid, {}), "Duplicate configuration seed")
        reports = value["condition_reports"]
        # frozen aggregate verifies exact nominal/replicate structure and seed pairing.
        checked = ref.aggregate({seed: reports}, expected_seeds=(seed,))
        require(checked["conditions"] == 96 and checked["prediction_views_per_sample_per_seed"] == 144, "Wrong condition/view count")
        require(scores(value["attempted96"]) == checked["per_seed"][seed], "Stored attempted96 differs from reference aggregation")
        require(scores(event["metrics"]["attempted96"]) == checked["per_seed"][seed], "Event attempted96 mismatch")
        scores(value["clean"])
        for condition, views in reports.items():
            for replica, view in enumerate(views):
                eligible, total = integer(view["eligible_count"]), integer(view["total_count"], 1)
                require(eligible <= total and math.isclose(number(view["coverage"], 0, 1), eligible / total, abs_tol=1e-12), "Coverage disagreement")
                scores(view["attempted"])
                if population is None:
                    population = total
                require(total == population == valid_count, "Population differs across models or verified VALID source count")
                stamp = view["pairing"]
                key = (condition, replica)
                current = (stamp["population"], stamp["eligibility"], stamp["view"], eligible, total)
                if key in pairing_reference:
                    require(pairing_reference[key] == current, "Unpaired corruption/population across models")
                else:
                    pairing_reference[key] = current
        grids[cid][seed] = reports
        evaluations.setdefault(cid, {})[seed] = {"clean": scores(value["clean"]), "attempted96": scores(value["attempted96"])}
        evidence.append({"kind": "PRIVATE_COMPLETED_EVALUATION", "trial_id": tid, **file_evidence})
    configurations, seed_csv, condition_csv, factor_csv = [], [], [], []
    for cid, reports in sorted(grids.items()):
        seeds = tuple(s for s in SEEDS if s in reports)
        checked = ref.aggregate(reports, expected_seeds=seeds)
        complete = seeds == SEEDS
        status = "ALL_THREE_PRESPECIFIED_SEEDS_COMPLETED" if complete else "INCOMPLETE_SEED_SET_NOT_RANKED"
        conditions = []
        for condition, (group, fraction, position) in condition_ids.items():
            per_seed = {s: scores(checked["per_condition"][s][condition]) for s in seeds}
            eligible, total = checked["coverage"][condition]
            row = dict(condition=condition, target_modality_group=group, nominal_supported_window_fraction=fraction,
                       position=position, random_replicates=3 if position == "random" else 1,
                       eligible_count=eligible, total_count=total, coverage=eligible / total,
                       CLEAN_ONCE_fallback_count=total - eligible, per_seed=per_seed,
                       across_seeds=across_seed(per_seed, complete))
            conditions.append(row)
            shared = dict(configuration=cid, status=status, condition=condition, target_modality_group=group,
                          nominal_supported_window_fraction=fraction, position=position,
                          random_replicates=row["random_replicates"], eligible_count=eligible,
                          total_count=total, coverage=eligible / total, CLEAN_ONCE_fallback_count=total - eligible)
            for s in seeds:
                seed_csv.append({**shared, "seed": s, **per_seed[s]})
            condition_csv.append({**shared, "completed_seeds": ";".join(map(str, seeds)),
                **{key + suffix: (row["across_seeds"][key][field] if complete else None) for key in KEYS for suffix, field in (("_mean", "mean"), ("_seed_sd_ddof1", "seed_sd_ddof1"))}})
        factors = []
        for dimension in ("target_modality_group", "nominal_supported_window_fraction", "position"):
            for value in sorted({r[dimension] for r in conditions}):
                selected = [r for r in conditions if r[dimension] == value]
                per_seed = {s: mean_score([r["per_seed"][s] for r in selected]) for s in seeds}
                means = across_seed(per_seed, complete)
                row = dict(dimension=dimension, value=value, nominal_conditions=len(selected),
                           mean_coverage=math.fsum(r["coverage"] for r in selected) / len(selected),
                           per_seed=per_seed, across_seeds=means)
                factors.append(row)
                for s in seeds:
                    factor_csv.append(dict(configuration=cid, status=status, dimension=dimension, value=value,
                        nominal_conditions=len(selected), seed=s, mean_coverage=row["mean_coverage"], **per_seed[s]))
        configurations.append(dict(configuration=cid, status=status, completed_seeds=list(seeds),
            nominal_conditions=96, prediction_views_per_sample_per_seed=144,
            attempted96_per_seed={s: checked["per_seed"][s] for s in seeds},
            attempted96_across_seeds=across_seed({s: checked["per_seed"][s] for s in seeds}, complete),
            conditions=conditions, factor_descriptives=factors))
    summary = dict(schema_version=1, campaign_id=campaign_id, stage="S01", data_kind="OFFICIAL_VALID_AGGREGATES_ONLY",
        evidence_level="VERIFIED", source_sha256=SOURCE_SHA256, code_commit=binding["commit"],
        reference_sha256=REFERENCE_SHA256, execution_config_sha256=binding["execution_config_sha256"],
        reference_aggregate_called=True, nominal_conditions=96, prediction_views_per_sample_per_seed=144,
        aggregation_order=["random_replicate", "equal_weight_nominal_condition", "seed"],
        ranking_performed=False, new_model_evaluations=0, completed_fits_included=len(end_events),
        complete_configurations=sum(c["status"] == "ALL_THREE_PRESPECIFIED_SEEDS_COMPLETED" for c in configurations),
        incomplete_configurations=sum(c["status"] != "ALL_THREE_PRESPECIFIED_SEEDS_COMPLETED" for c in configurations),
        skipped=[dict(configuration=cid, reason="NO_STORED_FULL_96_CONDITION_GRID") for cid in ("PRIOR", "LATE-identity", "LATE-zscore")],
        uncompleted_trials=[dict(trial_id=tid, status=status, condition_metrics=None) for tid, status in states.items() if status != "COMPLETED"],
        private_input_fingerprints=evidence, configurations=configurations,
        formulas=dict(condition_score="arithmetic mean of 1 or 3 replicate attempted-population scores",
                      attempted96="arithmetic mean of exactly 96 nominal condition scores within each seed",
                      across_seeds="arithmetic mean of seeds 17,29,43 only if all completed; sample SD uses ddof=1",
                      factor_descriptive="within each seed, equal mean over matching nominal conditions; then mean across the full three-seed set",
                      coverage="eligible_count / total_count; eligibility is paired across seeds, models and replicates",
                      CLEAN_ONCE_fallback_count="total_count - eligible_count per nominal condition and per view; never multiplied into score weights"),
        limitations=["These are descriptive VALID summaries at already-selected checkpoints; no extra model selection or evaluation was performed.",
                     "Nominal window fractions refer to supported coordinates, not physical seconds or realized missing fractions of observed vectors.",
                     "Position names identify requested locations; the legal-window generator may relocate them. This report does not infer unrecorded displacement.",
                     "Coverage refers to artificial-window eligibility; fallback cases use CLEAN_ONCE in attempted-population scores.",
                     "The same VALID set informed checkpoint/configuration selection; the curves remain subject to selection optimism.",
                     "No independent-sample significance is claimed from random replicates or three training seeds.",
                     "Pairing fingerprints, row ordinals, sample IDs, individual predictions/labels and mask arrays are verified privately and not exported.",
                     "No TEST, attachment, source PKL, deserialized checkpoint tensor, or normalizer coefficient is read by this tool; checkpoint bytes are streamed solely to verify SHA256."])
    common_fields = ["configuration", "status", "condition", "target_modality_group", "nominal_supported_window_fraction", "position", "random_replicates", "eligible_count", "total_count", "coverage", "CLEAN_ONCE_fallback_count"]
    files = {
        "CONDITION_AGGREGATES.json": (json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode(),
        "CONDITIONS_PER_SEED.csv": csv_bytes(seed_csv, common_fields + ["seed", "macro_F1", "MAE"]),
        "CONDITIONS_ACROSS_SEEDS.csv": csv_bytes(condition_csv, common_fields + ["completed_seeds", "macro_F1_mean", "macro_F1_seed_sd_ddof1", "MAE_mean", "MAE_seed_sd_ddof1"]),
        "FACTOR_DESCRIPTIVES_PER_SEED.csv": csv_bytes(factor_csv, ["configuration", "status", "dimension", "value", "nominal_conditions", "seed", "mean_coverage", "macro_F1", "MAE"])}
    destination.mkdir(parents=True)
    manifest = dict(schema_version=1, campaign_id=campaign_id, exporter_sha256=sha(Path(__file__).read_bytes()),
        files=[], self_excluded="MANIFEST.json", pairing_fingerprints_exported=False)
    for name, raw in files.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
        manifest["files"].append(dict(path=name, sha256=sha(raw), size=len(raw)))
    (destination / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for row in manifest["files"]:
        raw = (destination / row["path"]).read_bytes()
        require(sha(raw) == row["sha256"] and len(raw) == row["size"], "Export verification failed")
    require({p.name for p in destination.iterdir()} == set(files) | {"MANIFEST.json"}, "Unexpected export member")
    return dict(status="CONDITION_AGGREGATES_EXPORTED", campaign_id=campaign_id, completed_fits=len(end_events),
                complete_configurations=summary["complete_configurations"], incomplete_configurations=summary["incomplete_configurations"],
                members_verified=len(files), manifest_sha256=sha((destination / "MANIFEST.json").read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--reference", default=str(Path.cwd() / "research/r01/reference.py"))
    parser.add_argument("--main-export", required=True, help="Verified aggregate export directory from the main exporter after campaign exit")
    parser.add_argument("--watchdog-receipt", help="Actual finished watchdog receipt, required when campaign_status.json is absent")
    args = parser.parse_args()
    try:
        result = export_conditions(args.campaign, args.destination, args.reference, args.main_export, args.watchdog_receipt)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status="CONDITION_EXPORT_REJECTED", exception_type=type(exc).__name__, detail_sha256=sha(str(exc).encode()))))
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
