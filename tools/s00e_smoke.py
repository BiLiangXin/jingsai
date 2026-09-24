"""S00E read-only aligned TRAIN bridge/pooling/backward smoke; no model training."""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import platform
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np

from mosei_flow import write_json
from stage_handoff import BRANCH, ORIGIN, spec_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mosei.data.dataset import create_aligned_dataset  # noqa: E402
from mosei.data.pooling import masked_mean  # noqa: E402

TASK_ID = "S00E_S01_PRESTART_ENGINEERING_HARDENING"
INPUT_FIELDS = ("text", "audio", "vision", "text_bert", "classification_labels", "regression_labels")


def file_fingerprint(path: Path) -> dict:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"file_name": path.name, "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "sha256": digest.hexdigest()}


def checked_source() -> tuple[Path, dict, str]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()

    if (git("remote", "get-url", "origin") != ORIGIN or
            git("branch", "--show-current") != BRANCH or
            git("config", "--local", "--get", "mosei.officialWorkspace").lower() != "true"):
        raise RuntimeError("Verified official workspace required")
    head = git("rev-parse", "HEAD")
    remote = git("ls-remote", "origin", f"refs/heads/{BRANCH}").split()
    if not remote or remote[0] != head:
        raise RuntimeError("Local and remote branch HEAD differ")
    spec = (ROOT / "TASK_SPEC.md").read_text(encoding="utf-8")
    expected = {"task_id": TASK_ID, "status": "ACTIVE", "research_authorized": "true",
                "next_stage_authorized": "false", "s01_training_authorized": "false"}
    if any(spec_scalar(spec, key) != value for key, value in expected.items()):
        raise RuntimeError("S00E authorization mismatch")
    config = json.loads((ROOT / "configs/paths.local.json").read_text(encoding="utf-8-sig"))
    if set(config) != {"data_root", "trusted_competition_pickle"} or config["trusted_competition_pickle"] is not True:
        raise RuntimeError("Trusted local competition source configuration required")
    source = Path(config["data_root"]) / "附件2-数据集特征文件" / "aligned_50.pkl"
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Trusted aligned source unavailable")
    baseline = json.loads((ROOT / "reports/data_contract/source_mutation_check.json").read_text(encoding="utf-8"))
    if baseline.get("unchanged") is not True or baseline.get("before") != baseline.get("after"):
        raise RuntimeError("S00D source baseline is not internally consistent")
    return source, baseline["after"], head


def numpy_digest(batch) -> dict[str, str]:
    arrays = {**batch.model_inputs, **batch.targets}
    return {name: hashlib.sha256(np.asarray(value).tobytes()).hexdigest()
            for name, value in arrays.items()}


def tiny_train_smoke(container: dict) -> dict:
    """Only access the train key and six allowlisted fields; never return sample values."""
    import torch

    train = container["train"]
    tiny = {name: np.asarray(train[name])[:2].copy() for name in INPUT_FIELDS}
    dataset = create_aligned_dataset({"train": tiny}, "train")
    batch = dataset.batch([0, 1])
    before = numpy_digest(batch)
    bridge = batch.to_torch()
    if set(bridge) != {"model_inputs", "targets"} or set(bridge["targets"]) != {
            "classification_target", "regression_target"}:
        raise RuntimeError("Torch bridge target separation failed")
    if set(bridge["model_inputs"]) != set(batch.model_inputs):
        raise RuntimeError("Torch bridge input allowlist changed")
    if any(bridge["model_inputs"][name].dtype != torch.float32
           for name in ("text", "audio", "vision")):
        raise RuntimeError("Torch bridge feature dtype mismatch")
    if any(value.dtype != torch.bool for name, value in bridge["model_inputs"].items()
           if name.endswith("mask")):
        raise RuntimeError("Torch bridge mask dtype mismatch")
    if bridge["targets"]["classification_target"].dtype != torch.int64 or bridge[
            "targets"]["regression_target"].dtype != torch.float32:
        raise RuntimeError("Torch bridge target dtype mismatch")
    if any(np.shares_memory(value.numpy(), batch.model_inputs[name])
           for name, value in bridge["model_inputs"].items()):
        raise RuntimeError("Torch bridge still shares NumPy input memory")
    if any(np.shares_memory(value.numpy(), batch.targets[name])
           for name, value in bridge["targets"].items()):
        raise RuntimeError("Torch bridge still shares NumPy target memory")

    devices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
    results = {}
    torch.manual_seed(20260924)
    for device in devices:
        inputs = {name: value.to(device) for name, value in bridge["model_inputs"].items()}
        pooled = []
        for name in ("text", "audio", "vision"):
            values = inputs[name]
            support = inputs[f"{name}_support_mask"]
            result = masked_mean(values, support)
            if result.shape != (2, values.shape[-1]) or not bool(torch.isfinite(result).all()):
                raise RuntimeError("Torch pooling shape or finite check failed")
            pooled.append(result)
        features = torch.cat(pooled, dim=-1)
        layer = torch.nn.Linear(features.shape[-1], 1).to(device)
        layer(features).sum().backward()
        if layer.weight.grad is None or layer.bias.grad is None or not bool(
                torch.isfinite(layer.weight.grad).all() and torch.isfinite(layer.bias.grad).all()):
            raise RuntimeError("Throwaway linear backward gradients are not finite")
        text = inputs["text"]
        support = inputs["text_support_mask"]
        original = masked_mean(text, support)
        poisoned = text.clone()
        poisoned[~support] = 1e30
        if not bool(torch.equal(original, masked_mean(poisoned, support))):
            raise RuntimeError("Large non-support values changed pooled output")
        poisoned[~support] = float("nan")
        if not bool(torch.isfinite(masked_mean(poisoned, support)).all()):
            raise RuntimeError("Non-support NaN contaminated pooled output")
        results[device] = {"bridge": "PASS", "pooled_modalities": 3,
                           "pooled_shapes_valid": True, "masked_tail_invariant": True,
                           "masked_nan_isolated": True, "linear_backward_finite": True}
    if before != numpy_digest(batch):
        raise RuntimeError("NumPy batch mutated during Torch smoke")
    return {"batch_size": 2, "split": "train", "test_key_indexed": False,
            "attachment3_content_opened": False, "attachment4_content_opened": False,
            "numpy_batch_unchanged": True, "torch_cpu_storage_separate": True,
            "devices": results}


def run(run_id: str) -> dict:
    import torch

    source, baseline, head = checked_source()
    before = file_fingerprint(source)
    if before != baseline:
        raise RuntimeError("Official aligned source differs from S00D fingerprint")
    smoke = None
    error = None
    try:
        # The trusted pickle contains all split arrays structurally. Only train is indexed.
        with source.open("rb") as stream:
            container = pickle.load(stream)
        if not isinstance(container, dict):
            raise RuntimeError("Official aligned container is not a dictionary")
        smoke = tiny_train_smoke(container)
    except Exception as exc:
        error = type(exc).__name__
        private = ROOT / "reports" / "runs" / run_id / "private"
        private.mkdir(parents=True, exist_ok=True)
        (private / "SMOKE_ERROR.txt").write_text(traceback.format_exc(), encoding="utf-8")
    after = file_fingerprint(source)
    unchanged = after == before == baseline
    source_report = {"task_id": TASK_ID, "stage": "S00E", "run_id": run_id,
                     "before": before, "after": after,
                     "unchanged": unchanged, "CRITICAL_DATA_MUTATION": not unchanged}
    write_json(ROOT / "reports/engineering/s00e_source_mutation_check.json", source_report)
    if not unchanged:
        raise RuntimeError("CRITICAL_DATA_MUTATION: official aligned source changed")
    runtime = {"stage": "S00E", "run_id": run_id, "task_id": TASK_ID,
               "status": "PASS" if error is None else "BLOCKED",
               "data_kind": "real_official_local", "source_file": "aligned_50.pkl",
               "source_unchanged": True, "head_at_smoke": head,
               "environment": {"name": "birdAL", "python": platform.python_version(),
                               "numpy": np.__version__, "torch": torch.__version__,
                               "cuda_runtime": torch.version.cuda,
                               "cuda_available": torch.cuda.is_available(),
                               "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None},
               "official_distribution_origin_independently_verified": False,
               "container_deserialized": True, "split_indexed": "train_only",
               "smoke": smoke, "error_type": error}
    write_json(ROOT / "reports/engineering/s00e_pytorch_runtime.json", runtime)
    if error:
        raise RuntimeError(f"Official TRAIN smoke blocked: {error}; inspect local private diagnostics")
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    result = run(args.run_id)
    print(json.dumps({"run_id": result["run_id"], "status": result["status"],
                      "devices": list(result["smoke"]["devices"]),
                      "source_unchanged": result["source_unchanged"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
