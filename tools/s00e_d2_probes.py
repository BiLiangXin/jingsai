"""Run independent synthetic D2 regressions and write aggregate review input only."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from mosei_flow import sha256, write_json
from stage_handoff import RUN_ID

ROOT = Path(__file__).resolve().parents[1]
TASK = "S00E_S01_PRESTART_ENGINEERING_HARDENING"
TEST = "tests/test_stage_s00e_d2_repair.py"


def run(run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", TEST], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    private = ROOT / "reports" / "runs" / run_id / "private"
    private.mkdir(parents=True, exist_ok=True)
    (private / "D2_SYNTHETIC_PROBE_LOG.txt").write_text(result.stdout + result.stderr,
                                                        encoding="utf-8")
    match = re.search(r"\b(\d+) passed\b", result.stdout)
    passed = int(match.group(1)) if match else 0
    report = {"task_id": TASK, "stage": "S00E", "run_id": run_id,
              "data_kind": "synthetic", "command": f"python -m pytest -q {TEST}",
              "exit_code": result.returncode, "passed": passed,
              "status": "PASS" if result.returncode == 0 and passed > 0 else "FAIL",
              "test_file_sha256": sha256(ROOT / TEST),
              "official_data_opened": False, "publication_called": False}
    if report["status"] != "PASS":
        raise RuntimeError("Synthetic D2 probes failed; no PASS report written")
    fixes = [
        ("R01", "MAJOR", "scalar sample and duplicate structured keys accepted",
         ["tools/stage_handoff.py", "tests/test_stage_s00e_d2_repair.py"]),
        ("R02", "MAJOR", "review self assertion and foreign acceptance run accepted",
         ["tools/stage_handoff.py", "tests/test_stage_s00e_d2_repair.py"]),
        ("R03", "MAJOR", "prepare wrote E13 PASS after failed gradient evidence",
         ["tools/s00e_prepare.py", "tools/s00e_evidence.py", "tests/test_stage_s00e_d2_repair.py"]),
        ("R04", "MAJOR", "contradictory stage counts and different executed nodes accepted",
         ["tools/s00e_test_record.py", "tools/s00e_pytest_probe.py",
          "tools/s00e_evidence.py", "tests/test_stage_s00e_d2_repair.py"]),
        ("M01", "MINOR", "missing or negative subtest count accepted",
         ["tools/s00e_evidence.py", "tests/test_stage_s00e_d2_repair.py"]),
    ]
    matrix = {"task_id": TASK, "stage": "S00E", "run_id": run_id,
              "status": "REPAIRED_PENDING_INDEPENDENT_REVIEW", "probe_report":
              "reports/engineering/s00e_d2_probe_results.json",
              "findings": [{"id": code, "severity": severity, "old_behavior": old,
                            "repair_state": "SYNTHETIC_REGRESSION_PASS_PENDING_ASTRA",
                            "evidence": evidence,
                            "sha256": {p: sha256(ROOT / p) for p in evidence}}
                           for code, severity, old, evidence in fixes],
              "unresolved": ["E19 independent review and trustworthy approval source pending",
                             "E21 read-only prepublication preflight pending E19",
                             "Historical sample CSV accessibility requires separate owner decision"]}
    write_json(ROOT / "reports/engineering/s00e_d2_repair_matrix.json", matrix)
    write_json(ROOT / "reports/engineering/s00e_d2_probe_results.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.run_id), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
