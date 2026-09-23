"""Fail-closed publication of an already authorized and accepted stage.

One invocation performs the public-file scan, exact Git staging, ordinary
commits/pushes, Review Release verification, and stable latest-run indexing.
It does not run a research stage or infer authorization from the presence of
outputs. The stage runner supplies an exact-file HANDOFF_INPUTS.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath

from mosei_flow import forbidden_path, make_review_zip, scan_file, scan_text, sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "codex/mosei-auto"
ORIGIN = "https://github.com/BiLiangXin/jingsai.git"
STAGE = re.compile(r"S\d{2}[A-Z]?\Z")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{4,100}\Z")
RAW_ID = re.compile(r"(?<![\w])[-_A-Za-z0-9]{5,}\$_\$\d+\b")
FORBIDDEN_JSON_KEYS = {"sample_ids", "raw_ids", "raw_text_dump", "token_ids_dump", "sample_level_labels", "test_label_distribution"}
TEST_DISTRIBUTION_KEYS = {"distribution", "histogram", "class_counts", "negative_count", "neutral_count", "positive_count", "mean", "std", "quantiles", "sample_labels"}
PUBLIC_SUFFIXES = {".md", ".json", ".csv", ".py", ".toml", ".yaml", ".yml"}


class HandoffError(RuntimeError):
    pass


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode:
        raise HandoffError(f"Command failed ({result.returncode}): {args[0]} {args[1] if len(args) > 1 else ''}: {result.stderr.strip()}")
    return result


def git(*args: str, check: bool = True) -> str:
    return command("git", *args, check=check).stdout.strip()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HandoffError(f"Expected JSON object: {path.name}")
    return value


def spec_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*([^\r\n]+)", text)
    return match.group(1).strip().strip("`").strip("'").strip(chr(34)) if match else None


def verify_workspace() -> str:
    if not (ROOT / ".git").is_dir():
        raise HandoffError("Use the verified official clone, not a linked worktree")
    if Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT.resolve():
        raise HandoffError("Repository root mismatch")
    if git("config", "--local", "--get", "mosei.officialWorkspace", check=False).lower() != "true":
        raise HandoffError("Official workspace marker missing; verify clone, then set local mosei.officialWorkspace=true")
    if git("remote", "get-url", "origin") != ORIGIN or git("branch", "--show-current") != BRANCH:
        raise HandoffError("Wrong origin or branch")
    local = git("rev-parse", "HEAD")
    remote = git("ls-remote", "--heads", "origin", BRANCH).split()
    if not remote or remote[0] != local:
        raise HandoffError("Remote HEAD differs; synchronize safely before publication")
    if git("diff", "--cached", "--name-only"):
        raise HandoffError("Pre-existing staged changes must be reviewed separately")
    if command("gh", "auth", "status", check=False).returncode:
        raise HandoffError("GitHub CLI authentication unavailable")
    return local


def public_path(relative: str, run_id: str, stage: str, root: Path = ROOT) -> Path:
    if not isinstance(relative, str) or "\\" in relative or not relative or relative.startswith("/"):
        raise HandoffError("Public path must be a relative POSIX path")
    parts = PurePosixPath(relative).parts
    if ".." in parts or "." in parts or (len(parts) < 2 and relative not in {"CHATGPT_REVIEW.md", "README_CODEX.md"}):
        raise HandoffError(f"Unsafe public path: {relative}")
    if forbidden_path(relative) or {x.lower() for x in parts} & {"private", "artifacts"} or PurePosixPath(relative).suffix.lower() not in PUBLIC_SUFFIXES:
        raise HandoffError(f"Forbidden public path: {relative}")
    allowed = (
        relative == "CHATGPT_REVIEW.md"
        or relative == "README_CODEX.md"
        or relative.startswith("docs/")
        or relative.startswith("src/mosei/")
        or relative.startswith("tests/")
        or relative.startswith("tools/")
        or relative.startswith("configs/")
        or relative.startswith(f"reports/runs/{run_id}/")
        or relative.startswith(f"reports/stages/{stage}/")
        or relative.startswith("reports/data_audit/")
        or relative.startswith("reports/experiments/")
    )
    if not allowed:
        raise HandoffError(f"Path outside publication allowlist: {relative}")
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise HandoffError(f"Missing, linked, or escaping public file: {relative}")
    return path


def scan_json(value: object, in_test: bool = False) -> list[str]:
    findings = []
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            if lower in FORBIDDEN_JSON_KEYS:
                findings.append(f"forbidden_json_key:{key}")
            if in_test and lower in TEST_DISTRIBUTION_KEYS:
                findings.append(f"test_distribution_key:{key}")
            if lower == "raw_text" and isinstance(item, list):
                findings.append("raw_text_array")
            if lower in {"labels", "classification_labels", "regression_labels"} and isinstance(item, list):
                findings.append("sample_level_label_array")
            findings.extend(scan_json(item, in_test or lower == "test" or lower.startswith("test_") or lower.endswith("_test")))
    elif isinstance(value, list):
        for item in value:
            findings.extend(scan_json(item, in_test))
    return findings


def scan_public(path: Path) -> list[str]:
    issues = scan_file(path)
    if issues:
        return issues
    content = path.read_text(encoding="utf-8")
    if RAW_ID.search(content):
        issues.append("raw_sample_id")
    if path.suffix.lower() == ".json":
        issues.extend(scan_json(json.loads(content)))
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as stream:
            header = next(csv.reader(stream), [])
        if {x.lower() for x in header} & {"id", "sample_id", "video_id", "clip_id", "raw_text", "token_ids", "label", "regression_label"}:
            issues.append("sample_level_csv_columns")
    return sorted(set(issues))


def validate_acceptance(path: Path, stage: str) -> None:
    acceptance = load_json(path)
    actual_stage = acceptance.get("stage")
    if actual_stage != stage and not (isinstance(actual_stage, str) and actual_stage.startswith(stage + "_")):
        raise HandoffError("Stage acceptance ID mismatch")
    evidence = acceptance.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise HandoffError("Missing acceptance evidence")
    for item in evidence:
        relative = item.get("path")
        if not isinstance(relative, str):
            raise HandoffError("Invalid acceptance path")
        parts = PurePosixPath(relative).parts
        if relative.startswith("/") or "\\" in relative or ".." in parts or forbidden_path(relative) or {x.lower() for x in parts} & {"private", "artifacts"}:
            raise HandoffError(f"Unsafe acceptance path: {relative}")
        target = ROOT / relative
        if not target.is_file() or not target.resolve().is_relative_to(ROOT.resolve()) or sha256(target) != item.get("sha256"):
            raise HandoffError(f"Acceptance hash mismatch: {relative}")


def validate_run(manifest: dict, root: Path = ROOT) -> tuple[list[str], Path]:
    stage = manifest.get("stage")
    run_id = manifest.get("run_id")
    task_id = manifest.get("task_id")
    if not isinstance(stage, str) or not STAGE.fullmatch(stage) or not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise HandoffError("Invalid stage or run ID")
    if not isinstance(task_id, str) or not task_id.startswith(stage + "_"):
        raise HandoffError("Task ID does not match stage")
    spec = (root / "TASK_SPEC.md").read_text(encoding="utf-8")
    if spec_scalar(spec, "task_id") != task_id or spec_scalar(spec, "status") != "ACTIVE" or spec_scalar(spec, "research_authorized") != "true":
        raise HandoffError("Current TASK_SPEC does not authorize this stage")
    run_dir = root / "reports" / "runs" / run_id
    run = load_json(run_dir / "RUN.json")
    gate = load_json(run_dir / "GATE.json")
    tests = load_json(run_dir / "TEST_RESULTS.json")
    if run.get("task_id") != task_id or run.get("data_kind") not in {"official", "real_official_local"}:
        raise HandoffError("Real official run evidence required")
    if gate.get("passed") is not True or gate.get("summary", {}).get("FAIL", 0) or gate.get("summary", {}).get("BLOCKED", 0) or gate.get("status", "PASS") != "PASS":
        raise HandoffError("Stage Gate did not pass")
    if tests.get("exit_code") != 0 or tests.get("failed") != 0 or not isinstance(tests.get("passed"), int) or tests["passed"] < 1:
        raise HandoffError("Actual engineering tests did not pass")
    validate_acceptance(root / "reports" / "stages" / stage / "acceptance.json", stage)
    files = manifest.get("public_files")
    if not isinstance(files, list) or not all(isinstance(x, str) for x in files):
        raise HandoffError("Manifest requires exact public_files list")
    required = ["CHATGPT_REVIEW.md", f"reports/runs/{run_id}/RUN.json", f"reports/runs/{run_id}/GATE.json", f"reports/runs/{run_id}/TEST_RESULTS.json", f"reports/stages/{stage}/acceptance.json", f"reports/runs/{run_id}/public/HANDOFF_INPUTS.json"]
    files = list(dict.fromkeys(required + files))
    findings = {name: issues for name in files if (issues := scan_public(public_path(name, run_id, stage, root)))}
    if findings:
        raise HandoffError(f"Public safety scan failed: {findings}")
    return files, run_dir


def exact_stage(paths: list[str], message: str) -> str:
    print(git("status", "--short"))
    command("git", "add", "--", *paths)
    staged = git("diff", "--cached", "--name-only", "-z").split("\0")
    staged = [x for x in staged if x]
    if not staged or not set(staged) <= set(paths):
        raise HandoffError("Staged paths differ from the explicit allowlist")
    print(git("diff", "--cached", "--name-status"))
    if command("git", "diff", "--cached", "--check", check=False).returncode:
        raise HandoffError("Staged diff has whitespace errors")
    for name in staged:
        path = public_path(name, _run_from_path(paths), _stage_from_path(paths)) if name != "state/LATEST_RUN.json" else ROOT / name
        issues = scan_public(path)
        staged_text = git("show", f":{name}")
        issues.extend(scan_text(staged_text))
        if RAW_ID.search(staged_text):
            issues.append("raw_sample_id_in_index")
        if issues:
            raise HandoffError(f"Staged public safety check failed for {name}: {issues}")
    command("git", "commit", "-m", message)
    return git("rev-parse", "HEAD")


def _run_from_path(paths: list[str]) -> str:
    return next(x.split("/")[2] for x in paths if x.startswith("reports/runs/"))


def _stage_from_path(paths: list[str]) -> str:
    return next(x.split("/")[2] for x in paths if x.startswith("reports/stages/"))


def push_and_verify(commit_sha: str) -> None:
    command("git", "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    remote = git("ls-remote", "--heads", "origin", BRANCH).split()
    if not remote or remote[0] != commit_sha:
        raise HandoffError("Remote branch HEAD verification failed")


def release_and_verify(run_id: str, implementation_sha: str, asset: Path, run_dir: Path) -> dict:
    tag = f"codex-run-{run_id}"
    existing = command("gh", "release", "view", tag, "--repo", "BiLiangXin/jingsai", "--json", "tagName,targetCommitish,assets,url,isDraft", check=False)
    if existing.returncode == 0:
        raise HandoffError("Release tag already exists; inspect it before retrying")
    command("gh", "release", "create", tag, str(asset), "--repo", "BiLiangXin/jingsai", "--target", implementation_sha, "--title", tag, "--notes", f"Authorized stage review for {run_id}")
    view = load_release(tag)
    remote_asset = next((x for x in view.get("assets", []) if x.get("name") == asset.name), None)
    if view.get("targetCommitish") != implementation_sha or not remote_asset or remote_asset.get("size") != asset.stat().st_size:
        raise HandoffError("Release target or asset size verification failed")
    tag_ref = git("ls-remote", "--tags", "origin", tag).split()
    if not tag_ref or tag_ref[0] != implementation_sha:
        raise HandoffError("Remote tag target verification failed")
    verify_dir = run_dir / "private" / f"release-verify-{uuid.uuid4().hex[:8]}"
    verify_dir.mkdir(parents=True, exist_ok=False)
    command("gh", "release", "download", tag, "--repo", "BiLiangXin/jingsai", "--pattern", asset.name, "--dir", str(verify_dir))
    local_hash = sha256(asset)
    downloaded_hash = sha256(verify_dir / asset.name)
    if local_hash != downloaded_hash or (remote_asset.get("digest") and remote_asset["digest"] != f"sha256:{local_hash}"):
        raise HandoffError("Downloaded asset SHA256 mismatch")
    return {"tag": tag, "url": view["url"], "target": implementation_sha, "asset_name": asset.name, "asset_size_bytes": asset.stat().st_size, "local_sha256": local_hash, "downloaded_sha256": downloaded_hash}


def load_release(tag: str) -> dict:
    return json.loads(command("gh", "release", "view", tag, "--repo", "BiLiangXin/jingsai", "--json", "tagName,targetCommitish,assets,url,isDraft").stdout)


def set_review_field(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:\s*.*$")
    replacement = f"{key}: `{value}`"
    return pattern.sub(replacement, text, count=1) if pattern.search(text) else text.replace("\n", "\n" + replacement + "\n", 1)


def refresh_acceptance(stage: str, run_id: str, new_paths: list[str]) -> None:
    path = ROOT / "reports" / "stages" / stage / "acceptance.json"
    value = load_json(path)
    entries = {x["path"]: x for x in value["evidence"]}
    for relative in new_paths:
        entries[relative] = {"requirement": PurePosixPath(relative).name, "path": relative, "sha256": sha256(ROOT / relative)}
    for entry in entries.values():
        entry["sha256"] = sha256(ROOT / entry["path"])
    value["evidence"] = list(entries.values())
    write_json(path, value)


def latest_index(stage: str, task_id: str, run_id: str, implementation: str, metadata: str, release: dict, evidence: list[str]) -> dict:
    return {
        "schema_version": 1,
        "latest_completed_stage": stage,
        "task_id": task_id,
        "run_id": run_id,
        "repository": "BiLiangXin/jingsai",
        "branch": BRANCH,
        "branch_head": {"ref": f"refs/heads/{BRANCH}", "verified_stage_completion_sha": metadata},
        "implementation_commit": implementation,
        "metadata_commit": metadata,
        "release": release,
        "review_path": "CHATGPT_REVIEW.md",
        "core_public_evidence_paths": evidence,
        "next_stage_authorized": False,
        "handoff_status": "PENDING_RESEARCH_REVIEW",
    }


def publish(manifest_path: Path) -> dict:
    initial_head = verify_workspace()
    expected_manifest = manifest_path.resolve()
    manifest = load_json(expected_manifest)
    stage, run_id, task_id = manifest["stage"], manifest["run_id"], manifest["task_id"]
    if expected_manifest != (ROOT / "reports" / "runs" / run_id / "public" / "HANDOFF_INPUTS.json").resolve():
        raise HandoffError("Manifest must reside in the corresponding run/public directory")
    latest_path = ROOT / "state" / "LATEST_RUN.json"
    if latest_path.is_file() and load_json(latest_path).get("run_id") == run_id:
        raise HandoffError("This run is already indexed as completed; no duplicate publication")
    release_probe = command("gh", "release", "view", f"codex-run-{run_id}", "--repo", "BiLiangXin/jingsai", "--json", "tagName", check=False)
    if release_probe.returncode == 0:
        raise HandoffError("Release tag already exists; inspect it before any Git write")
    if "not found" not in release_probe.stderr.lower():
        raise HandoffError("Cannot confirm Release tag availability")
    files, run_dir = validate_run(manifest)
    existing_changes = set(git("status", "--porcelain", "--untracked-files=all").splitlines())
    for line in existing_changes:
        if line and line[3:].replace("\\", "/") not in files:
            raise HandoffError("Unrelated workspace changes present; review them before publication")
    manifest_rows = [{"path": x, "size": (ROOT / x).stat().st_size, "sha256": sha256(ROOT / x)} for x in files]
    manifest_relative = f"reports/runs/{run_id}/MANIFEST.json"
    write_json(ROOT / manifest_relative, {"stage": stage, "run_id": run_id, "files": manifest_rows})
    if scan_public(ROOT / manifest_relative):
        raise HandoffError("Generated public manifest failed safety scan")
    files.append(manifest_relative)
    implementation = exact_stage(files, f"{stage} publish implementation {run_id}")
    push_and_verify(implementation)
    asset = run_dir / "artifacts" / f"review-{run_id}.zip"
    make_review_zip(asset, [ROOT / x for x in files])
    release = release_and_verify(run_id, implementation, asset, run_dir)
    receipt_relative = f"reports/runs/{run_id}/PUBLISH_RECEIPT.json"
    test_record = load_json(run_dir / "TEST_RESULTS.json")
    receipt = {"run_id": run_id, "stage": stage, "branch": BRANCH, "baseline_sha": initial_head, "implementation_commit": implementation, "implementation_staged_files": files, "actual_tests": {key: test_record.get(key) for key in ("command", "exit_code", "passed", "failed")}, "gate": load_json(run_dir / "GATE.json")["summary"], "release": release, "implementation_push_result": "PASS", "remote_asset_verified": True}
    write_json(ROOT / receipt_relative, receipt)
    review_path = ROOT / "CHATGPT_REVIEW.md"
    review = review_path.read_text(encoding="utf-8")
    for key, value in (("status", "PUBLICATION_VERIFIED_PENDING_INDEX"), ("implementation_commit", implementation), ("release_url", release["url"]), ("release_tag", release["tag"]), ("review_asset", release["asset_name"])):
        review = set_review_field(review, key, value)
    review += f"\n## Verified automatic handoff\n\nRelease target: `{implementation}`. Asset SHA256: `{release['local_sha256']}`. Downloaded SHA256 matches. Stage remains `PENDING_RESEARCH_REVIEW`; `NEXT_STAGE_NOT_AUTHORIZED`.\n"
    review_path.write_text(review, encoding="utf-8")
    run_record = load_json(run_dir / "RUN.json")
    run_record.update({"implementation_commit": implementation, "release_url": release["url"], "status": "PUBLICATION_VERIFIED_PENDING_INDEX"})
    write_json(run_dir / "RUN.json", run_record)
    refresh_acceptance(stage, run_id, [receipt_relative, f"reports/runs/{run_id}/RUN.json"])
    metadata_paths = [receipt_relative, "CHATGPT_REVIEW.md", f"reports/runs/{run_id}/RUN.json", f"reports/stages/{stage}/acceptance.json"]
    for x in metadata_paths:
        if scan_public(ROOT / x):
            raise HandoffError(f"Metadata safety scan failed: {x}")
    metadata = exact_stage(metadata_paths, f"{stage} record verified release {run_id}")
    push_and_verify(metadata)
    review = set_review_field(review_path.read_text(encoding="utf-8"), "status", "SUCCESS")
    review = set_review_field(review, "metadata_commit", metadata)
    review_path.write_text(review, encoding="utf-8")
    evidence = [x for x in files if x.startswith("docs/") or x.startswith("reports/data_audit/") or x.startswith(f"reports/stages/{stage}/")]
    evidence += [f"reports/runs/{run_id}/RUN.json", f"reports/runs/{run_id}/GATE.json", f"reports/runs/{run_id}/TEST_RESULTS.json", f"reports/runs/{run_id}/MANIFEST.json", receipt_relative]
    index = latest_index(stage, task_id, run_id, implementation, metadata, release, list(dict.fromkeys(evidence)))
    write_json(ROOT / "state" / "LATEST_RUN.json", index)
    final_paths = ["CHATGPT_REVIEW.md", "state/LATEST_RUN.json"]
    for x in final_paths:
        if scan_public(ROOT / x):
            raise HandoffError(f"Final safety scan failed: {x}")
    index_commit = exact_stage(final_paths + [f"reports/runs/{run_id}/GATE.json", f"reports/stages/{stage}/acceptance.json"], f"{stage} update latest-run index {run_id}")
    push_and_verify(index_commit)
    final_release = load_release(release["tag"])
    if final_release.get("targetCommitish") != implementation or not any(x.get("name") == release["asset_name"] and x.get("size") == release["asset_size_bytes"] for x in final_release.get("assets", [])):
        raise HandoffError("Final Release verification failed")
    return {"stage": stage, "run_id": run_id, "implementation_commit": implementation, "metadata_commit": metadata, "index_commit": index_commit, "release": release, "branch_head_ref": index["branch_head"]["ref"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True, help="Exact-file manifest at reports/runs/<run_id>/public/HANDOFF_INPUTS.json")
    args = parser.parse_args()
    try:
        result = publish(args.manifest)
    except (HandoffError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"HANDOFF_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
