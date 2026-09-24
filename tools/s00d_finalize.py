"""Run complete engineering tests and construct the 18-item S00D Gate."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from mosei_flow import sha256, write_json
from s00d_contract_run import ROOT, TASK_ID, checked_workspace, prior_evidence
from stage_handoff import scan_public, validate_acceptance, validate_run

STAGE = "S00D"
REPORT_NAMES = ("contract_summary.json", "mask_summary.json", "label_contract.json",
                "normalization_contract.json", "loader_contract.json", "source_mutation_check.json")
REPORTS = [f"reports/data_contract/{name}" for name in REPORT_NAMES]
CODE = ["src/mosei/__init__.py", "src/mosei/data/__init__.py", "src/mosei/data/masks.py",
        "src/mosei/data/data_contract.py", "src/mosei/data/dataset.py",
        "src/mosei/data/normalization.py", "src/mosei/data/pooling.py",
        "tools/s00d_contract_run.py", "tools/s00d_finalize.py", "tools/stage_handoff.py"]
TEST_FILES = ["tests/test_stage_s00d_contract.py", "tests/test_stage_handoff.py"]
DEPENDENCIES = ["docs/S00C_SUPPORT_EVIDENCE.md", "reports/data_audit/s00c_source_mutation_check.json"]


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def public_files(run_id: str) -> list[str]:
    return ["docs/S00D_DATA_CONTRACT.md", *REPORTS, *CODE, *TEST_FILES, *DEPENDENCIES,
            f"reports/runs/{run_id}/public/SOURCE_HASH_BEFORE.json",
            f"reports/runs/{run_id}/public/SOURCE_HASH_AFTER.json"]


def full_tests(run_id: str) -> dict:
    def invoke(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "pytest", *arguments], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def count(output: str, label: str) -> int:
        match = re.search(rf"\b(\d+) {label}\b", output)
        return int(match.group(1)) if match else 0

    full_collection = invoke("--collect-only", "-q", "tests")
    stage_collection = invoke("--collect-only", "-q", "tests/test_stage_s00d_contract.py")
    result = invoke("-q", "tests")
    stage_result = invoke("-q", "tests/test_stage_s00d_contract.py")
    private = ROOT / f"reports/runs/{run_id}/private"
    private.mkdir(exist_ok=True)
    (private / "TEST_LOG.txt").write_text(
        "\n".join(x.stdout + x.stderr for x in (full_collection, stage_collection, result, stage_result)),
        encoding="utf-8")
    passed, failed, skipped = (count(result.stdout, key) for key in ("passed", "failed", "skipped"))
    stage_passed, stage_failed, stage_skipped = (
        count(stage_result.stdout, key) for key in ("passed", "failed", "skipped"))
    record = {"command": "python -m pytest -q tests", "exit_code": result.returncode,
              "collection_exit_code": full_collection.returncode,
              "collected": count(full_collection.stdout, "tests? collected"),
              "passed": passed, "failed": failed, "skipped": skipped,
              "executed": passed + failed + skipped,
              "result_summary": result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "no summary",
              "s00d_stage_collection_exit_code": stage_collection.returncode,
              "s00d_stage_exit_code": stage_result.returncode,
              "s00d_stage_collected": count(stage_collection.stdout, "tests? collected"),
              "s00d_contract_test_count": stage_passed,
              "s00d_stage_failed": stage_failed, "s00d_stage_skipped": stage_skipped}
    write_json(ROOT / f"reports/runs/{run_id}/TEST_RESULTS.json", record)
    return record


def build_review(run_id: str, tests: dict, passed: bool) -> str:
    masks = read(REPORTS[1])
    source = read(REPORTS[5])
    return f"""# Current Review — S00D aligned data contract

task_id: `{TASK_ID}`
run_id: `{run_id}`
status: `{'READY_FOR_AUTOMATED_HANDOFF' if passed else 'GATE_NOT_PASSED'}`
repository: `BiLiangXin/jingsai`
branch: `codex/mosei-auto`
implementation_commit: `PENDING_PUBLICATION`
metadata_commit: `PENDING_PUBLICATION`
release_url: `PENDING_PUBLICATION`
release_tag: `PENDING_PUBLICATION`
review_asset: `PENDING_PUBLICATION`

## Real contract audit

The official aligned train and valid splits were validated read-only: 3,395 and 728 samples. Text/audio/vision shapes are `(N,50,768)`, `(N,50,74)`, `(N,50,35)`. Support is the continuous, nonempty binary prefix from `text_bert` channel 1. Audio/vision observed masks exclude supported structural zero rows; text observed equals support. Train support covers {masks['train']['support_positions']:,} positions and valid covers {masks['valid']['support_positions']:,}. Structural zero is not interpreted as missing. Full aggregate results are in `docs/S00D_DATA_CONTRACT.md` and `reports/data_contract/`.

Source SHA256 before/after: `{source['before']['sha256']}` / `{source['after']['sha256']}`. Both match S00C. No original file was changed. Test was never indexed for numerical audit; Attachment 3/4 content was not opened.

## Engineering and research boundary

The adapter emits float32 feature batches and explicit boolean support/observed/padding masks. Labels and regression targets are separate from the model input allowlist. The two normalizers are infrastructure only; the final normalizer choice remains undecided. This run fitted z-score statistics on train observed vectors only and checked a valid transform without model fitting or metric comparison. The NumPy adapter and masked pooling were exercised. Optional PyTorch conversion was not runtime exercised because torch is unavailable in this environment.

The full test command `python -m pytest -q tests` returned {tests['passed']} passed, {tests['failed']} failed (exit {tests['exit_code']}). The S00D Gate has 18 items. The stage remains `PENDING_RESEARCH_REVIEW`, `NEXT_STAGE_NOT_AUTHORIZED`, `STOPPED_AFTER_S00D`. S01 training is not authorized.

## Open research decisions

Unaligned's final role, final normalizer, model architecture and future missing simulation remain undecided. No `PROPOSED_RESEARCH_CHANGE` was needed; the frozen D-DATA-01 through D-DATA-07 contract was implemented without semantic change.
"""


def finalize(run_id: str) -> dict:
    head = checked_workspace()
    prior_evidence()
    run = read(f"reports/runs/{run_id}/RUN.json")
    if run.get("task_id") != TASK_ID or run.get("stage_activation_commit") != head or run.get("data_kind") != "real_official_local":
        raise RuntimeError("S00D real run or stage activation mismatch")
    tests = full_tests(run_id)
    contract, masks, labels, normalizer, loader, source = [read(p) for p in REPORTS]
    checks = [
        ("D01", "Official workspace and active S00D authorization", True, ["TASK_SPEC.md", f"reports/runs/{run_id}/RUN.json"]),
        ("D02", "S00C dependency and source baseline verified", prior_evidence() == source["before"], DEPENDENCIES),
        ("D03", "Aligned primary baseline interface encoded", contract.get("interface") == "aligned_50.pkl" and contract.get("status") == "FROZEN_FOR_BASELINE", [REPORTS[0], "DECISIONS.md"]),
        ("D04", "Support, observed and structural zero separated", all(masks[s]["audio"]["observed_equals_support_nonzero"] and masks[s]["vision"]["observed_equals_support_nonzero"] for s in ("train", "valid")), [REPORTS[1], CODE[2]]),
        ("D05", "Padding is support complement; masked reductions implemented", all(masks[s]["support_positions"] + masks[s]["padding_positions"] == 50 * masks[s]["sample_count"] for s in ("train", "valid")), [REPORTS[1], CODE[6]]),
        ("D06", "Artificial corruption is explicit and separate", "corruption" in masks["semantics"], [CODE[2], TEST_FILES[0]]),
        ("D07", "Three-class strict-zero label contract verified", labels.get("train_valid_mapping_verified") is True and labels.get("neutral_rule") == "exactly zero", [REPORTS[2], CODE[3]]),
        ("D08", "Train-only normalization enforced", normalizer.get("fit_split") == "train" and normalizer.get("valid_transform_finite") is True, [REPORTS[3], CODE[5], TEST_FILES[0]]),
        ("D09", "Model input allowlist excludes targets and private fields", loader.get("model_input_allowed_only") is True and set(loader["model_input_shapes"]) == {"text", "audio", "vision", "text_support_mask", "audio_support_mask", "vision_support_mask", "text_observed_mask", "audio_observed_mask", "vision_observed_mask", "padding_mask"}, [REPORTS[4], CODE[3]]),
        ("D10", "Train/valid dataset and batch shape/dtype validated", loader.get("model_input_shapes", {}).get("text") == [16, 50, 768] and loader.get("target_dtypes", {}).get("classification_target") == "int64", [REPORTS[4], CODE[4]]),
        ("D11", "Masked pooling nonzero-tail leakage test passed",
         tests["s00d_stage_collection_exit_code"] == 0 and tests["s00d_stage_exit_code"] == 0 and
         tests["s00d_stage_collected"] > 0 and
         tests["s00d_contract_test_count"] == tests["s00d_stage_collected"] and
         tests["s00d_stage_failed"] == tests["s00d_stage_skipped"] == 0,
         [CODE[6], TEST_FILES[0], f"reports/runs/{run_id}/TEST_RESULTS.json"]),
        ("D12", "Real aligned train/valid contract audit completed", run.get("sample_counts") == {"train": 3395, "valid": 728} and contract["splits"]["train"]["finite_features"], [REPORTS[0], f"reports/runs/{run_id}/RUN.json"]),
        ("D13", "Official aligned source unchanged", source.get("unchanged") is True and source["before"] == source["after"], [REPORTS[5], f"reports/runs/{run_id}/public/SOURCE_HASH_BEFORE.json", f"reports/runs/{run_id}/public/SOURCE_HASH_AFTER.json"]),
        ("D14", "Test quarantine preserved", run["split_usage"].get("test") == "quarantined; not indexed" and contract.get("test", "").startswith("LOCKED"), [CODE[4], CODE[7], REPORTS[0]]),
        ("D15", "Attachment 3/4 content isolation preserved", run.get("attachment3_content_inspected") is False and run.get("attachment4_content_inspected") is False, [CODE[7], f"reports/runs/{run_id}/RUN.json"]),
        ("D16", "Public safety scan passed", True, ["tools/stage_handoff.py", f"reports/runs/{run_id}/public/HANDOFF_INPUTS.json"]),
        ("D17", "Complete pytest suite passed",
         tests["collection_exit_code"] == 0 and tests["exit_code"] == 0 and
         tests["collected"] > 0 and tests["passed"] == tests["collected"] == tests["executed"] and
         tests["failed"] == tests["skipped"] == 0,
         [f"reports/runs/{run_id}/TEST_RESULTS.json"]),
        ("D18", "Documentation and evidence complete", (ROOT / "docs/S00D_DATA_CONTRACT.md").is_file() and all((ROOT / p).is_file() for p in REPORTS), ["docs/S00D_DATA_CONTRACT.md", *REPORTS]),
    ]
    files = public_files(run_id)
    if len(files) != len(set(files)) or any(not (ROOT / path).is_file() for path in files):
        raise RuntimeError("Missing or duplicate public evidence")
    scan = {path: issue for path in files if (issue := scan_public(ROOT / path))}
    if scan:
        checks[15] = ("D16", "Public safety scan failed", False, list(scan))
    items = [{"id": code, "status": "PASS" if good else "FAIL", "detail": detail, "evidence": evidence}
             for code, detail, good, evidence in checks]
    passed = all(x["status"] == "PASS" for x in items)
    gate = {"task_id": TASK_ID, "run_id": run_id, "status": "PASS" if passed else "FAIL", "passed": passed,
            "summary": {"PASS": sum(x["status"] == "PASS" for x in items),
                        "FAIL": sum(x["status"] == "FAIL" for x in items), "SKIPPED": 0, "BLOCKED": 0},
            "items": items}
    write_json(ROOT / f"reports/runs/{run_id}/GATE.json", gate)
    (ROOT / "CHATGPT_REVIEW.md").write_text(build_review(run_id, tests, passed), encoding="utf-8")
    acceptance_paths = ["CHATGPT_REVIEW.md", "docs/S00D_DATA_CONTRACT.md", *REPORTS,
        f"reports/runs/{run_id}/RUN.json", f"reports/runs/{run_id}/GATE.json",
        f"reports/runs/{run_id}/TEST_RESULTS.json"]
    acceptance = {"stage": STAGE, "data_kind": "real_official_local", "run_id": run_id,
        "status": "PASS" if passed else "FAIL",
        "evidence": [{"requirement": Path(x).name, "path": x, "sha256": sha256(ROOT / x)} for x in acceptance_paths]}
    write_json(ROOT / f"reports/stages/{STAGE}/acceptance.json", acceptance)
    manifest = {"stage": STAGE, "task_id": TASK_ID, "run_id": run_id, "public_files": files}
    write_json(ROOT / f"reports/runs/{run_id}/public/HANDOFF_INPUTS.json", manifest)
    validate_acceptance(ROOT / f"reports/stages/{STAGE}/acceptance.json", STAGE)
    if not passed:
        raise RuntimeError("S00D Gate failed; publication stopped")
    validate_run(manifest)
    return {"run_id": run_id, "gate": gate["summary"], "tests": tests, "ready_for_handoff": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.run_id), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
