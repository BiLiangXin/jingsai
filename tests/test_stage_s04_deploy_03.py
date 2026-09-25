"""Synthetic contract checks for the one fixed E1 visible-UNK interface."""
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("s04_e1_visible_unk", ROOT / "tools/s04_e1_visible_unk.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    value = np.zeros((1, 3, 50), dtype=np.float32)
    value[0, 0, :5] = [101, 2023, 100, 2003, 102]
    value[0, 1, :5] = 1
    return value


class VisibleUnkContract(unittest.TestCase):
    def test_legal_unk_preserves_exact_channels(self):
        raw = fixture()
        tokens, support = MODULE.validate_tokens(raw)
        np.testing.assert_array_equal(tokens, raw.astype(np.int64))
        self.assertEqual(int(tokens[0, 0, 2]), 100)
        self.assertEqual(support[0].tolist(), [True] * 5 + [False] * 45)

    def test_no_unk_uses_same_contract(self):
        raw = fixture()
        raw[0, 0, 2] = 2000
        tokens, support = MODULE.validate_tokens(raw)
        self.assertEqual(int(tokens[0, 0, 2]), 2000)
        self.assertEqual(int(support.sum()), 5)

    def test_reject_nonintegral_and_nonfinite(self):
        for bad in (100.5, np.nan, np.inf):
            raw = fixture()
            raw[0, 0, 2] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MODULE.validate_tokens(raw)

    def test_reject_bad_token_range(self):
        for bad in (-1, 30522):
            raw = fixture()
            raw[0, 0, 2] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MODULE.validate_tokens(raw)

    def test_reject_corrupted_support_or_segments(self):
        changes = [(1, 1, 0), (1, 5, 1), (1, 2, 0.5), (2, 5, 1)]
        for channel, pos, value in changes:
            raw = fixture()
            raw[0, channel, pos] = value
            with self.subTest(channel=channel, pos=pos), self.assertRaises(ValueError):
                MODULE.validate_tokens(raw)

    def test_active_segment_one_is_preserved(self):
        raw = fixture()
        raw[0, 2, 2] = 1
        tokens, _ = MODULE.validate_tokens(raw)
        self.assertEqual(int(tokens[0, 2, 2]), 1)

    def test_reject_wrong_boundary_or_padding(self):
        for pos, value in ((0, 100), (4, 100), (5, 100)):
            raw = fixture()
            raw[0, 0, pos] = value
            with self.subTest(pos=pos), self.assertRaises(ValueError):
                MODULE.validate_tokens(raw)

    def test_reject_wrong_shape_and_all_padding(self):
        for raw in (np.zeros((3, 49), dtype=np.float32), np.zeros((3, 50), dtype=np.float32)):
            with self.subTest(shape=raw.shape), self.assertRaises(ValueError):
                MODULE.validate_tokens(raw)


if __name__ == "__main__":
    unittest.main()
