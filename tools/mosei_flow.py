"""Small, auditable S00A engineering flow. No competition data is read."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASELINE = "50cd572e47274903b43230dcd3add65f34447c84"
ORIGIN = "https://github.com/BiLiangXin/jingsai.git"
FORBIDDEN_NAMES = {".env", "paths.local.json"}
FORBIDDEN_SUFFIXES = {".pkl", ".mp4", ".xlsx", ".xls", ".pt", ".pth", ".ckpt"}
PRIVATE_PATH = re.compile(r"(?i)[a-z]:[/\\]users[/\\][^/\\\s]+")
SECRET = re.compile(r"(?i)(?:(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|(?:token|api[_-]?key|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,})")
ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def forbidden_path(path: str) -> bool:
    name = path.replace("\\", "/").lower()
    pieces = name.split("/")
    return ("e题数据" in pieces or ".git" in pieces or
            pieces[-1] in FORBIDDEN_NAMES or pieces[-1].startswith(".env.") or
            Path(name).suffix in FORBIDDEN_SUFFIXES or
            any(piece in {"credentials", "tokens", "__pycache__", ".pytest_cache", ".cache"} for piece in pieces))


def scan_text(value: str) -> list[str]:
    findings = []
    if PRIVATE_PATH.search(value):
        findings.append("private_windows_path")
    if SECRET.search(value):
        findings.append("secret_pattern")
    return findings


def scan_file(path: Path) -> list[str]:
    if forbidden_path(path.as_posix()):
        return ["forbidden_path"]
    if path.stat().st_size > 1024 * 1024:
        return ["oversize"]
    try:
        return scan_text(path.read_text(encoding="utf-8"))
    except UnicodeError:
        return ["binary_or_unknown"]


def safe_tree(paths: list[Path], root: Path = ROOT) -> dict[str, list[str]]:
    findings = {}
    for path in paths:
        rel = path.relative_to(root).as_posix()
        issues = scan_file(path)
        if issues:
            findings[rel] = issues
    return findings


def verify_baseline(expected: str = BASELINE, url: str = ORIGIN) -> dict[str, object]:
    result = run("git", "ls-remote", url, "refs/heads/main")
    actual = result.stdout.split()[0] if result.returncode == 0 and result.stdout.strip() else None
    return {"command": "git ls-remote <origin> refs/heads/main", "expected": expected,
            "actual": actual, "status": "PASS" if actual == expected else "BLOCKED",
            "exit_code": result.returncode}


def doctor() -> dict[str, object]:
    git = shutil.which("git")
    gh = shutil.which("gh")
    head = run("git", "rev-parse", "HEAD").stdout.strip() if git else None
    branch = run("git", "branch", "--show-current").stdout.strip() if git else None
    origin = run("git", "remote", "get-url", "origin").stdout.strip() if git else None
    tracked = run("git", "ls-files", "-z").stdout.split("\0") if git else []
    dangerous = [p for p in tracked if p and forbidden_path(p)]
    ignored = run("git", "check-ignore", "-q", "E题数据/sentinel.pkl").returncode == 0 if git else False
    auth = run("gh", "auth", "status").returncode == 0 if gh else False
    files = ["AGENTS.md", "DECISIONS.md", "TASK_SPEC.md", "CHATGPT_REVIEW.md"]
    governance = {p: (ROOT / p).is_file() for p in files}
    local_config = ROOT / "configs" / "paths.local.json"
    report = {"python": sys.version.split()[0], "repo_root": "<official_repo>", "git_available": bool(git),
              "origin": origin, "branch": branch, "head": head, "expected_main_sha": BASELINE,
              "main_baseline": run("git", "rev-parse", "main").stdout.strip() == BASELINE if git else False,
              "gh_available": bool(gh), "gh_authenticated": auth, "release_capable": bool(gh and auth),
              "governance": governance, "raw_data_ignored": ignored, "dangerous_tracked": dangerous,
              "local_path_config": "present" if local_config.exists() else "absent",
              "tracked_secret_or_private_path_findings": safe_tree([ROOT / p for p in tracked if p and (ROOT / p).is_file() and Path(p).suffix.lower() not in {".docx", ".png", ".jpg", ".jpeg"}])}
    return report


def gate(items: list[dict[str, object]]) -> dict[str, object]:
    legal = {"PASS", "FAIL", "SKIPPED", "BLOCKED"}
    if any(x.get("status") not in legal for x in items):
        raise ValueError("Invalid gate status")
    if any(x.get("status") == "PASS" and not x.get("evidence") for x in items):
        raise ValueError("PASS requires evidence")
    counts = {s: sum(x.get("status") == s for x in items) for s in legal}
    return {"items": items, "summary": counts, "passed": counts["FAIL"] == counts["BLOCKED"] == 0}


def archive(run_dir: Path, data: dict[str, object], files: list[Path]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "RUN.json", data)
    entries = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha256(p), "size": p.stat().st_size} for p in files]
    write_json(run_dir / "MANIFEST.json", entries)
    (run_dir / "SHA256SUMS.txt").write_text("".join(f"{x['sha256']}  {x['path']}\n" for x in entries), encoding="utf-8")


def make_review_zip(path: Path, files: list[Path], root: Path = ROOT) -> dict[str, object]:
    issues = safe_tree(files, root)
    if issues:
        raise ValueError(f"Unsafe review inputs: {issues}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for file in files:
            output.write(file, file.relative_to(root).as_posix())
    with zipfile.ZipFile(path) as check:
        names = check.namelist()
        if any(forbidden_path(n) or scan_text(check.read(n).decode("utf-8", errors="ignore")) for n in names):
            path.unlink()
            raise ValueError("Unsafe ZIP content")
    return {"path": path.name, "sha256": sha256(path), "size": path.stat().st_size, "members": names}


def publish_dry_run(run_id: str, existing_tags: set[str], changed: bool) -> dict[str, object]:
    tag = f"codex-run-{run_id}"
    return {"tag": tag, "create_release": tag not in existing_tags,
            "create_commit": bool(changed), "status": "EXISTS" if tag in existing_tags else "WOULD_CREATE"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["doctor", "baseline", "gate", "archive", "package", "publish", "publish-dry-run"])
    parser.add_argument("--run-id")
    parser.add_argument("--target", help="Exact implementation commit SHA for publish")
    args = parser.parse_args()
    if args.command == "doctor":
        report = doctor()
        write_json(ROOT / "reports" / "bootstrap" / "DOCTOR.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["main_baseline"] and report["raw_data_ignored"] and not report["dangerous_tracked"] else 1
    if args.command == "baseline":
        report = verify_baseline()
        print(json.dumps(report))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "publish":
        raise SystemExit("Legacy publish is disabled. Use tools/stage_handoff.py with an authorized HANDOFF_INPUTS.json manifest.")
    if not args.run_id:
        parser.error("--run-id is required")
    run_dir = ROOT / "reports" / "runs" / args.run_id
    if args.command == "gate":
        path = run_dir / "GATE.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps(report["summary"]))
        return 0 if report["passed"] else 1
    if args.command == "archive":
        from s00a_report import create
        create(args.run_id)
        print(run_dir.relative_to(ROOT).as_posix())
        return 0
    if args.command == "package":
        names = ["CHATGPT_REVIEW.md", "AGENTS.md", "DECISIONS.md", "TASK_SPEC.md",
                 "reports/bootstrap/MIGRATION_INVENTORY.csv", "reports/bootstrap/MIGRATION_NOTES.md"]
        names += [f"reports/runs/{args.run_id}/{name}" for name in
                  ("SUMMARY.md", "RUN.json", "GATE.json", "TEST_RESULTS.json", "MANIFEST.json", "MIGRATION_SUMMARY.md", "SHA256SUMS.txt", "ARTIFACTS.json")]
        path = run_dir / "artifacts" / f"review-{args.run_id}.zip"
        result = make_review_zip(path, [ROOT / name for name in names])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.command == "publish-dry-run":
        existing = run("gh", "release", "list", "--json", "tagName", "--limit", "100").stdout
        try:
            tags = {x["tagName"] for x in json.loads(existing)}
        except (ValueError, KeyError):
            tags = set()
        changed = bool(run("git", "status", "--porcelain").stdout.strip())
        print(json.dumps(publish_dry_run(args.run_id, tags, changed)))
        return 0
    parser.error("Unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
