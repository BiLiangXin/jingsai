"""D2 regression cases use invented records and temporary repositories only."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import s00e_prepare
import stage_handoff as handoff
import web_chat_handoff as web
from test_stage_s00e_phase_d_repair import fixture, refresh, validate, write, git


RESPONSE = {"stage": "S00E", "status": "blocked", "summary": "Synthetic scan probe",
            "changes": [], "tests": [], "blockers": [], "next_actions": [],
            "data_kind": "synthetic", "metrics_file": None}


@pytest.mark.parametrize("relative,payload", [
    ("docs/bom.csv", "\ufeffclassification_labels\n1\n"),
    ("docs/space.csv", " regression_labels \n1\n"),
    ("docs/uppercase.json", '{"nested":{"RAW_TEXT":"invented fixture"}}'),
    ("docs/plural.json", '{"nested":{"id":"invented","regression_labels":1}}'),
    ("docs/plural.yaml", 'nested:\n  id: invented\n  classification_labels: 1\n'),
    ("docs/plural.toml", '[nested]\nid="invented"\nlabels=1\n'),
    ("docs/sample.json", '{"id":"invented","label":1,"raw_text":"fixture"}'),
    ("docs/sample.yaml", 'outer:\n  record:\n    id: invented\n    label: 1\n    raw_text: fixture\n'),
    ("docs/sample.toml", '[outer.record]\nid="invented"\nlabel=1\nraw_text="fixture"\n'),
    ("docs/duplicate.json", '{"raw_text":"fixture","raw_text":{"present":true}}'),
    ("docs/duplicate.yaml", 'raw_text:\n  - fixture\nraw_text: {present: true}\n'),
])
def test_sample_and_duplicate_scans_all_surfaces(relative, payload):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        fx = fixture(root)
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        assert handoff.scan_public_bytes(relative, path.read_bytes())
        git(root, "add", "--", relative)
        assert relative in handoff.scan_tracked_public_tree(root)["findings"]
        path.write_text("{}\n" if relative.endswith(".json") else "title: safe\n" if relative.endswith(".yaml") else 'title="safe"\n', encoding="utf-8")
        assert relative in handoff.scan_tracked_public_tree(root)["findings"]
        git(root, "add", "--", relative)
        path.write_text(payload, encoding="utf-8")
        assert relative in handoff.scan_tracked_public_tree(root)["findings"]
        with pytest.raises(handoff.HandoffError):
            validate(fx)  # tracked, outside manifest
        fx["manifest"]["public_files"].append(relative)
        write(fx["run_base"] / "public/HANDOFF_INPUTS.json", fx["manifest"])
        with pytest.raises(handoff.HandoffError):
            validate(fx)  # manifest and tracked
        with pytest.raises(web.BundleError):
            web.create_bundle(root, "synthetic_d2_scan_fixture", RESPONSE, [relative])


def test_safe_aggregate_control_and_gate_id():
    for relative, payload in (
        ("docs/aggregate.json", '{"run_id":"fixture-run","summary":{"PASS":21},"items":[{"id":"E19","status":"BLOCKED"}]}'),
        ("docs/aggregate.yaml", 'label:\n  present: true\nrun_id: fixture-run\n'),
        ("docs/aggregate.toml", '[label]\npresent=true\n')):
        assert handoff.scan_public_bytes(relative, payload.encode()) == []


def test_manual_review_approval_is_hard_gate_even_for_self_asserted_pass():
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        refresh(fx)
        with patch.object(handoff, "ROOT", fx["root"]), pytest.raises(
                handoff.HandoffError, match="MANUAL_REVIEW_APPROVAL_REQUIRED"):
            handoff.validate_run(fx["manifest"], fx["root"], preflight=True)


def test_acceptance_other_run_and_stale_review_rejected():
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        refresh(fx)
        path = fx["root"] / "reports/stages/S00E/acceptance.json"
        acceptance = json.loads(path.read_text(encoding="utf-8"))
        acceptance["run_id"] = "different-run"
        write(path, acceptance)
        with patch.object(handoff, "ROOT", fx["root"]), pytest.raises(
                handoff.HandoffError, match="acceptance task/stage/run"):
            handoff.validate_run(fx["manifest"], fx["root"], preflight=True)
        refresh(fx)
        fx["review"]["reviewed_files"]["tools/s00e_evidence.py"] = "0" * 64
        write(fx["root"] / fx["review_relative"], fx["review"])
        with pytest.raises(handoff.HandoffError):
            validate(fx)


@pytest.mark.parametrize("defect", ["stage_sum", "different_node_same_count", "stage_collected_only",
                                    "missing_subtests", "negative_subtests", "string_subtests",
                                    "boolean_subtests", "subtest_failure", "proof_hash"])
def test_pytest_node_and_subtest_attacks_rejected(defect):
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        tests = copy.deepcopy(fx["tests"])
        if defect == "stage_sum":
            tests["s00e_stage_collected"] = 18
            tests["s00e_repair_collected"] = 29
        elif defect == "different_node_same_count":
            tests["executed_nodeids_sha256"] = "0" * 64
        elif defect == "stage_collected_only":
            proof = fx["run_base"] / "private/PYTEST_EXECUTION_NODES.json"
            value = json.loads(proof.read_text(encoding="utf-8"))
            value["reports"] = [r for r in value["reports"] if not r["nodeid"].startswith("tests/test_stage_s00e_d2_repair.py::")]
            write(proof, value)
            tests["execution_proof_sha256"] = handoff.sha256(proof)
        elif defect == "missing_subtests":
            del tests["subtests_passed"]
        elif defect == "negative_subtests":
            tests["subtests_passed"] = -1
        elif defect == "string_subtests":
            tests["subtests_passed"] = "0"
        elif defect == "boolean_subtests":
            tests["subtests_passed"] = False
        elif defect == "subtest_failure":
            tests["subtests_failed"] = 1
        elif defect == "proof_hash":
            tests["collection_proof_sha256"] = "0" * 64
        write(fx["run_base"] / "TEST_RESULTS.json", tests)
        with pytest.raises(handoff.HandoffError):
            validate(fx)


@pytest.mark.parametrize("defect", ["failed_gradient", "missing_cpu", "missing_cuda",
                                    "wrong_runtime_run", "wrong_test_type"])
def test_prepare_rejects_bad_evidence_before_writing_gate(defect):
    with tempfile.TemporaryDirectory() as directory:
        fx = fixture(Path(directory))
        root = fx["root"]
        if defect == "wrong_test_type":
            tests = copy.deepcopy(fx["tests"])
            tests["collection_exit_code"] = False
            write(fx["run_base"] / "TEST_RESULTS.json", tests)
        else:
            runtime = copy.deepcopy(fx["runtime"])
            if defect == "failed_gradient":
                runtime["smoke"]["devices"]["cpu"]["linear_backward_finite"] = False
            elif defect == "missing_cpu":
                runtime["smoke"]["devices"].pop("cpu")
            elif defect == "missing_cuda":
                runtime["environment"]["cuda_available"] = True
            elif defect == "wrong_runtime_run":
                runtime["run_id"] = "foreign-run"
            write(root / "reports/engineering/s00e_pytorch_runtime.json", runtime)
        old_gate = handoff.sha256(fx["run_base"] / "GATE.json")
        def fake_git(*args):
            if args == ("remote", "get-url", "origin"):
                return s00e_prepare.ORIGIN
            if args == ("branch", "--show-current"):
                return s00e_prepare.BRANCH
            if args == ("config", "--local", "--get", "mosei.officialWorkspace"):
                return "true"
            if args == ("rev-parse", "HEAD"):
                return s00e_prepare.GOVERNANCE_HEAD
            if args == ("merge-base", s00e_prepare.SAFETY_PRECOMMIT, "HEAD"):
                return s00e_prepare.SAFETY_PRECOMMIT
            if args == ("diff", "--name-only", s00e_prepare.SAFETY_PRECOMMIT, "HEAD"):
                return "AGENTS.md\nDECISIONS.md\nTASK_SPEC.md\ndocs/HANDOFF_WORKFLOW.md"
            if args[:2] == ("ls-remote", "origin"):
                return s00e_prepare.GOVERNANCE_HEAD + " refs/heads/codex/mosei-auto"
            if args[:2] == ("ls-files", "--"):
                return ""
            if args == ("show", f"{s00e_prepare.SAFETY_PRECOMMIT}:DECISIONS.md"):
                return "| Q1-SOURCE-01 | FROZEN | synthetic fixture |"
            raise AssertionError(args)
        (root / "DECISIONS.md").write_text("| Q1-SOURCE-01 | FROZEN | synthetic fixture |\n", encoding="utf-8")
        with patch.object(s00e_prepare, "ROOT", root), patch.object(
                s00e_prepare, "git", side_effect=fake_git), pytest.raises(RuntimeError):
            s00e_prepare.prepare(fx["manifest"]["run_id"])
        assert handoff.sha256(fx["run_base"] / "GATE.json") == old_gate
