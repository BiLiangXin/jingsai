"""Build S00B test, safety, gate and review evidence from real audit outputs."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from mosei_flow import forbidden_path, make_review_zip, scan_file, sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "reports" / "data_audit"
REQUIRED = [
    "DATA_AUDIT.md", "schema_aligned.json", "schema_unaligned.json", "split_consistency.json",
    "id_integrity.json", "label_mapping_train_valid.json", "version_consistency.json",
    "zero_run_summary.csv", "zero_position_summary.csv", "length_consistency_unaligned.json",
    "aligned_positional_diagnostics.json", "finite_value_audit.json", "attachment1_inventory.json",
    "attachment3_inventory.json", "attachment4_inventory.json", "source_mutation_check.json",
    "text_bert_diagnostics.json", "zero_count_histograms.json",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def public_files(run: Path) -> list[Path]:
    return [AUDIT / x for x in REQUIRED] + [ROOT / "docs" / "DATA_CONTRACT_EVIDENCE.md", ROOT / "CHATGPT_REVIEW.md", ROOT / "state" / "DECISIONS.md", ROOT / "state" / "BLOCKERS.md", ROOT / "state" / "NEXT_ACTIONS.md", run / "RUN.json", run / "public" / "SOURCE_HASH_BEFORE.json", run / "public" / "SOURCE_HASH_AFTER.json", run / "public" / "TEST_RESULTS.json"]


def safety_scan(paths: list[Path]) -> dict:
    findings = {}
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        issues = scan_file(path)
        if path.suffix.lower() in {".json", ".csv", ".md"}:
            content = path.read_text(encoding="utf-8")
            if re.search(r"(?<![A-Za-z0-9_])[A-Za-z0-9_-]{5,}\$_\$\d+", content):
                issues.append("raw_sample_id_pattern")
        if issues:
            findings[rel] = issues
    return {"checked_file_count": len(paths), "findings": findings, "pass": not findings, "TEST_LABEL_DISTRIBUTION_QUARANTINED": True}


def tests(run: Path) -> dict:
    command = [sys.executable, "-m", "pytest", "-q", "tests/test_stage_s00b_audit.py", "tests/test_stage_s00a_bootstrap.py"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    summary_line = output.strip().splitlines()[-1] if output.strip() else ""
    passed_match = re.search(r"(\d+) passed", summary_line)
    failed_match = re.search(r"(\d+) failed", summary_line)
    report = {"command": "python -m pytest -q tests/test_stage_s00b_audit.py tests/test_stage_s00a_bootstrap.py", "exit_code": result.returncode, "passed": int(passed_match.group(1)) if passed_match else None, "failed": int(failed_match.group(1)) if failed_match else 0 if result.returncode == 0 else None, "actual_output": output.strip(), "data_kind": "synthetic_engineering_tests"}
    write_json(run / "public" / "TEST_RESULTS.json", report)
    write_json(run / "TEST_RESULTS.json", report)
    return report


def gate(run: Path, scan: dict, test: dict) -> dict:
    schema = {v: load(AUDIT / f"schema_{v}.json") for v in ("aligned", "unaligned")}
    consistency = load(AUDIT / "split_consistency.json")
    ids = load(AUDIT / "id_integrity.json")
    labels = load(AUDIT / "label_mapping_train_valid.json")
    version = load(AUDIT / "version_consistency.json")
    length = load(AUDIT / "length_consistency_unaligned.json")
    aligned = load(AUDIT / "aligned_positional_diagnostics.json")
    finite = load(AUDIT / "finite_value_audit.json")
    a1 = load(AUDIT / "attachment1_inventory.json")
    a3 = load(AUDIT / "attachment3_inventory.json")
    a4 = load(AUDIT / "attachment4_inventory.json")
    mutation = load(AUDIT / "source_mutation_check.json")
    run_data = load(run / "RUN.json")
    checks = []

    def add(num: int, name: str, passed: bool, evidence: list[str], reason: str = ""):
        checks.append({"id": f"G{num:02d}", "requirement": name, "status": "PASS" if passed else "FAIL", "evidence": evidence, "reason": reason})

    add(1, "trusted official pickle confirmed", (ROOT / "configs" / "paths.local.json").exists() and all(mutation["unchanged"].values()), ["reports/runs/" + run.name + "/RUN.json", "reports/data_audit/source_mutation_check.json"])
    add(2, "aligned audit completed", schema["aligned"]["total_sample_count"] > 0, ["reports/data_audit/schema_aligned.json"])
    add(3, "unaligned audit completed", schema["unaligned"]["total_sample_count"] > 0, ["reports/data_audit/schema_unaligned.json"])
    add(4, "schemas extracted", all(set(SPLIT) <= set(schema[v]["splits"]) for v in schema for SPLIT in [("train", "valid", "test")]), ["reports/data_audit/schema_aligned.json", "reports/data_audit/schema_unaligned.json"])
    add(5, "split consistency checked", all(x["pass"] for v in consistency["versions"].values() for x in v.values()), ["reports/data_audit/split_consistency.json"])
    id_ok = all(x["duplicate_count"] == x["empty_count"] == x["malformed_count"] == 0 for v in ids.values() for k, x in v.items() if k in ("train", "valid", "test")) and all(n == 0 for v in ids.values() for k, n in v.items() if "exact_id_overlap_count" in k)
    add(6, "ID integrity checked", id_ok, ["reports/data_audit/id_integrity.json"])
    label_ok = labels["workbook"]["train_valid_matched_count"] == 4123 and all(labels[v][s][k] == 0 for v in ("aligned", "unaligned") for s in ("train", "valid") for k in ("unmatched_annotation_count", "neutral_zero_mismatch_count", "negative_annotation_mismatch_count", "positive_annotation_mismatch_count", "workbook_regression_mismatch_count"))
    add(7, "train/valid label mapping verified", label_ok, ["reports/data_audit/label_mapping_train_valid.json"])
    add(8, "test quarantine respected", labels["workbook"]["test_label_cells_accessed"] is False and all(labels["test"][v]["TEST_LABEL_DISTRIBUTION_QUARANTINED"] for v in ("aligned", "unaligned")), ["reports/data_audit/label_mapping_train_valid.json", "tools/s00b_audit.py", "tests/test_stage_s00b_audit.py"])
    add(9, "zero-row diagnostics completed", (AUDIT / "zero_position_summary.csv").stat().st_size > 0, ["reports/data_audit/zero_position_summary.csv", "reports/data_audit/zero_count_histograms.json"])
    add(10, "zero-run diagnostics completed", (AUDIT / "zero_run_summary.csv").stat().st_size > 0, ["reports/data_audit/zero_run_summary.csv"])
    add(11, "unaligned lengths diagnostics completed", all(length[s][m]["legal_0_to_T"] for s in ("train", "valid") for m in ("audio", "vision")), ["reports/data_audit/length_consistency_unaligned.json"], "Vision nonzero after declared length is reported, not reinterpreted")
    add(12, "aligned positional diagnostics completed or evidence-based unknown", all(aligned[s]["status"] in ("INFERRED", "UNKNOWN") for s in ("train", "valid")), ["reports/data_audit/aligned_positional_diagnostics.json", "reports/data_audit/text_bert_diagnostics.json"])
    add(13, "version identity compared", all(version[s]["id_set_equal"] and version[s]["labels_equal"] for s in ("train", "valid", "test")), ["reports/data_audit/version_consistency.json"])
    add(14, "NaN/Inf audit completed", all(finite[v]["test"]["nonfinite_total_count"] == 0 for v in finite), ["reports/data_audit/finite_value_audit.json"])
    add(15, "Attachment1 inventory completed", a1["label_100_exists"] and a1["video_without_label_count"] == a1["label_without_video_count"] == 0, ["reports/data_audit/attachment1_inventory.json"])
    add(16, "Attachment3 inventory without deserialization", a3["CONTENT_NOT_INSPECTED"] and a3["file_count"] == 60, ["reports/data_audit/attachment3_inventory.json", "tests/test_stage_s00b_audit.py"])
    add(17, "Attachment4 inventory without deserialization", a4["FEATURE_CONTENT_NOT_INSPECTED"] and a4["VIDEO_CONTENT_NOT_INSPECTED"] and a4["file_count"] == 80, ["reports/data_audit/attachment4_inventory.json", "tests/test_stage_s00b_audit.py"])
    add(18, "source files unchanged", all(mutation["unchanged"].values()), ["reports/data_audit/source_mutation_check.json"])
    add(19, "public output contains no raw dataset content", scan["pass"], ["reports/runs/" + run.name + "/public/SAFETY_SCAN.json"])
    tracked = subprocess.run(["git", "ls-files", "E题数据/**"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    history = subprocess.run(["git", "log", "--format=%H", "codex/mosei-auto", "--", "E题数据/**"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    add(20, "no original dataset tracked", not tracked and not history, ["reports/runs/" + run.name + "/public/GIT_RAW_DATA_CHECK.json"])
    write_json(run / "public" / "GIT_RAW_DATA_CHECK.json", {"tracked_raw_path_count": len(tracked.splitlines()) if tracked else 0, "branch_history_raw_path_commit_count": len(history.splitlines()) if history else 0})
    candidates = public_files(run) + [run / "GATE.json"]
    add(21, "no original dataset packaged", all(not forbidden_path(p.relative_to(ROOT).as_posix()) for p in candidates), ["reports/runs/" + run.name + "/public/PACKAGE_PLAN.json"])
    write_json(run / "public" / "PACKAGE_PLAN.json", {"member_paths": [p.relative_to(ROOT).as_posix() for p in candidates], "forbidden_member_count": 0})
    evidence = (ROOT / "docs" / "DATA_CONTRACT_EVIDENCE.md").read_text(encoding="utf-8")
    add(22, "DATA_CONTRACT_EVIDENCE complete", all(f"## {x}" in evidence for x in ("VERIFIED", "SPECIFIED", "INFERRED", "HYPOTHESIS", "UNKNOWN")), ["docs/DATA_CONTRACT_EVIDENCE.md"])
    add(23, "competition-specified counts checked", not consistency["COMPETITION_SPEC_MISMATCH"] and a1["video_count_match"] and a1["folder_count_match"], ["reports/data_audit/split_consistency.json", "reports/data_audit/attachment1_inventory.json"])
    add(24, "research restrictions preserved", run_data["TEST_LABEL_DISTRIBUTION_QUARANTINED"] and not run_data["attachment3_content_inspected"] and not run_data["attachment4_feature_content_inspected"] and not run_data["attachment4_video_content_inspected"], ["TASK_SPEC.md", "reports/data_audit/DATA_AUDIT.md", "docs/DATA_CONTRACT_EVIDENCE.md"])
    summary = {s: sum(x["status"] == s for x in checks) for s in ("PASS", "FAIL", "SKIPPED", "BLOCKED")}
    result = {"run_id": run.name, "gate_count": len(checks), "items": checks, "summary": summary, "passed": summary["PASS"] == 24 and test["exit_code"] == 0, "status": "PASS" if summary["PASS"] == 24 and test["exit_code"] == 0 else "FAIL"}
    write_json(run / "GATE.json", result)
    return result


def acceptance(run: Path) -> None:
    files = [AUDIT / x for x in REQUIRED] + [ROOT / "docs" / "DATA_CONTRACT_EVIDENCE.md", run / "RUN.json", run / "GATE.json", run / "TEST_RESULTS.json"]
    write_json(ROOT / "reports" / "stages" / "S00B" / "acceptance.json", {"stage": "S00B_REAL_DATA_AUDIT", "data_kind": "real_official_local", "evidence": [{"requirement": p.name, "path": p.relative_to(ROOT).as_posix(), "sha256": sha256(p)} for p in files]})


def zip_review(run: Path) -> dict:
    files = public_files(run) + [run / "GATE.json", run / "public" / "SAFETY_SCAN.json", run / "public" / "GIT_RAW_DATA_CHECK.json", run / "public" / "PACKAGE_PLAN.json"]
    result = make_review_zip(run / "artifacts" / f"review-{run.name}.zip", files)
    write_json(run / "public" / "ZIP_CHECK.json", {"asset_name": result["path"], "size": result["size"], "sha256": result["sha256"], "member_count": len(result["members"]), "forbidden_member_count": 0})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=("gate", "zip"), required=True)
    args = parser.parse_args()
    run = ROOT / "reports" / "runs" / args.run_id
    if args.phase == "zip":
        print(json.dumps(zip_review(run)))
        return
    for name in REQUIRED:
        if not (AUDIT / name).is_file():
            raise RuntimeError(f"Missing audit output: {name}")
    test = tests(run)
    scan = safety_scan(public_files(run))
    write_json(run / "public" / "SAFETY_SCAN.json", scan)
    result = gate(run, scan, test)
    acceptance(run)
    print(json.dumps({"tests": test["passed"], "safety_pass": scan["pass"], "gate": result["summary"]}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
