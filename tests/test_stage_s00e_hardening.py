"""Synthetic adversarial checks for S00E; no official data is opened."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from mosei.data.data_contract import AlignedBatch, validate_label_contract
from mosei.data.dataset import create_aligned_dataset
from mosei.data.masks import aligned_mask_set
from mosei.data.normalization import TrainOnlyZScoreNormalizer
from mosei.data.pooling import masked_mean, masked_sum
import stage_handoff as handoff
import s00d_finalize
import s00e_prepare
import s00e_smoke
import s00e_test_record


def arrays():
    text = np.ones((2, 50, 768), dtype=np.float32)
    audio = np.ones((2, 50, 74), dtype=np.float64)
    vision = np.ones((2, 50, 35), dtype=np.float64)
    audio[0, 0] = 0
    vision[0, 1] = 0
    support = np.zeros((2, 50), dtype=bool)
    support[:, :2] = True
    masks = aligned_mask_set(support, audio, vision)
    return text, audio, vision, masks


def batch():
    text, audio, vision, masks = arrays()
    return AlignedBatch.from_arrays(
        text, audio, vision, masks, np.array([0, 2]), np.array([-1.0, 1.0]))


def test_all_mask_fields_require_boolean_shape():
    text, audio, vision, masks = arrays()
    for name in masks.__dataclass_fields__:
        original = getattr(masks, name)
        for forged in (original.astype(np.int8), original[:, :-1]):
            with pytest.raises(ValueError):
                AlignedBatch.from_arrays(text, audio, vision, replace(masks, **{name: forged}),
                                         np.array([0, 2]), np.array([-1.0, 1.0]))


def test_frozen_mask_equalities_reject_forgery():
    text, audio, vision, masks = arrays()
    alterations = [
        ("padding_mask", (0, 0)),
        ("text_observed_mask", (0, 0)),
        ("audio_support_mask", (0, 0)),
        ("vision_support_mask", (0, 0)),
        ("audio_observed_mask", (0, 1)),
        ("vision_observed_mask", (0, 0)),
        ("audio_structural_zero_mask", (0, 0)),
        ("vision_structural_zero_mask", (0, 1)),
    ]
    for name, location in alterations:
        forged = getattr(masks, name).copy()
        forged[location] = ~forged[location]
        with pytest.raises(ValueError):
            AlignedBatch.from_arrays(text, audio, vision, replace(masks, **{name: forged}),
                                     np.array([0, 2]), np.array([-1.0, 1.0]))
    for forged_support in (np.zeros_like(masks.text_support_mask),
                           np.tile([False, True] + [False] * 48, (2, 1))):
        forged = aligned_mask_set(forged_support, audio, vision)
        with pytest.raises(ValueError):
            AlignedBatch.from_arrays(text, audio, vision, forged,
                                     np.array([0, 2]), np.array([-1.0, 1.0]))
    assert not bool(batch().padding_mask[0, 0])


def test_float32_conversion_preserves_finite_and_strict_zero():
    text, audio, vision, masks = arrays()
    audio[0, 1, 0] = 1e300
    with pytest.raises(ValueError, match="float32"):
        AlignedBatch.from_arrays(text, audio, vision, masks,
                                 np.array([0, 2]), np.array([-1.0, 1.0]))
    with pytest.raises(ValueError, match="strict-zero"):
        validate_label_contract(np.array([2]), np.array([1e-50]))
    with pytest.raises(ValueError, match="structural-zero"):
        small = arrays()
        small[1][0, 1, :] = 1e-300
        AlignedBatch.from_arrays(small[0], small[1], small[2], small[3],
                                 np.array([0, 2]), np.array([-1.0, 1.0]))
    classes, values = validate_label_contract(np.array([1]), np.array([0.0]))
    assert classes[0] == 1 and values[0] == 0


def test_batch_and_torch_bridge_do_not_alias_sources():
    text, audio, vision, masks = arrays()
    original_text = text.copy()
    original_support = masks.text_support_mask.copy()
    raw = AlignedBatch.from_arrays(text, audio, vision, masks,
                                   np.array([0, 2]), np.array([-1.0, 1.0]))
    raw.text[0, 0, 0] += 1
    raw.text_support_mask[0, 0] = False
    assert np.array_equal(text, original_text)
    assert np.array_equal(masks.text_support_mask, original_support)
    for group in ("model_inputs", "targets"):
        for key in getattr(batch(), group):
            current = batch()
            original = getattr(current, group)[key].copy()
            tensor = current.to_torch()[group][key]
            if tensor.dtype == torch.bool:
                tensor.reshape(-1)[0].logical_not_()
            else:
                tensor.reshape(-1)[0].add_(1)
            assert np.array_equal(getattr(current, group)[key], original), (group, key)
    bridge = batch().to_torch()
    assert set(bridge["model_inputs"]) == set(batch().model_inputs)
    assert set(bridge["targets"]) == {"classification_target", "regression_target"}
    assert set(bridge["model_inputs"]).isdisjoint(bridge["targets"])
    assert all(bridge["model_inputs"][key].dtype == torch.float32 for key in ("text", "audio", "vision"))
    assert all(value.dtype == torch.bool for key, value in bridge["model_inputs"].items()
               if key.endswith("mask"))


def test_normalized_zero_does_not_redefine_source_observed_mask():
    text, audio, vision, masks = arrays()
    bert = np.zeros((2, 3, 50), dtype=np.int64)
    bert[:, 1, :2] = 1
    item = {"text": text, "audio": audio, "vision": vision, "text_bert": bert,
            "classification_labels": np.array([0, 2]),
            "regression_labels": np.array([-1.0, 1.0])}
    dataset = create_aligned_dataset({"train": item}, "train")
    original = dataset.batch([0, 1])
    transformed = TrainOnlyZScoreNormalizer().fit(dataset).transform(original)
    assert transformed.audio[0, 1, 0] == 0
    assert bool(transformed.audio_observed_mask[0, 1])
    assert not bool(transformed.audio_observed_mask[0, 0])
    assert np.array_equal(original.audio_observed_mask, transformed.audio_observed_mask)


def test_tiny_smoke_indexes_only_train_and_isolates_targets():
    text, audio, vision, _ = arrays()
    bert = np.zeros((2, 3, 50), dtype=np.int64)
    bert[:, 1, :2] = 1
    train = {"text": text, "audio": audio, "vision": vision, "text_bert": bert,
             "classification_labels": np.array([0, 2]),
             "regression_labels": np.array([-1.0, 1.0])}

    class GuardedSource(dict):
        def __getitem__(self, key):
            if key != "train":
                raise AssertionError("Quarantined split was indexed")
            return super().__getitem__(key)

    original = {key: value.copy() for key, value in train.items()}
    result = s00e_smoke.tiny_train_smoke(GuardedSource(train=train))
    assert result["split"] == "train" and not result["test_key_indexed"]
    assert result["numpy_batch_unchanged"]
    assert "cpu" in result["devices"]
    assert all(np.array_equal(train[key], original[key]) for key in train)


@pytest.mark.parametrize("device", ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"])
def test_torch_pooling_ignores_padding_nan_inf_and_has_finite_gradients(device):
    current = batch()
    bridge = current.to_torch()
    values = bridge["model_inputs"]["text"].to(device).requires_grad_(True)
    support = bridge["model_inputs"]["text_support_mask"].to(device)
    expected = masked_mean(values, support)
    assert torch.isfinite(expected).all()
    expected.sum().backward()
    assert torch.isfinite(values.grad).all()
    assert torch.all(values.grad[~support] == 0)
    for tail in (1e30, float("nan"), float("inf")):
        poisoned = values.detach().clone()
        poisoned[~support] = tail
        torch.testing.assert_close(masked_mean(poisoned, support), expected.detach())
    active = values.detach().clone()
    active[0, 0, 0] = float("nan")
    with pytest.raises(ValueError, match="Supported"):
        masked_sum(active, support)
    active[0, 0, 0] = float("inf")
    with pytest.raises(ValueError, match="Supported"):
        masked_mean(active, support)
    assert torch.all(masked_mean(values.detach(), torch.zeros_like(support)) == 0)
    assert torch.isfinite(values.detach()).all()


def git(root: Path, *args: str):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_tracked_tree_scans_unlisted_index_content_and_deletions():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        git(root, "init", "-q")
        (root / "docs").mkdir()
        (root / "images").mkdir()
        safe = root / "docs/safe.md"
        unsafe = root / "docs/unlisted.csv"
        safe.write_text("# safe aggregate evidence\n", encoding="utf-8")
        (root / "images/figure.png").write_bytes(b"\x89PNG\x00")
        (root / "docs/statement.docx").write_bytes(b"PK\x00")
        git(root, "add", "--", "docs/safe.md", "images/figure.png", "docs/statement.docx")
        clean = handoff.scan_tracked_public_tree(root)
        assert clean == {"scanned_text_files": 1, "findings": {}}
        unsafe.write_text("sample_id,label\n", encoding="utf-8")
        git(root, "add", "--", "docs/unlisted.csv")
        assert "sample_level_csv_columns" in handoff.scan_tracked_public_tree(root)["findings"]["docs/unlisted.csv"]
        git(root, "-c", "user.email=fixture@invalid", "-c", "user.name=Fixture",
            "commit", "-q", "-m", "synthetic fixture")
        git(root, "rm", "--", "docs/unlisted.csv")
        assert handoff.scan_tracked_public_tree(root)["findings"] == {}
        safe.unlink()
        assert "missing_linked_or_escaping_worktree_file" in handoff.scan_tracked_public_tree(root)["findings"]["docs/safe.md"]


def test_manifest_safe_but_unlisted_tracked_csv_blocks_run_validation():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        git(root, "init", "-q")
        (root / "TASK_SPEC.md").write_text(
            "task_id: S01_EXAMPLE\nstatus: ACTIVE\nresearch_authorized: true\n",
            encoding="utf-8")
        (root / "CHATGPT_REVIEW.md").write_text("# Safe review\n", encoding="utf-8")
        run = root / "reports/runs/r12345"
        (run / "public").mkdir(parents=True)
        values = {
            "RUN.json": {"task_id": "S01_EXAMPLE", "data_kind": "official"},
            "GATE.json": {"task_id": "S01_EXAMPLE", "run_id": "r12345", "status": "PASS",
                          "passed": True,
                          "summary": {"PASS": 1, "FAIL": 0, "SKIPPED": 0, "BLOCKED": 0},
                          "items": [{"id": "X01", "status": "PASS",
                                     "evidence": ["CHATGPT_REVIEW.md"]}]},
            "TEST_RESULTS.json": {"exit_code": 0, "passed": 1, "failed": 0},
        }
        for name, value in values.items():
            (run / name).write_text(json.dumps(value), encoding="utf-8")
        manifest = {"stage": "S01", "task_id": "S01_EXAMPLE",
                    "run_id": "r12345", "public_files": []}
        (run / "public/HANDOFF_INPUTS.json").write_text(json.dumps(manifest), encoding="utf-8")
        acceptance = root / "reports/stages/S01/acceptance.json"
        acceptance.parent.mkdir(parents=True)
        acceptance.write_text(json.dumps({
            "stage": "S01", "evidence": [{
                "path": "reports/runs/r12345/RUN.json",
                "sha256": handoff.sha256(run / "RUN.json")}]}), encoding="utf-8")
        outside = root / "docs/unlisted.csv"
        outside.parent.mkdir()
        outside.write_text("sample_id,label\n", encoding="utf-8")
        git(root, "add", "--", "docs/unlisted.csv")
        with patch.object(handoff, "ROOT", root):
            with pytest.raises(handoff.HandoffError, match="Tracked public text"):
                handoff.validate_run(manifest, root)


def test_public_markdown_test_distribution_blocked():
    unsafe = b"| split | Negative | Neutral | Positive |\n| test | 1 | 2 | 3 |\n"
    assert "test_distribution_table" in handoff.scan_public_bytes("docs/table.md", unsafe)
    pooled = b"| File | Negative | Neutral | Positive |\n| label.xlsx | 10 | 10 | 10 |\n"
    assert "test_bearing_label_distribution_table" in handoff.scan_public_bytes(
        "docs/pooled.md", pooled)
    assert handoff.scan_public_bytes("docs/aggregate.md", b"# Verified contract\n") == []
    assert "sample_level_array" in handoff.scan_public_bytes(
        "docs/list.yaml", b"sample_ids: [item_one, item_two]\n")


def full_gate():
    return {"task_id": "S00E_EXAMPLE", "run_id": "r12345", "status": "PASS", "passed": True,
            "summary": {"PASS": 21, "FAIL": 0, "SKIPPED": 0, "BLOCKED": 0},
            "items": [{"id": f"E{i:02d}", "status": "PASS", "evidence": ["docs/evidence.md"]}
                      for i in range(1, 22)]}


def test_gate_rejects_skip_missing_duplicate_inconsistent_and_foreign_identity():
    handoff.validate_gate(full_gate(), "S00E", "S00E_EXAMPLE", "r12345")
    for defect in ("skip", "fail_item", "missing_items", "zero_pass", "duplicate",
                   "missing_status", "foreign_run", "missing_id", "wrong_summary",
                   "missing_evidence", "boolean_count"):
        gate = json.loads(json.dumps(full_gate()))
        if defect == "skip":
            gate["items"][0]["status"] = "SKIPPED"
            gate["summary"] = {"PASS": 20, "FAIL": 0, "SKIPPED": 1, "BLOCKED": 0}
        elif defect == "fail_item":
            gate["items"][0]["status"] = "FAIL"
        elif defect == "missing_items":
            gate.pop("items")
        elif defect == "zero_pass":
            gate["items"] = []
            gate["summary"]["PASS"] = 0
        elif defect == "duplicate":
            gate["items"][1]["id"] = "E01"
        elif defect == "missing_status":
            gate.pop("status")
        elif defect == "foreign_run":
            gate["run_id"] = "other"
        elif defect == "missing_id":
            gate["items"].pop()
            gate["summary"]["PASS"] = 20
        elif defect == "wrong_summary":
            gate["summary"]["PASS"] = 22
        elif defect == "missing_evidence":
            gate["items"][0]["evidence"] = []
        elif defect == "boolean_count":
            gate["summary"]["FAIL"] = False
        with pytest.raises(handoff.HandoffError):
            handoff.validate_gate(gate, "S00E", "S00E_EXAMPLE", "r12345")


def test_publisher_rechecks_live_source_hash_before_git_write():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "data/附件2-数据集特征文件/aligned_50.pkl"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"synthetic fixture")
        expected = {"file_name": "aligned_50.pkl", "size": source.stat().st_size,
                    "mtime_ns": source.stat().st_mtime_ns,
                    "sha256": handoff.sha256(source)}
        files = {
            "reports/data_contract/source_mutation_check.json":
                {"before": expected, "after": expected, "unchanged": True},
            "reports/engineering/s00e_source_mutation_check.json":
                    {"task_id": "S00E_S01_PRESTART_ENGINEERING_HARDENING", "stage": "S00E",
                     "run_id": "synthetic-run", "before": expected, "after": expected, "unchanged": True},
            "reports/engineering/s00e_pytorch_runtime.json":
                    {"task_id": "S00E_S01_PRESTART_ENGINEERING_HARDENING", "stage": "S00E",
                     "run_id": "synthetic-run", "status": "PASS", "data_kind": "real_official_local",
                     "source_unchanged": True,
                     "environment": {"name": "birdAL", "cuda_available": False},
                     "smoke": {"batch_size": 2, "split": "train", "test_key_indexed": False,
                               "attachment3_content_opened": False,
                               "attachment4_content_opened": False,
                               "numpy_batch_unchanged": True, "torch_cpu_storage_separate": True,
                               "devices": {"cpu": {"bridge": "PASS", "pooled_modalities": 3,
                                                   "pooled_shapes_valid": True,
                                                   "masked_tail_invariant": True,
                                                   "masked_nan_isolated": True,
                                                   "linear_backward_finite": True}}}},
            "configs/paths.local.json":
                {"data_root": str(root / "data"), "trusted_competition_pickle": True},
        }
        for name, value in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
            run = {"task_id": "S00E_S01_PRESTART_ENGINEERING_HARDENING", "stage": "S00E",
                   "run_id": "synthetic-run", "source_sha256_before": expected["sha256"],
               "source_sha256_after": expected["sha256"]}
        handoff.validate_s00e_source(run, root)
        source.write_bytes(b"changed synthetic fixture")
        with pytest.raises(handoff.HandoffError, match="changed"):
            handoff.validate_s00e_source(run, root)


def test_porcelain_rename_and_unicode_paths_remain_visible():
    raw = "R  docs/new-证据.md\0docs/old-证据.md\0"
    with patch.object(handoff, "command", return_value=SimpleNamespace(stdout=raw)):
        assert handoff.worktree_changed_paths() == {
            "docs/new-证据.md", "docs/old-证据.md"}


def test_s00d_test_count_comes_from_actual_process_output():
    def completed(stdout):
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)

    responses = [
        completed("1 test collected in 0.01s\n"),
        completed("1 test collected in 0.01s\n"),
        completed("1 passed in 0.01s\n"),
        completed("1 passed in 0.01s\n"),
    ]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "reports/runs/r12345").mkdir(parents=True)
        with patch.object(s00d_finalize, "ROOT", root), patch.object(
                s00d_finalize.subprocess, "run", side_effect=responses):
            result = s00d_finalize.full_tests("r12345")
    assert result["collected"] == result["executed"] == result["passed"] == 1
    assert result["s00d_stage_collected"] == result["s00d_contract_test_count"] == 1
    assert result["collection_exit_code"] == result["s00d_stage_exit_code"] == 0


def test_phase_c_gate_stays_blocked_until_review_and_handoff():
    evidence = {code: ["docs/evidence.md"] for code in handoff.S00E_GATE_IDS}
    checks = {code: code not in {"E19", "E21"} for code in handoff.S00E_GATE_IDS}
    gate = s00e_prepare.make_gate("r12345", evidence, checks)
    assert gate["status"] == "BLOCKED" and gate["passed"] is False
    assert gate["summary"] == {"PASS": 19, "FAIL": 0, "SKIPPED": 0, "BLOCKED": 2}
    with pytest.raises(handoff.HandoffError):
        handoff.validate_gate(gate, "S00E", "S00E_EXAMPLE", "r12345")


def test_pytest_counts_do_not_add_subtests_to_collected_cases():
    summary = "132 passed, 25 subtests passed in 1.0s"
    assert s00e_test_record.number(summary, "passed") == 132
    assert s00e_test_record.number(summary, "subtests passed") == 25
    assert s00e_test_record.number("132 tests collected in 1.0s", "tests? collected") == 132


def test_q1_governance_and_public_navigation():
    decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs/data-guide.md").read_text(encoding="utf-8")
    assert "Q1-SOURCE-01" in decisions and "Q1-MISSING-01 | UNDECIDED" in decisions
    assert "SPECIFIED user-supplied competition forum expert reply" in decisions
    assert "label-100.xlsx:text" in decisions and "Retain all 100" in decisions
    assert "samples/labels-" not in guide
    assert "samples/labels-" not in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS" in (
        ROOT / "state/NEXT_ACTIONS.md").read_text(encoding="utf-8")
