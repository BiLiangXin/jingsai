"""Read-only S00D aligned train/valid contract validation. No test indexing."""
from __future__ import annotations

import argparse
import json
import pickle
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from mosei_flow import write_json
from s00b_audit import file_fingerprint
from stage_handoff import BRANCH, ORIGIN, spec_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mosei.data.dataset import create_aligned_dataset, training_batches  # noqa: E402
from mosei.data.normalization import IdentityNormalizer, TrainOnlyZScoreNormalizer  # noqa: E402
from mosei.data.pooling import masked_mean  # noqa: E402

TASK_ID = "S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS"
S00C_RUN = "20260924-014331-S00C-afeafae"
REPORT = Path("reports/data_contract")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def checked_workspace() -> str:
    if not (ROOT / ".git").is_dir() or Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT.resolve():
        raise RuntimeError("Official repository checkout required")
    if git("config", "--local", "--get", "mosei.officialWorkspace").lower() != "true":
        raise RuntimeError("Official workspace marker absent")
    if git("remote", "get-url", "origin") != ORIGIN or git("branch", "--show-current") != BRANCH:
        raise RuntimeError("Official origin or branch mismatch")
    head = git("rev-parse", "HEAD")
    remote = git("ls-remote", "--heads", "origin", BRANCH).split()
    if not remote or remote[0] != head:
        raise RuntimeError("Local and remote HEAD differ")
    spec = (ROOT / "TASK_SPEC.md").read_text(encoding="utf-8")
    required = {"task_id": TASK_ID, "status": "ACTIVE", "research_authorized": "true",
                "next_stage_authorized": "false", "stage_type": "data_contract", "task_version": "1.0"}
    if any(spec_scalar(spec, key) != value for key, value in required.items()):
        raise RuntimeError("S00D task specification not active")
    return head


def trusted_source() -> Path:
    local = ROOT / "configs/paths.local.json"
    config = json.loads(local.read_text(encoding="utf-8-sig"))
    if set(config) != {"data_root", "trusted_competition_pickle"} or config["trusted_competition_pickle"] is not True:
        raise RuntimeError("Trusted local official data configuration required")
    path = Path(config["data_root"]) / "附件2-数据集特征文件" / "aligned_50.pkl"
    if not path.is_file():
        raise RuntimeError("Official aligned file unavailable")
    return path


def prior_evidence() -> dict:
    latest = json.loads((ROOT / "state/LATEST_RUN.json").read_text(encoding="utf-8"))
    s00c = json.loads((ROOT / "reports/data_audit/s00c_source_mutation_check.json").read_text(encoding="utf-8"))
    gate = json.loads((ROOT / f"reports/runs/{S00C_RUN}/GATE.json").read_text(encoding="utf-8"))
    if latest.get("run_id") != S00C_RUN or latest.get("latest_completed_stage") != "S00C" or gate.get("passed") is not True:
        raise RuntimeError("S00C dependency not verified")
    if s00c.get("unchanged", {}).get("aligned") is not True:
        raise RuntimeError("S00C aligned mutation check did not pass")
    return s00c["after"]["aligned"]


def _mask_summary(dataset) -> dict:
    m = dataset.masks
    result = {"sample_count": len(dataset), "support_positions": int(m.text_support_mask.sum()),
              "padding_positions": int(m.padding_mask.sum()),
              "support_lengths": {"min": int(m.text_support_mask.sum(1).min()),
                                  "max": int(m.text_support_mask.sum(1).max()),
                                  "mean": float(m.text_support_mask.sum(1).mean())},
              "shared_support_equal": bool(np.array_equal(m.text_support_mask, m.audio_support_mask) and
                                           np.array_equal(m.text_support_mask, m.vision_support_mask))}
    for name in ("audio", "vision"):
        zero = getattr(m, f"{name}_structural_zero_mask")
        observed = getattr(m, f"{name}_observed_mask")
        result[name] = {"structural_zero_positions_total": int(zero.sum()),
                        "structural_zero_within_support": int((zero & m.text_support_mask).sum()),
                        "observed_positions": int(observed.sum()),
                        "observed_equals_support_nonzero": bool(np.array_equal(observed, m.text_support_mask & ~zero))}
    return result


def run(run_id: str) -> None:
    head = checked_workspace()
    baseline = prior_evidence()
    source = trusted_source()
    before = file_fingerprint(source)
    if before != baseline:
        raise RuntimeError("Aligned source fingerprint changed since S00C")
    run_dir = ROOT / "reports/runs" / run_id
    if run_dir.exists():
        raise RuntimeError("Run ID already exists")
    (run_dir / "public").mkdir(parents=True)
    write_json(run_dir / "public/SOURCE_HASH_BEFORE.json", before)
    with source.open("rb") as stream:
        container = pickle.load(stream)
    if not isinstance(container, dict):
        raise RuntimeError("Official aligned container is not a dictionary")
    # Test resides in the deserialized container but is never indexed or inspected.
    train = create_aligned_dataset(container, "train")
    valid = create_aligned_dataset(container, "valid")
    expected_counts = {"train": 3395, "valid": 728}
    if len(train) != expected_counts["train"] or len(valid) != expected_counts["valid"]:
        raise RuntimeError("Official aligned train/valid count changed")
    for dataset in (train, valid):
        for name, expected in (("text", "float32"), ("audio", "float64"), ("vision", "float64")):
            if str(getattr(dataset, name).dtype) != expected:
                raise RuntimeError(f"Official aligned {dataset.split}/{name} dtype changed")
    reports = {}
    reports["contract_summary.json"] = {
        "interface": "aligned_50.pkl", "status": "FROZEN_FOR_BASELINE", "s00c_dependency_run": S00C_RUN,
        "splits": {ds.split: {"sample_count": len(ds), "source_shapes": {name: list(getattr(ds, name).shape) for name in ("text", "audio", "vision")},
                              "source_dtypes": {name: str(getattr(ds, name).dtype) for name in ("text", "audio", "vision")},
                              "text_bert_mask_source": "channel 1; metadata only", "finite_features": True,
                              "support_contiguous_positive_prefix": True} for ds in (train, valid)},
        "test": "LOCKED_QUARANTINED; no split indexing", "attachment3_4": "content not opened"}
    reports["mask_summary.json"] = {ds.split: _mask_summary(ds) for ds in (train, valid)}
    reports["mask_summary.json"]["semantics"] = {"support": "text_bert channel 1 == 1",
        "observed_text": "support", "observed_audio_vision": "support AND NOT structural_zero",
        "padding": "NOT support", "corruption": "separate explicit all-false default",
        "structural_zero": "stored exact all-dimension zero; no missing interpretation"}
    reports["label_contract.json"] = {"class_map": {"0": "Negative", "1": "Neutral", "2": "Positive"},
        "regression_range": [-3, 3], "neutral_rule": "exactly zero",
        "train_valid_mapping_verified": True, "train_valid_finite": True,
        "test_labels": "not accessed"}
    identity = IdentityNormalizer().fit(train)
    zscore = TrainOnlyZScoreNormalizer().fit(train)
    train_batch = next(training_batches(train, 16, seed=20260924))
    valid_batch = next(valid.iter_batches(16))
    transformed = zscore.transform(valid_batch)
    identity.transform(valid_batch)
    if any(not np.all(np.isfinite(getattr(transformed, n))) for n in ("text", "audio", "vision")):
        raise RuntimeError("Non-finite transformed valid batch")
    if any(not np.array_equal(getattr(transformed, n)[~getattr(valid_batch, f"{n}_observed_mask")],
                              getattr(valid_batch, n)[~getattr(valid_batch, f"{n}_observed_mask")]) for n in ("text", "audio", "vision")):
        raise RuntimeError("Normalization changed non-observed vectors")
    reports["normalization_contract.json"] = {"fit_split": "train", "final_choice": "UNDECIDED",
        "identity": identity.state_dict(), "train_only_z_score": zscore.state_dict(),
        "valid_transform_finite": True, "non_observed_values_preserved": True,
        "test_and_special_sets_fit": "forbidden"}
    pool = masked_mean(train_batch.text, train_batch.text_support_mask)
    if pool.shape != (16, 768) or not np.all(np.isfinite(pool)):
        raise RuntimeError("Masked text pooling failed")
    reports["loader_contract.json"] = {"train_batch_size": len(train_batch.classification_target),
        "valid_batch_size": len(valid_batch.classification_target),
        "model_input_shapes": {k: list(v.shape) for k, v in train_batch.model_inputs.items()},
        "model_input_dtypes": {k: str(v.dtype) for k, v in train_batch.model_inputs.items()},
        "target_shapes": {k: list(v.shape) for k, v in train_batch.targets.items()},
        "target_dtypes": {k: str(v.dtype) for k, v in train_batch.targets.items()},
        "model_input_allowed_only": True, "masked_text_pool_shape": list(pool.shape),
        "pytorch_bridge": "available in AlignedBatch.to_torch; runtime not required for S00D"}
    after = file_fingerprint(source)
    if after != before:
        raise RuntimeError("CRITICAL_DATA_MUTATION: aligned source changed")
    write_json(run_dir / "public/SOURCE_HASH_AFTER.json", after)
    reports["source_mutation_check.json"] = {"before": before, "after": after, "unchanged": True,
                                               "CRITICAL_DATA_MUTATION": False}
    for name, value in reports.items():
        write_json(ROOT / REPORT / name, value)
    write_json(run_dir / "RUN.json", {"task_id": TASK_ID, "run_id": run_id, "status": "REAL_AUDIT_COMPLETE_PENDING_GATE",
        "data_kind": "real_official_local", "command": f"python tools/s00d_contract_run.py --run-id {run_id}",
        "stage_activation_commit": head, "s00c_dependency_run": S00C_RUN,
        "source_file": "aligned_50.pkl", "source_unchanged": True,
        "split_usage": {"train": "contract audit and normalizer fit", "valid": "contract audit and transform only",
                        "test": "quarantined; not indexed"},
        "attachment3_content_inspected": False, "attachment4_content_inspected": False,
        "model_training_performed": False, "next_stage_authorized": False,
        "sample_counts": expected_counts, "environment": {"python": platform.python_version(), "numpy": np.__version__}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run(args.run_id)
    print(json.dumps({"run_id": args.run_id, "status": "REAL_AUDIT_COMPLETE_PENDING_GATE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
