"""Record actual S00E pytest nodes, phases and counts without publishing node IDs."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from mosei_flow import sha256, write_json
from s00e_evidence import (EvidenceError, REQUIRED_TESTED, STAGE_TESTS,
                           node_digest, validate_tests)
from stage_handoff import RUN_ID

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "S00E_S01_PRESTART_ENGINEERING_HARDENING"


def number(output: str, label: str) -> int:
    match = re.search(rf"\b(\d+) {label}\b", output)
    return int(match.group(1)) if match else 0


def _pytest(kind: str, private: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "pytest"]
    if kind == "collection":
        command.append("--collect-only")
    command += ["-q", "tests"]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "tools") + os.pathsep + environment.get("PYTHONPATH", "")
    plugins = environment.get("PYTEST_PLUGINS", "")
    environment["PYTEST_PLUGINS"] = (plugins + "," if plugins else "") + "s00e_pytest_probe"
    environment["MOSEI_PYTEST_EVIDENCE_KIND"] = kind
    environment["MOSEI_PYTEST_EVIDENCE_PATH"] = str(private / (
        "PYTEST_COLLECTION_NODES.json" if kind == "collection" else "PYTEST_EXECUTION_NODES.json"))
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=environment)


def run(run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    run_dir = ROOT / "reports" / "runs" / run_id
    private = run_dir / "private"
    private.mkdir(parents=True, exist_ok=True)
    def snapshot():
        names = set(REQUIRED_TESTED)
        for folder in ("src", "tools", "tests"):
            names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*.py")
                         if "__pycache__" not in p.parts)
        names.update(name for name in ("pyproject.toml", "pytest.ini", "setup.cfg") if (ROOT / name).is_file())
        return {name: sha256(ROOT / name) for name in sorted(names)}
    before = snapshot()
    collection = _pytest("collection", private)
    at_execution = snapshot()
    execution = _pytest("execution", private)
    after = snapshot()
    (private / "COLLECTION_LOG.txt").write_text(collection.stdout + collection.stderr, encoding="utf-8")
    (private / "TEST_LOG.txt").write_text(execution.stdout + execution.stderr, encoding="utf-8")
    collection_path = private / "PYTEST_COLLECTION_NODES.json"
    execution_path = private / "PYTEST_EXECUTION_NODES.json"
    try:
        collection_proof = json.loads(collection_path.read_text(encoding="utf-8"))
        execution_proof = json.loads(execution_path.read_text(encoding="utf-8"))
        collected_nodes = collection_proof["nodeids"]
        reports = execution_proof["reports"]
        calls = [report for report in reports if report["when"] == "call" and report.get("subtest") is False]
        subcalls = [report for report in reports if report.get("subtest") is True]
        executed_nodes = list(dict.fromkeys(report["nodeid"] for report in calls))
        subtests = len(subcalls)
    except (OSError, ValueError, KeyError, TypeError):
        collected_nodes, executed_nodes, subtests, calls = [], [], 0, []
        subcalls = []
    passed = number(execution.stdout, "passed")
    failed = number(execution.stdout, "failed")
    errors = number(execution.stdout, "errors?")
    skipped = number(execution.stdout, "skipped")
    deselected = number(execution.stdout, "deselected")
    subtests_passed = subtests if all(report["outcome"] == "passed" for report in subcalls) else 0
    subtests_failed = sum(report["outcome"] == "failed" for report in subcalls)
    subtests_errors = sum(report["outcome"] not in {"passed", "failed"} for report in subcalls)
    record = {
        "stage": "S00E", "task_id": TASK_ID, "run_id": run_id, "status": "PASS",
        "environment": "birdAL", "collection_command": "python -m pytest --collect-only -q tests",
        "command": "python -m pytest -q tests", "pytest_evidence_plugin": "s00e_pytest_probe",
        "collection_exit_code": collection.returncode,
        "exit_code": execution.returncode, "collected": len(collected_nodes),
        "executed": len(executed_nodes), "passed": passed, "failed": failed,
        "errors": errors, "skipped": skipped, "deselected": deselected,
        "subtests_passed": subtests_passed, "subtests_failed": subtests_failed,
        "subtests_errors": subtests_errors,
        "s00e_stage_collected": sum(x.startswith(STAGE_TESTS[0]) for x in collected_nodes),
        "s00e_repair_collected": sum(x.startswith(STAGE_TESTS[1]) for x in collected_nodes),
        "s00e_d2_collected": sum(x.startswith(STAGE_TESTS[2]) for x in collected_nodes),
        "collected_nodeids_sha256": node_digest(collected_nodes),
        "executed_nodeids_sha256": node_digest(executed_nodes),
        "collection_proof_sha256": sha256(collection_path) if collection_path.is_file() else None,
        "execution_proof_sha256": sha256(execution_path) if execution_path.is_file() else None,
        "tested_files_sha256": after,
        "tested_files_before_sha256": before, "tested_files_at_execution_sha256": at_execution,
        "result_summary": execution.stdout.strip().splitlines()[-1] if execution.stdout.strip() else "no summary",
    }
    try:
        validate_tests(record, ROOT, TASK_ID, run_id)
    except EvidenceError:
        record["status"] = "FAIL"
    write_json(run_dir / "TEST_RESULTS.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    result = run(args.run_id)
    print(json.dumps({key: result[key] for key in
                      ("run_id", "status", "collected", "executed", "passed", "failed",
                       "skipped", "subtests_passed", "exit_code")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
