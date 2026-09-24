"""Private pytest node and phase recorder for the S00E test evidence contract."""
from __future__ import annotations

import json
import os
from pathlib import Path
from _pytest.subtests import SubtestReport

_nodes: list[str] = []
_reports: list[dict] = []


def pytest_collection_finish(session):
    _nodes[:] = [item.nodeid for item in session.items]


def pytest_runtest_logreport(report):
    _reports.append({"nodeid": report.nodeid, "when": report.when,
                     "outcome": report.outcome,
                     "subtest": isinstance(report, SubtestReport)})


def pytest_sessionfinish(session, exitstatus):
    target = os.environ.get("MOSEI_PYTEST_EVIDENCE_PATH")
    kind = os.environ.get("MOSEI_PYTEST_EVIDENCE_KIND")
    if not target or kind not in {"collection", "execution"}:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"kind": kind, "exit_code": int(exitstatus), "nodeids": _nodes,
             "reports": _reports if kind == "execution" else []}
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")
