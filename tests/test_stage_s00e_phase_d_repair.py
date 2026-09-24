"""PHASE D repair regressions. Every source and label here is synthetic."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import stage_handoff as handoff
import s00e_preflight
import web_chat_handoff
from s00e_evidence import node_digest

TASK = "S00E_S01_PRESTART_ENGINEERING_HARDENING"
RUN = "synthetic-review-fixture"
TESTED = {"tools/s00e_approval.py", "tests/test_stage_s00e_closeout.py","tools/stage_handoff.py", "tools/s00e_preflight.py",
          "tools/s00e_test_record.py", "tools/s00e_prepare.py", "tools/s00e_smoke.py",
          "tools/s00e_pytest_probe.py", "tools/s00e_evidence.py", "tools/s00e_d2_probes.py",
          "tools/s00d_finalize.py", "tools/web_chat_handoff.py",
          "src/mosei/data/data_contract.py", "src/mosei/data/pooling.py",
          "tests/test_stage_handoff.py", "tests/test_stage_s00e_hardening.py",
          "tests/test_stage_s00e_phase_d_repair.py", "tests/test_stage_s00e_d2_repair.py"}
REVIEWED = {"tools/s00e_approval.py", "tests/test_stage_s00e_closeout.py","tools/stage_handoff.py", "tools/s00e_preflight.py",
            "tools/web_chat_handoff.py", "tools/s00e_test_record.py",
            "tools/s00e_pytest_probe.py", "tools/s00e_evidence.py", "tools/s00e_d2_probes.py",
            "tools/s00e_prepare.py", "tools/s00e_smoke.py",
            "src/mosei/data/data_contract.py", "src/mosei/data/pooling.py",
            "tests/test_stage_s00e_hardening.py", "tests/test_stage_handoff.py",
            "tests/test_stage_s00e_phase_d_repair.py", "tests/test_stage_s00e_d2_repair.py"}


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.mark.parametrize("relative,payload", [
    ("docs/target.csv", "classification_labels,regression_labels\n1,0\n"),
    ("docs/records.json", '{"records":[{"id":"invented_fixture","label":1,"raw_text":"fixture sentence"}]}'),
    ("docs/records-top-level.json", '[{"id":"invented_fixture","regression_label":1}]'),
    ("docs/list.yaml", "raw_text:\n  - fixture sentence\n"),
    ("docs/key.json", '{"password":"fixture_' + "x" * 24 + '"}'),
    ("docs/key.toml", '"api_key" = "fixture_' + "x" * 24 + '"\n'),
    ("reports/runs/fixture/private/note.json", "{}"),
    ("reports/runs/fixture/artifacts/note.json", "{}"),
])
def test_five_sensitive_forms_detected_in_direct_worktree_and_index(relative, payload):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        git(root, "init", "-q")
        path = root / relative
        path.parent.mkdir(parents=True)
        path.write_text(payload, encoding="utf-8")
        assert handoff.scan_public_bytes(relative, path.read_bytes())
        git(root, "add", "--", relative)
        if "/private/" in relative or "/artifacts/" in relative:
            (root / ".gitignore").write_text("private/\nartifacts/\n", encoding="utf-8")
        assert relative in handoff.scan_tracked_public_tree(root)["findings"]
        if "/private/" not in relative and "/artifacts/" not in relative:
            path.write_text("{}" if relative.endswith(".json") else "# safe aggregate\n", encoding="utf-8")
            assert relative in handoff.scan_tracked_public_tree(root)["findings"]  # unsafe index
            git(root, "add", "--", relative)
            path.write_text(payload, encoding="utf-8")
            assert relative in handoff.scan_tracked_public_tree(root)["findings"]  # unsafe worktree


def test_safe_aggregates_and_binary_exclusions():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        git(root, "init", "-q")
        files = {"docs/aggregate.json": '{"train_count":3,"label":{"present":true}}',
                 "docs/config.toml": 'title = "safe aggregate"\n',
                 "docs/config.yaml": "title: safe aggregate\n"}
        for relative, value in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
            git(root, "add", "--", relative)
        (root / "figure.png").write_bytes(b"\x89PNG\x00")
        (root / "figure.docx").write_bytes(b"PK\x00")
        git(root, "add", "--", "figure.png", "figure.docx")
        result = handoff.scan_tracked_public_tree(root)
        assert result["findings"] == {}
        assert result["scanned_text_files"] == len(files)


def fixture(root: Path) -> dict:
    git(root, "init", "-q")
    (root / "TASK_SPEC.md").write_text(
        f"task_id: {TASK}\nstatus: ACTIVE\nresearch_authorized: true\n", encoding="utf-8")
    (root / "CHATGPT_REVIEW.md").write_text("# Synthetic review\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs/evidence.md").write_text("# Synthetic aggregate evidence\n", encoding="utf-8")
    for relative in TESTED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic test source\n", encoding="utf-8")
    source = root / "fixture/附件2-数据集特征文件/aligned_50.pkl"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"NOT A PICKLE; synthetic file hash fixture")
    fingerprint = {"file_name": source.name, "size": source.stat().st_size,
                   "mtime_ns": source.stat().st_mtime_ns, "sha256": handoff.sha256(source)}
    write(root / "configs/paths.local.json",
          {"data_root": str(root / "fixture"), "trusted_competition_pickle": True})
    write(root / "reports/data_contract/source_mutation_check.json",
          {"before": fingerprint, "after": fingerprint, "unchanged": True})
    source_report = {"task_id": TASK, "stage": "S00E", "run_id": RUN, "before": fingerprint,
                     "after": fingerprint, "unchanged": True}
    write(root / "reports/engineering/s00e_source_mutation_check.json", source_report)
    runtime = {"task_id": TASK, "stage": "S00E", "run_id": RUN,
               "status": "PASS", "data_kind": "real_official_local", "source_unchanged": True,
               "environment": {"name": "birdAL", "cuda_available": False},
               "smoke": {"batch_size": 2, "split": "train", "test_key_indexed": False,
                         "attachment3_content_opened": False, "attachment4_content_opened": False,
                         "numpy_batch_unchanged": True, "torch_cpu_storage_separate": True,
                         "devices": {"cpu": {"bridge": "PASS", "pooled_modalities": 3,
                                             "pooled_shapes_valid": True,
                                             "masked_tail_invariant": True,
                                             "masked_nan_isolated": True,
                                             "linear_backward_finite": True}}}}
    runtime_path = root / "reports/engineering/s00e_pytorch_runtime.json"
    write(runtime_path, runtime)
    run_base = root / "reports/runs" / RUN
    run = {"task_id": TASK, "stage": "S00E", "run_id": RUN,
           "data_kind": "real_official_local", "source_sha256_before": fingerprint["sha256"],
           "source_sha256_after": fingerprint["sha256"]}
    write(run_base / "RUN.json", run)
    nodes = ["tests/test_stage_s00e_hardening.py::test_fixture_a",
             "tests/test_stage_s00e_phase_d_repair.py::test_fixture_b",
             "tests/test_stage_s00e_d2_repair.py::test_fixture_c"]
    collection_proof = {"kind": "collection", "exit_code": 0, "nodeids": nodes, "reports": []}
    execution_proof = {"kind": "execution", "exit_code": 0, "nodeids": nodes,
                       "reports": [{"nodeid": node, "when": phase, "outcome": "passed", "subtest": False}
                                   for node in nodes for phase in ("setup", "call", "teardown")]}
    write(run_base / "private/PYTEST_COLLECTION_NODES.json", collection_proof)
    write(run_base / "private/PYTEST_EXECUTION_NODES.json", execution_proof)
    tests = {"task_id": TASK, "stage": "S00E", "run_id": RUN, "status": "PASS",
             "environment": "birdAL", "collection_command": "python -m pytest --collect-only -q tests",
             "command": "python -m pytest -q tests", "pytest_evidence_plugin": "s00e_pytest_probe",
             "collection_exit_code": 0, "exit_code": 0, "errors": 0, "failed": 0,
             "skipped": 0, "deselected": 0, "collected": 3, "executed": 3,
             "passed": 3, "subtests_passed": 0, "subtests_failed": 0,
             "subtests_errors": 0, "s00e_stage_collected": 1,
             "s00e_repair_collected": 1, "s00e_d2_collected": 1,
             "collected_nodeids_sha256": node_digest(nodes),
             "executed_nodeids_sha256": node_digest(nodes),
             "collection_proof_sha256": handoff.sha256(run_base / "private/PYTEST_COLLECTION_NODES.json"),
             "execution_proof_sha256": handoff.sha256(run_base / "private/PYTEST_EXECUTION_NODES.json"),
             "tested_files_sha256": {p: handoff.sha256(root / p) for p in TESTED}}
    tests["tested_files_before_sha256"] = dict(tests["tested_files_sha256"])
    tests["tested_files_at_execution_sha256"] = dict(tests["tested_files_sha256"])
    write(run_base / "TEST_RESULTS.json", tests)
    review_relative = "reports/engineering/s00e_phase_d_review.json"
    probe_relative = "reports/engineering/s00e_synthetic_probe_results.json"
    write(root / probe_relative, {"stage": "S00E", "run_id": RUN, "synthetic": True})
    review = {"task_id": TASK, "stage": "S00E", "run_id": RUN, "phase": "D", "status": "PASS",
              "critical_issues": 0, "blocking_issues": 0,
              "reviewer_model": "GPT-6 Astra", "reasoning": "High",
              "reviewed_files": {p: handoff.sha256(root / p) for p in REVIEWED},
              "review_evidence": [probe_relative, f"reports/runs/{RUN}/TEST_RESULTS.json"]}
    review["review_evidence_sha256"] = {p: handoff.sha256(root / p) for p in review["review_evidence"]}
    write(root / review_relative, review)
    gate = {"task_id": TASK, "run_id": RUN, "status": "BLOCKED", "passed": False,
            "summary": {"PASS": 20, "FAIL": 0, "SKIPPED": 0, "BLOCKED": 1},
            "items": [{"id": f"E{i:02d}", "status": "BLOCKED" if i == 21 else "PASS",
                       "evidence": [review_relative] if i == 19 else ["docs/evidence.md"]}
                      for i in range(1, 22)]}
    write(run_base / "GATE.json", gate)
    manifest = {"stage": "S00E", "task_id": TASK, "run_id": RUN,
                "public_files": ["docs/evidence.md", review_relative, probe_relative, *sorted(TESTED),
                                 "reports/engineering/s00e_pytorch_runtime.json",
                                 "reports/engineering/s00e_source_mutation_check.json"]}
    write(run_base / "public/HANDOFF_INPUTS.json", manifest)
    return {"root": root, "manifest": manifest, "run": run, "tests": tests,
            "runtime": runtime, "review": review, "review_relative": review_relative,
            "run_base": run_base}


def refresh(fx: dict) -> None:
    root = fx["root"]
    paths = set(fx["manifest"]["public_files"])
    paths |= {f"reports/runs/{RUN}/{name}" for name in ("RUN.json", "GATE.json", "TEST_RESULTS.json",
                                                      "public/HANDOFF_INPUTS.json")}
    paths |= {"CHATGPT_REVIEW.md"}
    write(root / "reports/stages/S00E/acceptance.json",
          {"task_id": TASK, "stage": "S00E", "run_id": RUN, "evidence": [
              {"requirement": Path(p).name, "path": p, "sha256": handoff.sha256(root / p)}
              for p in sorted(paths)]})


def validate(fx: dict) -> None:
    refresh(fx)
    with patch.object(handoff, "ROOT", fx["root"]), patch.object(
            handoff, "verify_independent_review_approval", return_value=None):
        handoff.validate_run(fx["manifest"], fx["root"], preflight=True)


def test_complete_synthetic_preflight_control_and_unlisted_tracked_rejection():
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        validate(fx)
        with patch.object(s00e_preflight, "ROOT", fx["root"]), patch.object(
                handoff, "ROOT", fx["root"]), patch.object(
                s00e_preflight, "verify_workspace", return_value="fixture"), patch.object(
                s00e_preflight, "worktree_changed_paths", return_value=set()), patch.object(
                handoff, "verify_independent_review_approval", return_value=None):
            result = s00e_preflight.run(fx["run_base"] / "public/HANDOFF_INPUTS.json")
        assert result["status"] == "PASS" and result["release_created"] is False
        unsafe = fx["root"] / "docs/unlisted.csv"
        unsafe.write_text("classification_labels,regression_labels\n1,0\n", encoding="utf-8")
        git(fx["root"], "add", "--", "docs/unlisted.csv")
        with pytest.raises(handoff.HandoffError, match="Tracked public text"):
            validate(fx)


def test_e21_requires_real_prepublication_preflight_and_no_release():
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        root = fx["root"]
        receipt_relative = "reports/engineering/s00e_prepublication_preflight.json"
        receipt = root / receipt_relative
        write(receipt, {"status": "BLOCKED", "name": "PREPUBLICATION_SAFETY_PREFLIGHT"})
        fx["manifest"]["public_files"].append(receipt_relative)
        write(fx["run_base"] / "public/HANDOFF_INPUTS.json", fx["manifest"])
        refresh(fx)
        with patch.object(s00e_preflight, "ROOT", root), patch.object(
                handoff, "ROOT", root), patch.object(
                s00e_preflight, "verify_workspace", return_value="fixture"), patch.object(
                s00e_preflight, "worktree_changed_paths", return_value=set()), patch.object(
                handoff, "verify_independent_review_approval", return_value=None):
            result = s00e_preflight.run(fx["run_base"] / "public/HANDOFF_INPUTS.json")
        assert result["status"] == "PASS" and result["release_created"] is False
        write(receipt, result)
        gate = json.loads((fx["run_base"] / "GATE.json").read_text(encoding="utf-8"))
        gate["items"][-1]["status"] = "PASS"
        gate["items"][-1]["evidence"] = [receipt_relative]
        gate["status"] = "PASS"
        gate["passed"] = True
        gate["summary"] = {"PASS": 21, "FAIL": 0, "SKIPPED": 0, "BLOCKED": 0}
        write(fx["run_base"] / "GATE.json", gate)
        refresh(fx)
        with patch.object(handoff, "ROOT", root), patch.object(
                handoff, "verify_independent_review_approval", return_value=None):
            handoff.validate_run(fx["manifest"], root)
        result["manifest_sha256"] = "0" * 64
        write(receipt, result)
        refresh(fx)
        with pytest.raises(handoff.HandoffError, match="E21"):
            with patch.object(handoff, "ROOT", root), patch.object(
                    handoff, "verify_independent_review_approval", return_value=None):
                handoff.validate_run(fx["manifest"], root)


@pytest.mark.parametrize("defect", ["missing_review", "stale_review", "wrong_run_review",
                                    "wrong_hash", "wrong_test_run", "test_status",
                                    "collection_exit", "execution_exit_bool", "errors",
                                    "deselected", "stage_count", "repair_count", "tested_code_changed",
                                    "runtime_other_run", "runtime_no_smoke", "cpu_failure",
                                    "cuda_missing"])
def test_adversarial_evidence_rejected_before_git_write(defect):
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        run_base, root = fx["run_base"], fx["root"]
        if defect == "missing_review":
            (root / fx["review_relative"]).unlink()
        elif defect == "stale_review":
            (root / "tools/stage_handoff.py").write_text("# changed after review\n", encoding="utf-8")
            tests = fx["tests"]
            tests["tested_files_sha256"]["tools/stage_handoff.py"] = handoff.sha256(root / "tools/stage_handoff.py")
            write(run_base / "TEST_RESULTS.json", tests)
        elif defect == "wrong_run_review":
            fx["review"]["run_id"] = "foreign-fixture"
            write(root / fx["review_relative"], fx["review"])
        elif defect == "wrong_hash":
            fx["review"]["reviewed_files"]["tools/stage_handoff.py"] = "0" * 64
            write(root / fx["review_relative"], fx["review"])
        elif defect in {"wrong_test_run", "test_status", "collection_exit", "execution_exit_bool",
                        "errors", "deselected", "stage_count", "repair_count"}:
            tests = fx["tests"]
            key, value = {"wrong_test_run": ("run_id", "foreign-fixture"),
                          "test_status": ("status", "FAIL"),
                          "collection_exit": ("collection_exit_code", 2),
                          "execution_exit_bool": ("exit_code", False),
                          "errors": ("errors", 1), "deselected": ("deselected", 1),
                          "stage_count": ("s00e_stage_collected", 0),
                          "repair_count": ("s00e_repair_collected", 0)}[defect]
            tests[key] = value
            write(run_base / "TEST_RESULTS.json", tests)
        else:
            runtime = fx["runtime"]
            if defect == "tested_code_changed":
                (root / "tools/s00e_prepare.py").write_text("# changed after tests\n", encoding="utf-8")
            elif defect == "runtime_other_run":
                runtime["run_id"] = "foreign-fixture"
            elif defect == "runtime_no_smoke":
                runtime["smoke"] = None
            elif defect == "cpu_failure":
                runtime["smoke"]["devices"]["cpu"]["linear_backward_finite"] = False
            elif defect == "cuda_missing":
                runtime["environment"]["cuda_available"] = True
            if defect != "tested_code_changed":
                write(root / "reports/engineering/s00e_pytorch_runtime.json", runtime)
        with pytest.raises((handoff.HandoffError, FileNotFoundError)):
            validate(fx)


def test_generated_zip_uses_same_content_scan():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bad = root / "docs/target.csv"
        bad.parent.mkdir(parents=True)
        bad.write_text("classification_labels,regression_labels\n1,0\n", encoding="utf-8")
        response = {"stage": "S00E", "status": "blocked", "summary": "synthetic fixture",
                    "changes": [], "tests": [], "blockers": [], "next_actions": [],
                    "data_kind": "synthetic", "metrics_file": None}
        with pytest.raises(web_chat_handoff.BundleError):
            web_chat_handoff.create_bundle(root, "synthetic_safety_fixture", response,
                                           ["docs/target.csv"])
