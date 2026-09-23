"""Synthetic-only checks for aggregate aligned text/zero diagnostics."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("s00c_text_zero", ROOT / "tools" / "s00c_text_zero.py")
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)
baseline_spec = importlib.util.spec_from_file_location("s00b_audit_for_zero_compat", ROOT / "tools" / "s00b_audit.py")
baseline = importlib.util.module_from_spec(baseline_spec)
baseline_spec.loader.exec_module(baseline)


def fixture():
    bert = np.zeros((3, 3, 5), dtype=np.int64)
    bert[:, 1, :] = np.array([[1, 1, 1, 0, 0], [1, 1, 0, 0, 0], [1, 1, 1, 1, 1]])
    text = np.ones((3, 5, 2), dtype=np.float32)
    text[0, 3:] = [2, 2]
    text[1, 2:] = [[3, 0], [3, 0], [4, 0]]
    audio = np.ones((3, 5, 2), dtype=np.float32)
    audio[0, [0, 2, 4]] = 0  # Prefix, internal, suffix.
    audio[1] = 0              # Whole modality zero.
    audio[2, [1, 3]] = 0     # Multiple internal runs.
    vision = np.ones((3, 5, 2), dtype=np.float32)
    vision[0, [0, 4]] = 0    # Both ends.
    vision[1, [2, 3, 4]] = 0
    return bert, text, audio, vision


class TextZeroTests(unittest.TestCase):
    def test_s00b_exact_zero_and_half_open_runs_compatible(self):
        cases = [[True] * 5, [True, False, True, False, True],
                 [False, True, False, True, False], [False] * 5]
        for case in cases:
            with self.subTest(case=case):
                row = np.where(np.array(case)[:, None], 0.0, 1.0)
                self.assertEqual(diagnostics._zero_rows(row).tolist(), baseline.zero_rows(row).tolist())
                self.assertEqual(diagnostics._zero_runs(case), baseline.zero_runs(case))
                self.assertEqual(diagnostics._zero_structure(case), baseline.zero_structure(case))

    def test_mask_prefix_lengths_and_nonzero_inactive_text(self):
        text_public, _ = diagnostics.diagnose_aligned_split(*fixture())
        mask = text_public["candidate_mask"]
        self.assertEqual(mask["status"], "INFERRED")
        self.assertTrue(mask["continuous_active_prefix_all_samples"])
        self.assertEqual(mask["candidate_active_length_histogram"], {"2": 1, "3": 1, "5": 1})
        self.assertEqual(text_public["text_features"]["inactive"]["nonzero_row_count"], 5)
        self.assertEqual(text_public["text_features"]["inactive"]["zero_row_count"], 0)

    def test_tail_repetition_counts_exact_and_high_cosine(self):
        text_public, _ = diagnostics.diagnose_aligned_split(*fixture())
        tail = text_public["text_features"]["inactive_tail_repetition"]
        self.assertEqual(tail["samples_with_at_least_two_inactive_rows"], 2)
        self.assertEqual(tail["adjacent_inactive_pair_count"], 3)
        self.assertEqual(tail["adjacent_exact_equal_pair_count"], 2)
        self.assertEqual(tail["adjacent_high_cosine_pair_count"], 3)
        self.assertEqual(tail["samples_with_all_inactive_rows_exactly_identical"], 1)

    def test_zero_categories_and_candidate_overlap(self):
        text_public, zero = diagnostics.diagnose_aligned_split(*fixture())
        audio = zero["audio"]
        self.assertEqual(audio["all_zero_sample_count"], 1)
        self.assertEqual(audio["sample_flag_counts"]["multiple_internal"], 1)
        self.assertEqual(audio["zero_run_count_by_location"],
                         {"whole": 1, "prefix": 1, "suffix": 1, "internal": 3})
        self.assertEqual(audio["candidate_active_overlap"]["active_zero"], 6)
        self.assertEqual(text_public["mask_zero_cross"]["vision"]["inactive_zero"], 4)
        self.assertEqual(zero["vision"]["sample_flag_counts"]["both_ends"], 1)

    def test_nonbinary_and_nonprefix_candidate_stay_unknown(self):
        bert, text, audio, vision = fixture()
        bert[0, 1, 0] = 2
        result, zero = diagnostics.diagnose_aligned_split(bert, text, audio, vision)
        self.assertEqual(result["candidate_mask"]["status"], "UNKNOWN")
        self.assertIsNone(result["mask_zero_cross"])
        self.assertIsNone(zero["audio"]["candidate_active_overlap"])
        bert, text, audio, vision = fixture()
        bert[0, 1] = [1, 0, 1, 0, 0]
        result, _ = diagnostics.diagnose_aligned_split(bert, text, audio, vision)
        self.assertEqual(result["candidate_mask"]["non_prefix_sample_count"], 1)
        self.assertEqual(result["candidate_mask"]["status"], "UNKNOWN")

    def test_input_shape_finite_and_immutability(self):
        values = fixture()
        snapshots = [x.copy() for x in values]
        diagnostics.diagnose_aligned_split(*values)
        for original, snapshot in zip(values, snapshots):
            np.testing.assert_array_equal(original, snapshot)
        with self.assertRaisesRegex(ValueError, "aligned"):
            diagnostics.diagnose_aligned_split(values[0], values[1][:, :-1], values[2], values[3])
        bad = values[1].copy(); bad[0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            diagnostics.diagnose_aligned_split(values[0], bad, values[2], values[3])

    def test_json_aggregates_only(self):
        report = diagnostics.diagnose_aligned_split(*fixture())
        serialized = json.dumps(report, allow_nan=False)
        self.assertNotIn("sample_id", serialized)
        self.assertNotIn("raw_text", serialized)
        self.assertNotIn("classification_labels", serialized)
        self.assertNotIn("token_ids", serialized)
        self.assertIn("candidate_active_overlap", serialized)


if __name__ == "__main__":
    unittest.main()
