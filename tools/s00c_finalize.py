"""Run S00C engineering tests and build the 12-item prepublication Gate."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from mosei_flow import forbidden_path, sha256, write_json
from s00c_run import ROOT, TASK_ID, checked_workspace
from stage_handoff import scan_public, validate_acceptance, validate_run

STAGE = "S00C"
AUDIT = Path("reports/data_audit")
REPORTS = [f"{AUDIT.as_posix()}/{name}" for name in (
    "s00c_vision_length_boundary.json", "s00c_text_mask_diagnostics.json",
    "s00c_zero_mechanism_matrix.json", "s00c_s00b_reconciliation.json",
    "s00c_source_mutation_check.json")]
CODE = ["tools/s00c_run.py", "tools/s00c_vision.py", "tools/s00c_text_zero.py",
        "tools/s00c_finalize.py", "tools/stage_handoff.py"]
TESTS = ["tests/test_stage_s00c_run.py", "tests/test_s00c_vision.py",
         "tests/test_s00c_text_zero.py", "tests/test_stage_s00c_finalize.py",
         "tests/test_stage_handoff.py"]
BASELINE = ["docs/DATA_CONTRACT_EVIDENCE.md", "reports/data_audit/DATA_AUDIT.md",
            "reports/data_audit/length_consistency_unaligned.json",
            "reports/data_audit/aligned_positional_diagnostics.json",
            "docs/HANDOFF_WORKFLOW.md"]


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def public_files(run_id: str) -> list[str]:
    return ["docs/S00C_SUPPORT_EVIDENCE.md", *REPORTS, *CODE, *TESTS, *BASELINE,
            f"reports/runs/{run_id}/public/SOURCE_HASH_BEFORE.json",
            f"reports/runs/{run_id}/public/SOURCE_HASH_AFTER.json"]


def ensure_complete_manifest(manifest: dict, run_id: str) -> None:
    required = set(public_files(run_id))
    if (manifest.get("stage") != STAGE or manifest.get("task_id") != TASK_ID or
            manifest.get("run_id") != run_id or
            not isinstance(manifest.get("public_files"), list) or
            set(manifest["public_files"]) != required or
            len(manifest["public_files"]) != len(required)):
        raise ValueError("S00C handoff manifest does not list the exact required public files")


def test_command(run: Path) -> dict:
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    private = run / "private"
    private.mkdir(exist_ok=True)
    (private / "TEST_LOG.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    passed = re.search(r"\b(\d+) passed\b", result.stdout)
    failed = re.search(r"\b(\d+) failed\b", result.stdout)
    record = {"command": "python -m pytest -q tests", "exit_code": result.returncode,
              "passed": int(passed.group(1)) if passed else 0,
              "failed": int(failed.group(1)) if failed else 0,
              "result_summary": result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "no summary"}
    write_json(run / "TEST_RESULTS.json", record)
    return record


def review_text(run_id: str, run: dict, tests: dict, gate_count: int | None) -> str:
    vision = read(REPORTS[0])["unaligned"]
    text = read(REPORTS[1])
    zero = read(REPORTS[2])
    prior = read("state/LATEST_RUN.json")
    return f"""# Current Review — S00C support boundary evidence

task_id: `{TASK_ID}`
run_id: `{run_id}`
status: `{'READY_FOR_AUTOMATED_HANDOFF' if gate_count is not None else 'PENDING_GATE_VALIDATION'}`
repository: `BiLiangXin/jingsai`
branch: `codex/mosei-auto`
baseline_commit: `{run['stage_activation_commit']}`
previous_stage_implementation_commit: `{prior['implementation_commit']}`
implementation_commit: `PENDING_PUBLICATION`
metadata_commit: `PENDING_PUBLICATION`
release_url: `PENDING_PUBLICATION`
release_tag: `PENDING_PUBLICATION`
review_asset: `PENDING_PUBLICATION`

## Real run and source integrity

VERIFIED: The S00C run read the two trusted official Attachment 2 feature PKLs sequentially and calculated only train/valid numerical diagnostics. Both before/after source fingerprints match; the current fingerprints also match the S00B published source records. No original file was modified. Test was not indexed for new diagnostics. Attachment 3/4 content was not opened. See `reports/runs/{run_id}/RUN.json`, public source hash records and `reports/data_audit/s00c_source_mutation_check.json`.

An earlier local attempt with a different run ID stopped at a report-layer lookup error after source integrity verification. Its evidence remains in its ignored private directory; it was never published. The corrected run `{run_id}` completed and independently reconciled 16 S00B facts.

The first automatic handoff invocation stopped in pre-Git validation because its porcelain status parser dropped a significant leading space. No Git write or Release occurred in that attempt. The parser and synthetic regression test were corrected before retrying; the failed attempt record remains in this run's ignored private directory.

## S00B baseline reproduction

VERIFIED: Both feature versions again have train/valid 3,395/728 samples. Unaligned audio has zero nonzero rows after declared length; vision has {vision['train']['vision']['after']['nonzero_row_count']:,}/{vision['valid']['vision']['after']['nonzero_row_count']:,}. Train vision has 30 zero rows inside declared length, all from 30 whole-zero sequences with declared length 1. Aligned candidate-active positions and inactive-nonzero continuous text counts also match. All 16 reconciliation checks are equal. See `reports/data_audit/s00c_s00b_reconciliation.json`.

## Targeted boundary results

VERIFIED: After-boundary vision nonzero rows occur in {vision['train']['vision']['after']['affected_sample_count']}/3,395 train samples and {vision['valid']['vision']['after']['affected_sample_count']}/728 valid samples. No affected sample has a single nonzero row immediately at the declared boundary. The first nonzero offsets and extension lengths are heterogeneous, and median nonzero-row norms inside versus after are of similar magnitude. Audio supplies a contrasting zero-after-length pattern. The complete aggregate distributions and length bins are in `reports/data_audit/s00c_vision_length_boundary.json`.

INFERRED: The observed vision pattern does not fit a universal off-by-one or single fixed offset. UNKNOWN: whether post-length vision values are genuine observations, extraction artifacts or unusable values. A producer definition or independently verified feature-to-source alignment is needed. Official lengths were not replaced or reinterpreted as a final support rule.

## Aligned text and structural zeros

VERIFIED: Channel 1 of aligned `text_bert` is binary and continuous-prefix in every train/valid sample. Candidate-inactive continuous `text` has {text['train']['text_features']['inactive']['nonzero_row_count']:,}/{text['valid']['text_features']['inactive']['nonzero_row_count']:,} nonzero rows. Tail repetition and row-norm distributions are in `reports/data_audit/s00c_text_mask_diagnostics.json`. INFERRED: channel 1 remains an attention-mask candidate only; it does not define final padding for continuous text.

VERIFIED: Exact-zero runs differ by modality and interface. Aligned vision has {zero['aligned']['train']['vision']['all_zero_sample_count']}/{zero['aligned']['valid']['vision']['all_zero_sample_count']} whole-zero samples; unaligned vision has {vision['train']['vision']['whole_sequence_zero']['sample_count']}/{vision['valid']['vision']['whole_sequence_zero']['sample_count']}. Prefix, suffix, internal, multiple internal, candidate-active overlap and official-length boundary cross-statistics are in `reports/data_audit/s00c_zero_mechanism_matrix.json`. UNKNOWN: these zero structures do not establish padding, missingness or invalid observation.

## Tests, Gate and publication

Actual engineering test command: `{tests['command']}` — {tests['passed']} passed, {tests['failed']} failed, exit code {tests['exit_code']}. Synthetic tests are separate from the real-data run. S00C Gate: {f'{gate_count}/{gate_count} PASS, with no FAIL, SKIPPED or BLOCKED' if gate_count is not None else 'PENDING_FINAL_VALIDATION'}; see `reports/runs/{run_id}/GATE.json`. The public-file safety scan and Git raw-data protection check are recorded by the Gate. Release fields above are populated only after remote target, asset size and downloaded SHA256 verification.

## Research review boundary

Candidate data-contract meanings, alternatives, limits and independent evidence requirements are in `docs/S00C_SUPPORT_EVIDENCE.md`. Main Research Chat must decide whether and how to interpret vision lengths, text candidate mask and structural zeros. The existing `DECISIONS.md` remains unchanged. No aligned/unaligned final choice, missing/padding rule, model or S01 stage is approved.

`PROPOSED_RESEARCH_CHANGE: NONE`.

`PENDING_RESEARCH_REVIEW`
`NEXT_STAGE_NOT_AUTHORIZED`
`STOPPED_AFTER_S00C`
"""


def gate_item(code: str, passed: bool, evidence: list[str], detail: str) -> dict:
    return {"id": code, "status": "PASS" if passed else "FAIL", "evidence": evidence,
            "detail": detail}


def finalize(run_id: str) -> dict:
    checked_workspace()
    run_dir = ROOT / "reports" / "runs" / run_id
    run = read(f"reports/runs/{run_id}/RUN.json")
    if run.get("task_id") != TASK_ID or run.get("status") != "SUCCESS":
        raise RuntimeError("A successful real S00C run is required")
    tests = test_command(run_dir)
    docs_path = ROOT / "docs" / "S00C_SUPPORT_EVIDENCE.md"
    doc = docs_path.read_text(encoding="utf-8")
    review = ROOT / "CHATGPT_REVIEW.md"
    review.write_text(review_text(run_id, run, tests, None), encoding="utf-8")
    files = public_files(run_id)
    manifest_relative = f"reports/runs/{run_id}/public/HANDOFF_INPUTS.json"
    manifest = {"stage": STAGE, "task_id": TASK_ID, "run_id": run_id, "public_files": files}
    ensure_complete_manifest(manifest, run_id)
    write_json(ROOT / manifest_relative, manifest)
    evidence_paths = [*files, "CHATGPT_REVIEW.md", f"reports/runs/{run_id}/RUN.json",
                      f"reports/runs/{run_id}/TEST_RESULTS.json", manifest_relative]
    acceptance = {"stage": STAGE, "data_kind": "real_official_local",
                  "evidence": [{"requirement": Path(path).name, "path": path,
                                "sha256": sha256(ROOT / path)} for path in evidence_paths]}
    acceptance_relative = "reports/stages/S00C/acceptance.json"
    write_json(ROOT / acceptance_relative, acceptance)
    validate_acceptance(ROOT / acceptance_relative, STAGE)
    vision = read(REPORTS[0])["unaligned"]
    text = read(REPORTS[1])
    zero = read(REPORTS[2])
    reconciliation = read(REPORTS[3])
    mutation = read(REPORTS[4])
    safety = {path: issues for path in evidence_paths + [acceptance_relative]
              if (issues := scan_public(ROOT / path))}
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout.split("\0")
    raw_tracked = [path for path in tracked if path and forbidden_path(path)]
    quarantine = (run["split_usage"]["test"].startswith("quarantined") and
                  run["TEST_LABEL_DISTRIBUTION_QUARANTINED"] is True and
                  run["attachment3_content_inspected"] is False and
                  run["attachment4_feature_content_inspected"] is False and
                  run["attachment4_video_content_inspected"] is False)
    items = [
        gate_item("C01", True, ["TASK_SPEC.md", f"reports/runs/{run_id}/RUN.json"], "Official workspace, branch and active S00C specification verified"),
        gate_item("C02", reconciliation["all_equal"] and len(reconciliation["checks"]) >= 16,
                  [REPORTS[3]], "S00B baseline independently reconciled"),
        gate_item("C03", all(mutation["unchanged"].values()) and not mutation["CRITICAL_DATA_MUTATION"],
                  [REPORTS[4], f"reports/runs/{run_id}/public/SOURCE_HASH_BEFORE.json",
                   f"reports/runs/{run_id}/public/SOURCE_HASH_AFTER.json"], "Trusted official sources unchanged"),
        gate_item("C04", quarantine, [f"reports/runs/{run_id}/RUN.json", TESTS[0]],
                  "Train/valid only; test and Attachment 3/4 content quarantined"),
        gate_item("C05", all(vision[s]["vision"]["sample_count"] == run["sample_counts"]["unaligned"][s] and
                              all(key in vision[s]["vision"] for key in
                                  ("stored_zero_structure", "inside", "after", "length_bins", "row_norms")) and
                              vision[s]["vision"]["after"]["affected_sample_count"] <= vision[s]["vision"]["sample_count"]
                              for s in ("train", "valid")), [REPORTS[0]], "Vision boundary diagnostics complete"),
        gate_item("C06", all(vision[s]["audio"]["sample_count"] == run["sample_counts"]["unaligned"][s] and
                              all(key in vision[s]["audio"] for key in
                                  ("stored_zero_structure", "inside", "after", "length_bins", "row_norms"))
                              for s in ("train", "valid")), [REPORTS[0]], "Audio length control complete"),
        gate_item("C07", all(text[s]["candidate_mask"]["status"] in {"INFERRED", "UNKNOWN"} and
                              all(key in text[s] for key in ("candidate_mask", "text_features", "mask_zero_cross"))
                              for s in ("train", "valid")), [REPORTS[1]], "Aligned text candidate-mask diagnosis complete"),
        gate_item("C08", all(mod in zero[version][split] for version in ("aligned", "unaligned")
                              for split in ("train", "valid") for mod in ("audio", "vision")),
                  [REPORTS[2]], "Separate modality zero-run and cross-boundary evidence complete"),
        gate_item("C09", all(f"## {label}" in doc for label in
                              ("VERIFIED", "SPECIFIED", "INFERRED", "HYPOTHESIS", "UNKNOWN")) and
                  "PROPOSED_RESEARCH_CHANGE: NONE" in doc, ["docs/S00C_SUPPORT_EVIDENCE.md"],
                  "Observed facts, inferences, hypotheses and unknowns separated"),
        gate_item("C10", tests["exit_code"] == 0 and tests["failed"] == 0 and tests["passed"] > 0,
                  [f"reports/runs/{run_id}/TEST_RESULTS.json"], "Actual engineering suite passed"),
        gate_item("C11", not safety and not raw_tracked, [manifest_relative, "CHATGPT_REVIEW.md"],
                  "Selected public files scanned; no forbidden tracked path"),
        gate_item("C12", all((ROOT / path).is_file() for path in evidence_paths) and
                  len(acceptance["evidence"]) == len(evidence_paths),
                  [acceptance_relative, manifest_relative], "Run, report, acceptance and handoff inventory complete"),
    ]
    counts = {status: sum(item["status"] == status for item in items)
              for status in ("PASS", "FAIL", "SKIPPED", "BLOCKED")}
    gate = {"task_id": TASK_ID, "run_id": run_id, "status": "PASS" if counts["PASS"] == 12 else "FAIL",
            "passed": counts["PASS"] == 12, "summary": counts, "items": items}
    write_json(run_dir / "GATE.json", gate)
    if safety or raw_tracked or scan_public(run_dir / "GATE.json") or not gate["passed"]:
        raise RuntimeError(f"S00C Gate failed: {counts}; publication prohibited")
    validate_run(manifest)
    review.write_text(review_text(run_id, run, tests, 12), encoding="utf-8")
    for item in acceptance["evidence"]:
        if item["path"] == "CHATGPT_REVIEW.md":
            item["sha256"] = sha256(review)
    write_json(ROOT / acceptance_relative, acceptance)
    validate_acceptance(ROOT / acceptance_relative, STAGE)
    validate_run(manifest)
    if scan_public(review) or scan_public(ROOT / acceptance_relative):
        raise RuntimeError("Final S00C review or acceptance safety scan failed")
    return {"run_id": run_id, "tests": tests, "gate": counts,
            "manifest_file_count": len(files), "public_scan_findings": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.run_id), ensure_ascii=False))


if __name__ == "__main__":
    main()
