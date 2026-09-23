"""File-level selective inventory of the old workspace; never opens raw competition data."""
from __future__ import annotations

import csv
import os
import shutil
import sys
from pathlib import Path

from mosei_flow import ROOT, scan_file

KEEP = {"pyproject.toml", "src/mosei/provenance.py"}
RECREATE = {"AGENTS.md", "DECISIONS.md", "TASK_SPEC.md", "CHATGPT_REVIEW.md", ".gitignore", "README_CODEX.md"}
SKIP_DIRS = {".git", "E题数据", "reports", "__pycache__", ".pytest_cache", ".mypy_cache", ".cache", ".venv", "venv", "outputs", "downloads", "cache", "tmp", "temp", "jingsai_history_cleanup"}
SCANNED_DIRS = {".codex", "configs", "docs", "prompts", "schemas", "src", "tests", "tools", "paper", "experiments", "state"}


def inventory(old: Path) -> list[dict[str, str]]:
    rows = []
    for current, dirs, files in os.walk(old):
        base = Path(current)
        relative_dir = base.relative_to(old)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and (relative_dir != Path(".") or d in SCANNED_DIRS))
        for name in sorted(files):
            source = base / name
            rel = source.relative_to(old).as_posix()
            if source.is_symlink():
                flags = ["symlink"]
            else:
                flags = scan_file(source)
            if rel in KEEP and not flags:
                action, destination, reason, sanitized = "MIGRATE", rel, "Useful small engineering source; scan clean", "yes"
                target = ROOT / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            elif rel in RECREATE:
                action, destination, reason, sanitized = "RECREATE", rel, "Rebuilt for the new official workspace and current authority", "yes"
            elif flags:
                action, destination, reason, sanitized = "REVIEW_REQUIRED", "", "Candidate requires review before any migration", "no"
            else:
                action, destination, reason, sanitized = "SKIP", "", "Outside S00A minimal infrastructure or carries prior-stage assumptions", "n/a"
            rows.append({"source": rel, "destination": destination, "action": action,
                         "reason": reason, "risk_flags": ";".join(flags), "sanitized": sanitized})
    for rel in sorted(SKIP_DIRS & {p.name for p in old.iterdir() if p.is_dir()}):
        rows.append({"source": rel + "/", "destination": "", "action": "SKIP", "reason": "Excluded directory; contents not migrated", "risk_flags": "excluded", "sanitized": "n/a"})
    return sorted(rows, key=lambda row: row["source"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tools/migration_inventory.py <old-workspace>")
    old = Path(sys.argv[1]).resolve()
    if old == ROOT or not (old / "AGENTS.md").is_file():
        raise SystemExit("Invalid old workspace")
    rows = inventory(old)
    target = ROOT / "reports" / "bootstrap" / "MIGRATION_INVENTORY.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source", "destination", "action", "reason", "risk_flags", "sanitized"])
        writer.writeheader()
        writer.writerows(rows)
    print({action: sum(row["action"] == action for row in rows) for action in ("MIGRATE", "RECREATE", "SKIP", "REVIEW_REQUIRED")})
