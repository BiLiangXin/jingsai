"""Synthetic-only boundary diagnostics tests; no official data are opened."""

from __future__ import annotations

import json
import unittest

import numpy as np

from tools import s00b_audit, s00c_vision


def feature_rows(rows: list[list[float]]) -> np.ndarray:
    return np.asarray(rows, dtype=np.float64)[:, :, None]


class VisionBoundaryTests(unittest.TestCase):
    def test_s00b_zero_predicate_and_run_kinds_are_unchanged(self):
        x = feature_rows([[0, 0, 1, 0, 2, 0]])
        mask = np.all(x[0] == 0, axis=-1)
        self.assertEqual(mask.tolist(), s00b_audit.zero_rows(x)[0].tolist())
        self.assertEqual(s00c_vision._runs(mask), s00b_audit.zero_runs(mask))
        self.assertEqual(s00c_vision._structure(s00c_vision._runs(mask), len(mask)),
                         s00b_audit.zero_structure(mask))

    def test_length_zero_and_full_boundary(self):
        x = feature_rows([[2, 0, 0, 0], [1, 0, 0, 3]])
        public, rows = s00c_vision.diagnose_length_boundary(
            x, [0, 4], split="train", modality="vision")
        self.assertEqual(public["after"]["nonzero_row_count"], 1)
        self.assertEqual(public["declared_length_zero"]["with_nonzero_row_count"], 1)
        self.assertEqual(rows[0]["first_after_nonzero_offset"], 0)
        self.assertEqual(rows[1]["after_nonzero_row_count"], 0)
        self.assertEqual(sum(item["sample_count"] for item in public["length_bins"]), 2)

    def test_rejects_invalid_length_and_nonfinite_feature(self):
        x = feature_rows([[1, 2, 3, 4]])
        for lengths in ([-1], [5], [1.5], [np.nan], [np.inf]):
            with self.subTest(lengths=lengths), self.assertRaises(ValueError):
                s00c_vision.diagnose_length_boundary(
                    x, lengths, split="valid", modality="vision")
        with self.assertRaises(ValueError):
            s00c_vision.diagnose_length_boundary(
                feature_rows([[1, np.inf]]), [1], split="train", modality="audio")

    def test_test_quarantine_and_modality_guard(self):
        x = feature_rows([[1, 0]])
        for split in ("test", "TEST", ""):
            with self.subTest(split=split), self.assertRaises(ValueError):
                s00c_vision.diagnose_length_boundary(
                    x, [1], split=split, modality="vision")
        with self.assertRaises(ValueError):
            s00c_vision.diagnose_length_boundary(
                x, [1], split="train", modality="text")

    def test_after_runs_gaps_offsets_and_fixed_extension(self):
        x = feature_rows([[1, 2, 3, 4, 5, 0, 6, 7],
                          [1, 2, 3, 4, 5, 0, 6, 7]])
        public, rows = s00c_vision.diagnose_length_boundary(
            x, [3, 3], split="train", modality="vision")
        self.assertEqual(public["after"]["nonzero_row_count"], 8)
        self.assertEqual(public["after"]["affected_sample_count"], 2)
        self.assertEqual(public["after"]["run_count_per_sample"]["histogram"], {"2": 2})
        self.assertEqual(public["after"]["run_start_offset"]["histogram"], {"0": 2, "3": 2})
        self.assertEqual(public["after"]["nonzero_row_offset"]["histogram"],
                         {"0": 2, "1": 2, "3": 2, "4": 2})
        self.assertEqual(public["after"]["zero_gap_between_runs"]["histogram"], {"1": 2})
        self.assertEqual(public["after"]["last_nonzero_end_extension"]["dominant_offset"], 5)
        self.assertEqual(public["after"]["last_nonzero_end_extension"]["dominant_offset_affected_share"], 1)
        self.assertEqual(rows[0]["last_nonzero_index"], 7)
        self.assertEqual(rows[0]["after_nonzero_runs"],
                         [{"start_offset": 0, "length": 2}, {"start_offset": 3, "length": 2}])

    def test_off_by_one_candidate_is_descriptive(self):
        x = feature_rows([[1, 2, 3, 0], [1, 2, 0, 3]])
        public, _ = s00c_vision.diagnose_length_boundary(
            x, [2, 2], split="valid", modality="vision")
        self.assertEqual(public["after"]["boundary_row_nonzero_sample_count"], 1)
        self.assertEqual(public["after"]["off_by_one_exact_sample_count"], 1)
        self.assertEqual(public["after"]["last_nonzero_end_extension"]["histogram"],
                         {"1": 1, "2": 1})

    def test_inside_internal_multiple_and_whole_zero(self):
        x = feature_rows([[1, 0, 2, 0, 3, 4, 0, 5], [0, 0, 0, 0, 0, 0, 0, 0]])
        public, rows = s00c_vision.diagnose_length_boundary(
            x, [6, 2], split="train", modality="vision")
        self.assertEqual(public["inside"]["zero_row_count"], 4)
        self.assertEqual(public["inside"]["zero_structure_sample_counts"]["MULTIPLE_INTERNAL_RUNS"], 1)
        self.assertEqual(public["inside"]["zero_structure_sample_counts"]["ALL_ZERO"], 1)
        self.assertEqual(public["inside"]["zero_run_counts_by_kind"], {"internal": 2, "whole": 1})
        self.assertEqual(public["whole_sequence_zero"]["declared_length_positive_count"], 1)
        self.assertEqual(rows[1]["last_nonzero_index"], None)
        self.assertEqual(rows[1]["inside_zero_structure"], "ALL_ZERO")

    def test_stored_zero_structure_and_boundary_conflict(self):
        x = feature_rows([[1, 0, 0, 2], [0, 1, 2, 0]])
        public, rows = s00c_vision.diagnose_length_boundary(
            x, [2, 2], split="valid", modality="audio")
        stored = public["stored_zero_structure"]
        self.assertEqual(stored["zero_structure_sample_counts"],
                         {"INTERNAL_ZERO_RUN": 1, "PREFIX_AND_SUFFIX": 1})
        boundary = stored["declared_boundary_relation"]
        self.assertEqual(boundary["zero_run_counts"]["crosses_declared_boundary"], 1)
        self.assertEqual(boundary["zero_row_counts"]["crosses_declared_boundary"], 2)
        self.assertEqual(boundary["sample_count_with_crossing_zero_run"], 1)
        self.assertEqual(rows[0]["stored_zero_runs"][0]["boundary_relation"],
                         "crosses_declared_boundary")

    def test_norms_and_ratio_use_only_nonzero_rows(self):
        x = np.asarray([[[3., 4.], [6., 8.], [0., 0.]]])
        before = x.copy()
        public, rows = s00c_vision.diagnose_length_boundary(
            x, [1], split="train", modality="vision")
        self.assertEqual(public["row_norms"]["inside_nonzero_rows"]["quantiles"]["p50"], 5)
        self.assertEqual(public["row_norms"]["after_nonzero_rows"]["quantiles"]["p50"], 10)
        self.assertEqual(public["row_norms"]["after_to_inside_nonzero_global_median_ratio"], 2)
        self.assertEqual(rows[0]["after_to_inside_nonzero_norm_median_ratio"], 2)
        np.testing.assert_array_equal(x, before)

    def test_pairing_and_public_private_separation(self):
        audio = feature_rows([[1, 0, 0], [1, 0, 0]])
        vision = feature_rows([[1, 2, 0], [1, 0, 3]])
        public, private = s00c_vision.diagnose_unaligned_split(
            audio, [1, 1], vision, [1, 1], split="train")
        self.assertEqual(public["paired_after_nonzero_sample_counts"],
                         {"both": 0, "audio_only": 0, "vision_only": 2, "neither": 0})
        self.assertEqual(len(private["audio"]), 2)
        self.assertEqual(len(private["vision"]), 2)
        self.assertNotIn('"index":', json.dumps(public))
        self.assertNotIn('"inside_zero_runs":', json.dumps(public))
        self.assertEqual(private["vision"][0]["index"], 0)


if __name__ == "__main__":
    unittest.main()
