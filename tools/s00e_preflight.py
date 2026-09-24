"""Read-only S00E PREPUBLICATION_SAFETY_PREFLIGHT; never commits or publishes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage_handoff import (HandoffError, load_json, sha256, validate_run, verify_workspace,
                           worktree_changed_paths)

ROOT = Path(__file__).resolve().parents[1]


def run(manifest_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    run_id = manifest.get("run_id")
    expected = (ROOT / "reports" / "runs" / str(run_id) / "public" / "HANDOFF_INPUTS.json").resolve()
    if manifest_path != expected or manifest.get("stage") != "S00E":
        raise HandoffError("S00E manifest must be the current run's public handoff input")
    verify_workspace()
    files, _ = validate_run(manifest, ROOT, preflight=True)
    if worktree_changed_paths() - set(files):
        raise HandoffError("Unlisted worktree changes block prepublication preflight")
    return {"stage": "S00E", "run_id": run_id,
            "name": "PREPUBLICATION_SAFETY_PREFLIGHT", "status": "PASS",
            "read_only": True, "e01_e20_passed": True, "review_e19_checked": True,
            "manifest_files_checked": len(files), "tracked_tree_and_index_checked": True,
            "manifest_sha256": sha256(manifest_path),
            "git_write_performed": False, "release_created": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.manifest)
    except (HandoffError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"name": "PREPUBLICATION_SAFETY_PREFLIGHT",
                          "status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
