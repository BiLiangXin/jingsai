"""Synthetic S00C runner boundary checks; no official file is opened."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import s00c_run as run  # noqa: E402


def test_config_must_explicitly_trust_local_official_data(tmp_path):
    path = tmp_path / "paths.local.json"
    path.write_text(json.dumps({"data_root": str(tmp_path),
                                "trusted_competition_pickle": False}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Trusted"):
        run.trusted_sources(path)
    path.write_text(json.dumps({"data_root": str(tmp_path),
                                "trusted_competition_pickle": True}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Required Attachment 2"):
        run.trusted_sources(path)


def test_source_fingerprint_guard(tmp_path):
    source = {"aligned": {"file_name": "aligned_50.pkl", "size": 3, "mtime_ns": 1, "sha256": "a"},
              "unaligned": {"file_name": "unaligned_50.pkl", "size": 5, "mtime_ns": 2, "sha256": "b"}}
    run.match_sources(source, {"source": {"after": source}})
    bad = {**source, "unaligned": {**source["unaligned"], "sha256": "changed"}}
    with pytest.raises(RuntimeError, match="stop before deserialization"):
        run.match_sources(bad, {"source": {"after": source}})


def test_reconciliation_uses_published_s00b_report_shape():
    baseline = {
        "schema_aligned": {"splits": {s: {"sample_count": 1} for s in ("train", "valid")}},
        "schema_unaligned": {"splits": {s: {"sample_count": 1} for s in ("train", "valid")}},
        "length": {s: {m: {"nonzero_after_length_count": 0,
                            "zero_inside_declared_length_count": 0}
                       for m in ("audio", "vision")} for s in ("train", "valid")},
        "aligned_position": {s: {"candidate_active_position_count": 2,
                                  "text": {"inactive_nonzero": 0}}
                             for s in ("train", "valid")},
    }
    observed = {
        "counts": {v: {s: 1 for s in ("train", "valid")} for v in ("aligned", "unaligned")},
        "length": baseline["length"],
        "aligned": {s: {"active": 2, "inactive_text_nonzero": 0} for s in ("train", "valid")},
    }
    assert run.compare_observed(observed, baseline)["all_equal"]


def test_runner_never_indexes_test_or_attachment3_4(tmp_path, monkeypatch):
    class Quarantined(dict):
        def __getitem__(self, key):
            if key == "test":
                raise AssertionError("test accessed")
            return super().__getitem__(key)

    aligned_item = {"text_bert": np.array([[[1, 2], [1, 0], [0, 0]]]),
                    "text": np.ones((1, 2, 2)), "audio": np.ones((1, 2, 2)),
                    "vision": np.ones((1, 2, 2))}
    unaligned_item = {"text": np.ones((1, 2, 2)), "audio": np.ones((1, 3, 2)),
                      "vision": np.ones((1, 3, 2)), "audio_lengths": np.array([2]),
                      "vision_lengths": np.array([2])}
    loaded = [Quarantined(train=aligned_item, valid=aligned_item, test=object()),
              Quarantined(train=unaligned_item, valid=unaligned_item, test=object())]
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "checked_workspace", lambda: "a" * 40)
    monkeypatch.setattr(run, "load_baseline", lambda: {})
    monkeypatch.setattr(run, "trusted_sources", lambda _: {
        "aligned": tmp_path / "aligned_50.pkl", "unaligned": tmp_path / "unaligned_50.pkl"})
    for name in ("aligned_50.pkl", "unaligned_50.pkl"):
        (tmp_path / name).write_bytes(b"synthetic")
    monkeypatch.setattr(run, "file_fingerprint", lambda p: {"file_name": p.name, "size": 9,
                                                              "mtime_ns": 1, "sha256": "synthetic"})
    monkeypatch.setattr(run, "match_sources", lambda *_: None)
    monkeypatch.setattr(run.pickle, "load", lambda _: loaded.pop(0))
    monkeypatch.setattr(run, "compare_observed", lambda *_: {"all_equal": True, "checks": {}, "differences": []})
    result = run.audit_run("synthetic-S00C-run")
    assert result["status"] == "SUCCESS"
    assert result["sample_counts"] == {"aligned": {"train": 1, "valid": 1},
                                        "unaligned": {"train": 1, "valid": 1}}
    record = json.loads((tmp_path / "reports/runs/synthetic-S00C-run/RUN.json").read_text())
    assert record["split_usage"]["test"].startswith("quarantined")
    assert not record["attachment3_content_inspected"]
    assert not record["attachment4_feature_content_inspected"]


def test_diagnostics_are_reproducible_and_inputs_unchanged():
    from s00c_text_zero import diagnose_aligned_split
    from s00c_vision import diagnose_length_boundary

    bert = np.array([[[2, 3, 0], [1, 1, 0], [0, 0, 0]]])
    text = np.ones((1, 3, 2))
    audio = np.ones((1, 3, 2))
    vision = np.array([[[1., 0.], [0., 0.], [2., 1.]]])
    inputs = [bert, text, audio, vision]
    snapshots = [x.copy() for x in inputs]
    first = diagnose_aligned_split(*inputs)
    second = diagnose_aligned_split(*inputs)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    boundary_first = diagnose_length_boundary(vision, [2], split="valid", modality="vision")
    boundary_second = diagnose_length_boundary(vision, [2], split="valid", modality="vision")
    assert json.dumps(boundary_first, sort_keys=True) == json.dumps(boundary_second, sort_keys=True)
    for original, snapshot in zip(inputs, snapshots):
        np.testing.assert_array_equal(original, snapshot)
