"""Read-only S00C train/valid diagnostics of the two trusted official PKLs.

The loaded pickle contains test, but this module never indexes or computes on it.
Attachment 3/4 files are never opened. No labels or IDs are read from any split.
"""
from __future__ import annotations

import argparse
import gc
import json
import pickle
import platform
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np

from s00b_audit import file_fingerprint, length_consistency, write_json, zero_rows
from s00c_text_zero import diagnose_aligned_split
from s00c_vision import diagnose_length_boundary
from stage_handoff import BRANCH, ORIGIN, spec_scalar

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF"
S00B_RUN = "20260924-001338-S00B-fc277357"
SPLITS = ("train", "valid")
VERSIONS = ("aligned", "unaligned")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=True)
    return result.stdout.strip()


def checked_workspace() -> str:
    if git("remote", "get-url", "origin") != ORIGIN or git("branch", "--show-current") != BRANCH:
        raise RuntimeError("Official origin or branch mismatch")
    local = git("rev-parse", "HEAD")
    remote = git("ls-remote", "--heads", "origin", BRANCH).split()
    if not remote or remote[0] != local:
        raise RuntimeError("Local and remote HEAD differ")
    spec = (ROOT / "TASK_SPEC.md").read_text(encoding="utf-8")
    required = {"task_id": TASK_ID, "status": "ACTIVE", "research_authorized": "true",
                "next_stage_authorized": "false", "stage_type": "targeted_data_audit"}
    if any(spec_scalar(spec, key) != value for key, value in required.items()):
        raise RuntimeError("S00C task specification not active")
    return local


def trusted_sources(config_path: Path) -> dict[str, Path]:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if set(config) != {"data_root", "trusted_competition_pickle"} or config["trusted_competition_pickle"] is not True:
        raise RuntimeError("Trusted local official data configuration is required")
    root = Path(config["data_root"])
    if not root.is_dir():
        raise RuntimeError("Official local data root unavailable")
    folder = root / "附件2-数据集特征文件"
    paths = {version: folder / f"{version}_50.pkl" for version in VERSIONS}
    if any(not path.is_file() for path in paths.values()):
        raise RuntimeError("Required Attachment 2 official feature file unavailable")
    return paths


def load_baseline() -> dict:
    audit = ROOT / "reports" / "data_audit"
    stage = ROOT / "reports" / "runs" / S00B_RUN
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    baseline = {"source": read(audit / "source_mutation_check.json"),
                "schema_aligned": read(audit / "schema_aligned.json"),
                "schema_unaligned": read(audit / "schema_unaligned.json"),
                "length": read(audit / "length_consistency_unaligned.json"),
                "aligned_position": read(audit / "aligned_positional_diagnostics.json"),
                "bert": read(audit / "text_bert_diagnostics.json"),
                "run": read(stage / "RUN.json"), "gate": read(stage / "GATE.json")}
    if baseline["run"]["run_id"] != S00B_RUN or baseline["gate"]["passed"] is not True:
        raise RuntimeError("S00B run or Gate evidence inconsistent")
    for version in VERSIONS:
        if baseline[f"schema_{version}"]["total_sample_count"] != 4850:
            raise RuntimeError("S00B schema count inconsistent")
        if baseline["source"]["unchanged"][version] is not True:
            raise RuntimeError("S00B source mutation evidence inconsistent")
    return baseline


def match_sources(before: dict, baseline: dict) -> None:
    for version in VERSIONS:
        if before[version] != baseline["source"]["after"][version]:
            raise RuntimeError("Official source fingerprint differs from S00B; stop before deserialization")


def compare_observed(observed: dict, baseline: dict) -> dict:
    checks = {}
    for version in VERSIONS:
        for split in SPLITS:
            key = f"{version}_{split}_sample_count"
            expected = baseline[f"schema_{version}"]["splits"][split]["sample_count"]
            checks[key] = {"s00b": expected, "s00c": observed["counts"][version][split],
                           "equal": expected == observed["counts"][version][split]}
    for split in SPLITS:
        for mod in ("audio", "vision"):
            for field in ("nonzero_after_length_count", "zero_inside_declared_length_count"):
                key = f"unaligned_{split}_{mod}_{field}"
                expected = baseline["length"][split][mod][field]
                actual = observed["length"][split][mod][field]
                checks[key] = {"s00b": expected, "s00c": actual, "equal": expected == actual}
        for field, actual in (("candidate_active_position_count", observed["aligned"][split]["active"]),
                              ("text_inactive_nonzero", observed["aligned"][split]["inactive_text_nonzero"])):
            expected = (baseline["aligned_position"][split]["text"]["inactive_nonzero"]
                        if field == "text_inactive_nonzero" else
                        baseline["aligned_position"][split][field])
            key = f"aligned_{split}_{field}"
            checks[key] = {"s00b": expected, "s00c": actual, "equal": expected == actual}
    return {"source": "S00B published aggregate reports and independent S00C recomputation",
            "checks": checks, "all_equal": all(item["equal"] for item in checks.values()),
            "differences": [key for key, item in checks.items() if not item["equal"]]}


def audit_run(run_id: str | None = None, config_path: Path = ROOT / "configs" / "paths.local.json") -> dict:
    activation = checked_workspace()
    baseline = load_baseline()
    sources = trusted_sources(config_path)
    before = {version: file_fingerprint(path) for version, path in sources.items()}
    match_sources(before, baseline)
    audit = ROOT / "reports" / "data_audit"
    outputs = {name: audit / name for name in (
        "s00c_vision_length_boundary.json", "s00c_text_mask_diagnostics.json",
        "s00c_zero_mechanism_matrix.json", "s00c_s00b_reconciliation.json",
        "s00c_source_mutation_check.json")}
    if any(path.exists() for path in outputs.values()):
        raise RuntimeError("S00C output already exists; no overwrite allowed")
    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S") + "-S00C-" + activation[:8]
    run = ROOT / "reports" / "runs" / run_id
    run.mkdir(parents=True, exist_ok=False)
    public, private = run / "public", run / "private"
    public.mkdir()
    private.mkdir()
    write_json(public / "SOURCE_HASH_BEFORE.json", before)
    observed = {"counts": {}, "length": {}, "aligned": {}}
    text_report, zero_report, vision_report = {}, {"aligned": {}, "unaligned": {}}, {}
    for version in VERSIONS:
        with sources[version].open("rb") as stream:
            data = pickle.load(stream)
        observed["counts"][version] = {}
        if version == "unaligned":
            vision_report[version] = {}
        for split in SPLITS:
            item = data[split]
            observed["counts"][version][split] = len(item["text"])
            if version == "aligned":
                text_public, zero_public = diagnose_aligned_split(
                    item["text_bert"], item["text"], item["audio"], item["vision"])
                text_report[split] = text_public
                zero_report[version][split] = zero_public
                candidate = np.asarray(item["text_bert"])[:, 1, :] == 1
                observed["aligned"][split] = {
                    "active": int(np.count_nonzero(candidate)),
                    "inactive_text_nonzero": int(np.count_nonzero(~candidate & ~zero_rows(item["text"])))}
            else:
                vision_report[version][split] = {}
                observed["length"][split] = {}
                zero_report[version][split] = {}
                for mod in ("audio", "vision"):
                    values = np.asarray(item[mod])
                    lengths = np.asarray(item[f"{mod}_lengths"])
                    aggregate, sample_rows = diagnose_length_boundary(values, lengths, split=split, modality=mod)
                    vision_report[version][split][mod] = aggregate
                    zero_report[version][split][mod] = {
                        "stored_zero_structure": aggregate["stored_zero_structure"],
                        "inside": aggregate["inside"],
                        "after_nonzero_row_count": aggregate["after"]["nonzero_row_count"],
                    }
                    observed["length"][split][mod] = length_consistency(zero_rows(values), lengths)
                    write_json(private / f"{split}_{mod}_sample_diagnostics.json", sample_rows)
                    del values, lengths, aggregate, sample_rows
            del item
        del data
        gc.collect()
    after = {version: file_fingerprint(path) for version, path in sources.items()}
    unchanged = {version: before[version] == after[version] for version in VERSIONS}
    write_json(public / "SOURCE_HASH_AFTER.json", after)
    mutation = {"before": before, "after": after, "unchanged": unchanged,
                "CRITICAL_DATA_MUTATION": not all(unchanged.values())}
    write_json(outputs["s00c_source_mutation_check.json"], mutation)
    reconciliation = compare_observed(observed, baseline)
    write_json(outputs["s00c_s00b_reconciliation.json"], reconciliation)
    write_json(outputs["s00c_vision_length_boundary.json"], vision_report)
    write_json(outputs["s00c_text_mask_diagnostics.json"], text_report)
    write_json(outputs["s00c_zero_mechanism_matrix.json"], zero_report)
    status = "SUCCESS" if all(unchanged.values()) and reconciliation["all_equal"] else "FAILED"
    run_record = {
        "task_id": TASK_ID, "run_id": run_id, "status": status, "data_kind": "real_official_local",
        "stage_activation_commit": activation, "baseline_s00b_run_id": S00B_RUN,
        "command": f"python tools/s00c_run.py --run-id {run_id}",
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "source_files": [sources[version].name for version in VERSIONS],
        "source_unchanged": unchanged, "s00b_reconciliation_all_equal": reconciliation["all_equal"],
        "split_usage": {"train": "targeted numeric diagnostics", "valid": "targeted numeric diagnostics",
                        "test": "quarantined; no S00C feature or label access"},
        "sample_counts": observed["counts"],
        "attachment3_content_inspected": False, "attachment4_feature_content_inspected": False,
        "attachment4_video_content_inspected": False,
        "TEST_LABEL_DISTRIBUTION_QUARANTINED": True, "NEXT_STAGE_NOT_AUTHORIZED": True,
    }
    write_json(run / "RUN.json", run_record)
    if status != "SUCCESS":
        raise RuntimeError("S00C source mutation or S00B reconciliation failed; publication prohibited")
    return {"run_id": run_id, "status": status, "sample_counts": observed["counts"],
            "source_unchanged": unchanged, "s00b_reconciliation_all_equal": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "paths.local.json")
    args = parser.parse_args()
    print(json.dumps(audit_run(args.run_id, args.config), ensure_ascii=False))


if __name__ == "__main__":
    main()
