"""Synthetic S00B engineering tests; no competition file is opened."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("s00b_audit", ROOT / "tools" / "s00b_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
flow_spec = importlib.util.spec_from_file_location("mosei_flow", ROOT / "tools" / "mosei_flow.py")
flow = importlib.util.module_from_spec(flow_spec)
flow_spec.loader.exec_module(flow)


class S00BAuditTests(unittest.TestCase):
    def test_schema_extractor_and_extra_field(self):
        d = {"train": {"id": ["a$_$1"], "audio": np.zeros((1, 2, 3)), "extra": np.ones(1)}}
        result, consistency = audit.schema(d, {"file_name": "synthetic.pkl"})
        self.assertEqual(result["splits"]["train"]["fields"]["audio"]["shape"], [1, 2, 3])
        self.assertEqual(result["splits"]["train"]["EXTRA_FIELDS"], ["extra"])
        self.assertTrue(consistency["train"]["pass"])

    def test_schema_alignment_failure(self):
        _, consistency = audit.schema({"train": {"id": ["a$_$1"], "text": np.zeros((2, 1, 1))}}, {})
        self.assertFalse(consistency["train"]["pass"])

    def test_zero_row_detector_exact(self):
        a = np.array([[[0., 0.], [0., 1.], [np.nan, 0.]]])
        self.assertEqual(audit.zero_rows(a).tolist(), [[True, False, False]])

    def test_zero_run_detector(self):
        self.assertEqual(audit.zero_runs([True, True, False, True, False, True]), [(0, 2, "prefix"), (3, 4, "internal"), (5, 6, "suffix")])

    def test_structure_categories(self):
        cases = {
            "000": "ALL_ZERO", "111": "NO_ZERO", "011": "PREFIX_ZERO_ONLY",
            "110": "SUFFIX_ZERO_ONLY", "010": "PREFIX_AND_SUFFIX",
            "101": "INTERNAL_ZERO_RUN", "10101": "MULTIPLE_INTERNAL_RUNS",
        }
        for bits, expected in cases.items():
            with self.subTest(bits=bits):
                self.assertEqual(audit.zero_structure([x == "0" for x in bits]), expected)

    def test_all_zero_run(self):
        self.assertEqual(audit.zero_runs([True, True]), [(0, 2, "whole")])

    def test_length_consistency(self):
        x = np.array([[False, False, True, True], [True, False, False, True]])
        r = audit.length_consistency(x, np.array([2, 3]))
        self.assertTrue(r["legal_0_to_T"])
        self.assertEqual(r["nonzero_after_length_count"], 0)
        self.assertEqual(r["zero_inside_declared_length_count"], 1)
        self.assertEqual(r["leading_zero_inside_declared_length_count"], 1)

    def test_length_rejects_noninteger_and_out_of_range(self):
        x = np.zeros((1, 4), dtype=bool)
        self.assertFalse(audit.length_consistency(x, [1.5])["integer_like"])
        self.assertFalse(audit.length_consistency(x, [5])["legal_0_to_T"])

    def test_id_parser_preserves_video_underscores(self):
        self.assertEqual(audit.parse_id("a_b$_$4"), ("a_b", "4"))
        self.assertIsNone(audit.parse_id("broken"))
        self.assertIsNone(audit.parse_id("a$_$b$_$c"))

    def test_id_overlap_and_duplicates(self):
        d = {"train": {"id": ["a$_$1", "a$_$1"]}, "valid": {"id": ["a$_$2"]}, "test": {"id": ["a$_$1"]}}
        r, _ = audit.id_audit(d)
        self.assertEqual(r["train"]["duplicate_count"], 1)
        self.assertEqual(r["train_test_exact_id_overlap_count"], 1)
        self.assertEqual(r["train_valid_video_id_overlap_count"], 1)

    def test_label_mapping_and_neutral_zero(self):
        d = {}
        for s in ("train", "valid"):
            d[s] = {"id": ["a$_$1", "a$_$2", "a$_$3"], "regression_labels": np.array([-1., 0., 1.]), "classification_labels": np.array([0., 1., 2.])}
        ann = {"a$_$1": "Negative", "a$_$2": "Neutral", "a$_$3": "Positive"}
        r = audit.label_audit(d, ann, {k: v for k, v in zip(ann, [-1., 0., 1.])})
        self.assertEqual(r["train"]["neutral_zero_mismatch_count"], 0)
        self.assertEqual(len(r["train"]["annotation_x_classification"]), 3)

    def test_neutral_zero_mismatch_detected(self):
        d = {s: {"id": ["a$_$1"], "regression_labels": np.array([0.]), "classification_labels": np.array([0.])} for s in ("train", "valid")}
        self.assertEqual(audit.label_audit(d, {"a$_$1": "Negative"}, {"a$_$1": 0.})["train"]["neutral_zero_mismatch_count"], 1)

    def test_test_quarantine_has_no_distribution(self):
        r = audit.test_label_quarantine({"test": {"regression_labels": np.array([-1., 0., 1.]), "classification_labels": np.array([0., 1., 2.])}})
        serialized = json.dumps(r)
        self.assertTrue(r["TEST_LABEL_DISTRIBUTION_QUARANTINED"])
        self.assertFalse(any(key in serialized for key in ("mean", "histogram", "unique_values", "exact_zero_count", "negative_count")))

    def test_attachment3_loader_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "3"; p.mkdir(); (p / "x.pkl").write_bytes(b"not a pickle")
            with patch.object(audit.pickle, "load", side_effect=AssertionError("load forbidden")):
                r = audit.attachment_file_inventory(p, 3)
            self.assertTrue(r["CONTENT_NOT_INSPECTED"])
            self.assertEqual(r["file_count"], 1)

    def test_attachment4_loader_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "4"; p.mkdir(); (p / "x.pkl").write_bytes(b"x"); (p / "x.mp4").write_bytes(b"x")
            with patch.object(audit.pickle, "load", side_effect=AssertionError("load forbidden")):
                r = audit.attachment_file_inventory(p, 4)
            self.assertTrue(r["FEATURE_CONTENT_NOT_INSPECTED"])
            self.assertTrue(r["VIDEO_CONTENT_NOT_INSPECTED"])

    def test_path_redaction_and_package_exclusion(self):
        self.assertIn("private_windows_path", flow.scan_text("C:\\Users\\alice\\data"))
        for name in ("E题数据/a.pkl", "configs/paths.local.json", "x.mp4", "private/file.pkl"):
            self.assertTrue(flow.forbidden_path(name))

    def test_source_array_not_mutated(self):
        x = np.array([[[0., 0.], [1., 0.]]]); before = x.copy()
        audit.zero_rows(x)
        self.assertTrue(np.array_equal(x, before))

    def test_competition_expected_count_is_separate(self):
        d = {"train": {"id": ["a$_$1"]}}
        r, _ = audit.schema(d, {})
        self.assertEqual(r["total_sample_count"], 1)
        self.assertEqual(r["specified_expected_total"], 4850)
        self.assertTrue(r["COMPETITION_SPEC_MISMATCH"])

    def test_public_report_test_distribution_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "test.json"
            audit.write_json(p, audit.test_label_quarantine({"test": {"regression_labels": np.array([0., 1.])}}))
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("exact_zero_count", text)
            self.assertNotIn("sample_id", text)


if __name__ == "__main__":
    unittest.main()
