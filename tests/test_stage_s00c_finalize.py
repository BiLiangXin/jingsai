"""Synthetic manifest and public-safety checks for S00C handoff."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from s00c_finalize import STAGE, TASK_ID, ensure_complete_manifest, public_files  # noqa: E402
from stage_handoff import scan_public  # noqa: E402


def test_manifest_requires_every_public_implementation_and_evidence_file():
    run_id = "synthetic-S00C-001"
    files = public_files(run_id)
    assert len(files) == len(set(files))
    assert "docs/S00C_SUPPORT_EVIDENCE.md" in files
    assert "reports/data_audit/s00c_source_mutation_check.json" in files
    assert "tools/s00c_run.py" in files
    assert "tests/test_stage_s00c_finalize.py" in files
    assert all(not path.endswith("/") and "*" not in path for path in files)
    manifest = {"stage": STAGE, "task_id": TASK_ID, "run_id": run_id, "public_files": files}
    ensure_complete_manifest(manifest, run_id)
    with pytest.raises(ValueError, match="exact required"):
        ensure_complete_manifest({**manifest, "public_files": files[:-1]}, run_id)
    with pytest.raises(ValueError, match="exact required"):
        ensure_complete_manifest({**manifest, "public_files": files + [files[0]]}, run_id)


def test_public_report_scan_rejects_sample_level_labels(tmp_path):
    report = tmp_path / "aggregate.json"
    report.write_text(json.dumps({"after_nonzero_row_count": 4}), encoding="utf-8")
    assert scan_public(report) == []
    report.write_text(json.dumps({"sample_level_labels": [0, 1]}), encoding="utf-8")
    assert "forbidden_json_key:sample_level_labels" in scan_public(report)
