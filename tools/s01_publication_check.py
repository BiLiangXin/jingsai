"""Read-only S01 preparation publication gate, explicit payload and index scan."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_handoff import scan_tracked_public_tree, scan_public_bytes, forbidden_path


def need(value, message):
    if not value:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest, index=False):
    m = json.loads(manifest.read_text(encoding="utf-8"))
    allowed = m["publication_files"]
    need(len(allowed) == len(set(allowed)) == len({p.casefold() for p in allowed}), "Duplicate paths")
    changed = {x.decode() for x in git("diff", "--name-only", "HEAD", "-z").split(b"\0") if x}
    untracked = {x.decode() for x in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if x}
    need(changed | untracked == set(allowed), "Unexpected worktree/index/untracked path set")
    need(git("rev-parse", "HEAD").decode().strip() == m["base_commit"], "Base HEAD changed")
    need(git("branch", "--show-current").decode().strip() == "codex/mosei-auto", "Wrong branch")
    need(git("remote", "get-url", "origin").decode().strip() == "https://github.com/BiLiangXin/jingsai.git", "Wrong remote")
    for rel in allowed:
        posix, path = PurePosixPath(rel), ROOT / rel
        need(not posix.is_absolute() and ".." not in posix.parts and ":" not in rel and "\\" not in rel, "Unsafe path")
        need(not forbidden_path(rel) and posix.suffix in (".md", ".py", ".json"), "Disallowed artifact")
        need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT), "Redirected file")
        need(path.stat().st_size < 2**20, "Unexpected large file")
        need(not scan_public_bytes(rel, path.read_bytes()), "Unsafe public content: " + rel)
    for item in m["files"]:
        path = ROOT / item["path"]
        need(sha(path) == item["sha256"] and path.stat().st_size == item["size_bytes"], "Manifest mismatch: " + item["path"])
    scan = scan_tracked_public_tree(ROOT)
    need(not scan["findings"], "Tracked/index public safety findings")
    if index:
        staged = {x.decode() for x in git("diff", "--cached", "--name-only", "-z").split(b"\0") if x}
        need(staged == set(allowed), "Staged path set differs")
        for rel in allowed:
            need(git("show", ":" + rel) == (ROOT / rel).read_bytes(), "Index/worktree byte mismatch: " + rel)
    frozen_paths = ["docs/research/R01", "research/r01", "src/mosei/data", "state/LATEST_RUN.json", "AGENTS.md", "CHATGPT_REVIEW.md"]
    need(not git("diff", "--name-only", m["base_commit"], "--", *frozen_paths).strip(), "Frozen/historical interface changed")
    contract = lambda text: [s for s in text.splitlines() if s.startswith("| D-DATA-")]
    need(contract(git("show", m["base_commit"] + ":DECISIONS.md").decode()) ==
         contract((ROOT / "DECISIONS.md").read_text(encoding="utf-8")), "Data contract changed")
    c = json.loads((ROOT / "configs/s01_execution.json").read_text(encoding="utf-8"))
    need(c["training_authorized"] is False and c["resource_cap_status"] == "PROPOSED_NUMERIC_RESOURCE_CAP", "Self authorization")
    need(c["core_budget"] == 39 and c["execution_fit_budget"] == 30, "Deadline proposal mismatch")
    records = json.loads((ROOT / "docs/EXPERIMENT_REGISTER.json").read_text(encoding="utf-8"))["s01_preregistered_fits"]
    need(len(records) == len({r["trial_id"] for r in records}) == 39, "Preregistration count")
    need(all(r["status"] == "NOT_RUN" and r["metrics"] is None and r["training_authorized"] is False for r in records), "Invented model results")
    need("E题数据/" in (ROOT / ".gitignore").read_text(encoding="utf-8"), "Data ignore removed")
    return dict(status="PASS", exit_code=0, stage="S01_PREPARATION", base_commit=m["base_commit"],
        mode="INDEX_AND_WORKTREE" if index else "TRACKED_AND_CANDIDATE", publication_file_count=len(allowed),
        verified_payload_hashes=len(m["files"]), tracked_text_files_scanned=scan["scanned_text_files"], findings=[],
        exact_staged_set_verified=index, index_equals_worktree_verified=index, data_contract_unchanged=True,
        latest_run_unchanged=True, official_model_experiments="NOT_RUN", metrics=None,
        limitations=["Pattern scanning is not a universal secret-detection proof; no original data contents read.",
                    "Self-hash and mutable safety-report exclusions are explicitly listed in MANIFEST."])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--index", action="store_true")
    args = p.parse_args()
    result = check(args.manifest, args.index)
    result["command"] = "python -B -X utf8 tools/s01_publication_check.py --manifest reports/s01_preparation/MANIFEST.json" + (" --index" if args.index else "")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
