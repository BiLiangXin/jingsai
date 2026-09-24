"""Closed synthetic full-size timing; the only inputs are output destinations."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import torch
from s01_resource_profile import environment, measure
from mosei.s01.contracts import configure_runtime, require, synthetic_batch
from mosei.s01.engine import fit
from mosei.s01.normalization import Normalizer
from mosei.s01.protocol import ValidationLibrary
from mosei.s01.registry import recipe


def fingerprint():
    files = list((ROOT / "src/mosei/s01").glob("*.py")) + [Path(__file__),
        ROOT / "tools/s01_resource_profile.py", ROOT / "research/r01/reference.py"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-output-dir", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    args = p.parse_args()
    require(not args.private_output_dir.resolve().is_relative_to(ROOT), "Checkpoints remain outside repository")
    require(not args.private_output_dir.exists() and not args.report.exists(), "Never overwrite profile evidence")
    configure_runtime()
    require(torch.cuda.is_available(), "Measured proposal requires CUDA")
    sources = fingerprint()
    value = dict(kind="SYNTHETIC_ONLY_SCALED_RESOURCE_PROFILE", classification="NOT_MODEL_EXPERIMENT",
        status="RUNNING", official_data_loaded=False, metrics=None, environment=environment(),
        aggregate_count_source="Historical public docs/S00D_DATA_CONTRACT.md only",
        train_count=3395, valid_count=728, fixture_seeds=[7301, 7302], model_seed=17,
        geometry="Every synthetic row has50 supported and observed positions; no actual data values",
        batch_size=32, actual_epochs_per_architecture=1, samples=[], source_sha256=sources)
    start = time.perf_counter()
    train, valid = synthetic_batch(3395, 7301, dense=True), synthetic_batch(728, 7302, dense=True)
    value["fixture_creation_seconds"] = time.perf_counter() - start
    start = time.perf_counter()
    normalizer = Normalizer("identity").fit([train], split="train")
    value["normalizer_fit_seconds"] = time.perf_counter() - start
    start = time.perf_counter()
    library = ValidationLibrary(valid)
    value["validation_library_seconds"] = time.perf_counter() - start
    measure("B-CAT", 32, "cuda", repeats=1)  # warm CUDA/optimizer initialization outside timed fits
    for architecture in ("B-T", "B-A", "B-V", "B-CAT", "C0", "R0"):
        start = time.perf_counter()
        model, result = fit(train, valid, normalizer, recipe(architecture, "identity", 17),
            output_dir=args.private_output_dir / architecture, provenance=dict(kind="SYNTHETIC_ONLY", fixture_seeds=[7301,7302]),
            data_kind="SYNTHETIC_ONLY", device="cuda", library=library)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        row = dict(architecture=architecture, elapsed_seconds=elapsed, **result["timing"],
                   parameters=result["parameters"], checkpoint_roundtrip=True, predictive_metrics=None)
        row["unattributed_fixed_seconds"] = max(0., elapsed - sum(row["train_epoch_seconds"]) -
            sum(row["checkpoint_validation_seconds"]) - row["final_validation_seconds"])
        value["samples"].append(row)
        print(json.dumps(row), flush=True)
        args.report.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        del model, result
        torch.cuda.empty_cache()
    require(sources == fingerprint(), "Source changed during measurement")
    value.update(status="SYNTHETIC_ONLY_COMPLETED", source_unchanged_during_measurement=True, exit_code=0,
        command="python -B -X utf8 tools/s01_scaled_profile.py --private-output-dir PRIVATE_NEW_DIRECTORY --report reports/s01_preparation/scaled_profile.json",
        command_note="PRIVATE_NEW_DIRECTORY redacts the actual external checkpoint destination; all other arguments exact.")
    args.report.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
