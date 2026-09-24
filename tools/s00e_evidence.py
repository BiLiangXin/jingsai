"""Shared, fail-closed S00E test and runtime evidence checks.

The private pytest node report stays local; only its digest and aggregate counts
are published. This module never grants independent review approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TASK_ID = "S00E_S01_PRESTART_ENGINEERING_HARDENING"
REQUIRED_TESTED = {
    "tools/stage_handoff.py", "tools/s00e_preflight.py", "tools/s00e_test_record.py",
    "tools/s00e_pytest_probe.py", "tools/s00e_evidence.py", "tools/s00e_d2_probes.py",
    "tools/s00e_prepare.py", "tools/s00e_approval.py", "tests/test_stage_s00e_closeout.py",
    "tools/s00e_smoke.py", "tools/s00d_finalize.py", "tools/web_chat_handoff.py",
    "src/mosei/data/data_contract.py", "src/mosei/data/pooling.py",
    "tests/test_stage_handoff.py", "tests/test_stage_s00e_hardening.py",
    "tests/test_stage_s00e_phase_d_repair.py", "tests/test_stage_s00e_d2_repair.py",
}
STAGE_TESTS = ("tests/test_stage_s00e_hardening.py::",
               "tests/test_stage_s00e_phase_d_repair.py::",
               "tests/test_stage_s00e_d2_repair.py::")


class EvidenceError(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def node_digest(nodes: list[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(nodes), ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _integer(value: object, *, positive: bool = False) -> bool:
    return type(value) is int and (value > 0 if positive else value >= 0)


def validate_tests(tests: dict, root: Path, task_id: str, run_id: str) -> None:
    if (tests.get("task_id") != task_id or tests.get("stage") != "S00E" or
            tests.get("run_id") != run_id or tests.get("status") != "PASS" or
            tests.get("environment") != "birdAL"):
        raise EvidenceError("S00E test identity or status invalid")
    for key in ("collection_exit_code", "exit_code", "failed", "errors", "skipped",
                "deselected", "subtests_failed", "subtests_errors"):
        if not _integer(tests.get(key)) or tests[key] != 0:
            raise EvidenceError("S00E pytest failure or malformed zero count")
    if not _integer(tests.get("subtests_passed")):
        raise EvidenceError("S00E subtest count missing or invalid")
    for key in ("collected", "executed", "passed"):
        if not _integer(tests.get(key), positive=True):
            raise EvidenceError("S00E main test count missing or invalid")
    if tests["collected"] != tests["executed"] or tests["executed"] != tests["passed"]:
        raise EvidenceError("S00E main test counts disagree")
    if (tests.get("collection_command") != "python -m pytest --collect-only -q tests" or
            tests.get("command") != "python -m pytest -q tests" or
            tests.get("pytest_evidence_plugin") != "s00e_pytest_probe"):
        raise EvidenceError("S00E pytest command mismatch")
    private = root / "reports" / "runs" / run_id / "private"
    proofs = []
    for name, key in (("PYTEST_COLLECTION_NODES.json", "collection_proof_sha256"),
                      ("PYTEST_EXECUTION_NODES.json", "execution_proof_sha256")):
        path = private / name
        if not path.is_file() or digest(path) != tests.get(key):
            raise EvidenceError("S00E private pytest proof missing or changed")
        try:
            proofs.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, UnicodeError) as exc:
            raise EvidenceError("S00E private pytest proof malformed") from exc
    collection, execution = proofs
    if (collection.get("kind") != "collection" or execution.get("kind") != "execution" or
            type(collection.get("exit_code")) is not int or collection["exit_code"] != 0 or
            type(execution.get("exit_code")) is not int or execution["exit_code"] != 0):
        raise EvidenceError("S00E pytest proof exit mismatch")
    collected = collection.get("nodeids")
    executed_collection = execution.get("nodeids")
    reports = execution.get("reports")
    if (not isinstance(collected, list) or not collected or
            not all(isinstance(x, str) and x.startswith("tests/") for x in collected) or
            len(collected) != len(set(collected)) or executed_collection != collected or
            not isinstance(reports, list)):
        raise EvidenceError("S00E pytest collected node set incomplete")
    phases: dict[str, dict[str, str]] = {}
    subtest_count = 0
    for report in reports:
        if not isinstance(report, dict) or report.get("nodeid") not in collected:
            raise EvidenceError("S00E pytest report has unknown node")
        when, outcome = report.get("when"), report.get("outcome")
        if (when not in {"setup", "call", "teardown"} or outcome != "passed" or
                type(report.get("subtest")) is not bool):
            raise EvidenceError("S00E pytest report phase malformed or failed")
        if report["subtest"]:
            if when != "call":
                raise EvidenceError("S00E subtest phase must be call")
            subtest_count += 1
            continue
        node = phases.setdefault(report["nodeid"], {})
        if when in node:
            raise EvidenceError("S00E duplicate main pytest phase")
        node[when] = outcome
    if (set(phases) != set(collected) or
            any(set(node) != {"setup", "call", "teardown"} for node in phases.values())):
        raise EvidenceError("S00E pytest execution incomplete or failed")
    if (len(collected) != tests["collected"] or len(phases) != tests["executed"] or
            subtest_count != tests["subtests_passed"] or
            node_digest(collected) != tests.get("collected_nodeids_sha256") or
            node_digest(list(phases)) != tests.get("executed_nodeids_sha256")):
        raise EvidenceError("S00E pytest node proof disagrees with public counts")
    for prefix, key in zip(STAGE_TESTS, ("s00e_stage_collected", "s00e_repair_collected",
                                          "s00e_d2_collected")):
        count = sum(node.startswith(prefix) for node in collected)
        if count < 1 or tests.get(key) != count or type(tests.get(key)) is not int:
            raise EvidenceError("S00E stage test coverage disagrees with node proof")
    tested = tests.get("tested_files_sha256")
    if (tests.get("tested_files_before_sha256") != tested or
            tests.get("tested_files_at_execution_sha256") != tested):
        raise EvidenceError("S00E code changed during collection or execution")
    if not isinstance(tested, dict) or not REQUIRED_TESTED <= set(tested):
        raise EvidenceError("S00E tested source digest set incomplete")
    for relative, expected in tested.items():
        path = root / relative
        if (not path.is_file() or path.is_symlink() or
                not path.resolve().is_relative_to(root.resolve()) or
                type(expected) is not str or digest(path) != expected):
            raise EvidenceError("S00E tested source changed after execution")
