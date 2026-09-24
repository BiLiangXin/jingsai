"""One command interface; no CLI flag can grant official execution authority."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("synthetic", "official"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--architecture", default="R2")
    parser.add_argument("--device", choices=("cpu", "cuda"))
    args = parser.parse_args(argv)
    from mosei.s01.authorization import require_official_authority
    config = json.loads((ROOT / "configs/s01_execution.json").read_text(encoding="utf-8"))
    if args.mode == "official":
        device = args.device or config["device"]
        require_official_authority(config, split="train", optimizer=True, output_dir=args.output_dir,
                                   device=device, launch=True)
        from mosei.s01.contracts import configure_runtime
        configure_runtime()
        if args.source is None:
            raise ValueError("Authorized execution requires an explicit private source")
        from mosei.s01.execution import execute_core
        execute_core(config, args.source, args.output_dir, device=device)
        return 0
    if args.source is not None:
        raise ValueError("Synthetic mode accepts no data path")
    import torch
    from mosei.s01.contracts import configure_runtime, synthetic_batch
    from mosei.s01.engine import fit
    from mosei.s01.normalization import Normalizer
    from mosei.s01.registry import recipe
    configure_runtime()
    train, valid = synthetic_batch(8, 101), synthetic_batch(4, 102)
    norm = Normalizer("identity").fit([train], split="train")
    _, result = fit(train, valid, norm, recipe(args.architecture, "identity", 17),
                    output_dir=args.output_dir, provenance=dict(kind="SYNTHETIC_ONLY", fixture_seeds=[101, 102]),
                    data_kind="SYNTHETIC_ONLY", device=args.device or "cpu")
    print(json.dumps(dict(status="PASS", kind="SYNTHETIC_ONLY", classification="NOT_MODEL_EXPERIMENT",
                          architecture=args.architecture, completed_epochs=result["evaluated_epochs"],
                          checkpoint_roundtrip=True, predictive_metrics=None, official_data_loaded=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
