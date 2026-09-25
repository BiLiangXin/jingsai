"""Pure synthetic checks of the clarified S04 reader and mapping boundaries."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from s04_clarified_a3_audit import token_counts
from s04_clarified_map import token_word_indices, window_mapping


class ClarifiedS04Tests(unittest.TestCase):
    def test_float_token_container_with_integral_values(self):
        b = np.zeros((1, 3, 50), np.float32)
        b[0, 0, :4] = [101, 100, 12, 102]
        b[0, 1, :4] = 1
        self.assertEqual(token_counts(b)['unk100_active'], 1)
        b[0, 0, 1] = 100.25
        with self.assertRaisesRegex(ValueError, 'TOKEN_NONINTEGER_VALUE'):
            token_counts(b)

    def test_support_and_ids_reject_invalid(self):
        b = np.zeros((3, 50))
        b[0, :3] = [101, 15, 102]
        b[1, :3] = 1
        token_counts(b)
        b[1, 1] = 0
        with self.assertRaisesRegex(ValueError, 'SUPPORT_PREFIX'):
            token_counts(b)
        b[1, 1] = 1
        b[0, 3] = 42
        with self.assertRaisesRegex(ValueError, 'TOKEN_IDS'):
            token_counts(b)

    def test_subwords_and_specials(self):
        mapping = token_word_indices([(0, 0), (0, 2), (2, 4), (5, 8), (0, 0)], [1, 1, 1, 1, 0], [(0, 4), (5, 8)])
        self.assertEqual(mapping, [None, 0, 0, 1, None])
        window = window_mapping({'feature_start': 1, 'feature_end_exclusive': 4}, mapping, [(.2, .4), (.8, 1.1)], np.array([.25, .9]))
        self.assertEqual(window['quality'], 'ESTIMATED_ACOUSTIC_ALIGNMENT')
        self.assertEqual(len(window['intervals']), 2)
        self.assertEqual(window['intervals'][1]['nearest_video_pts'], .9)
        self.assertEqual(window_mapping({'feature_start': 0, 'feature_end_exclusive': 1}, mapping, None, np.array([0.]))['quality'], 'UNMAPPABLE')
        self.assertEqual(window_mapping({'feature_start': 1, 'feature_end_exclusive': 2}, mapping, None, np.array([0.]))['quality'], 'TEXT_SPAN_ONLY')
        with self.assertRaisesRegex(ValueError, 'WINDOW_BOUNDS'):
            window_mapping({'feature_start': 49, 'feature_end_exclusive': 51}, mapping, None, np.array([0.]))


if __name__ == '__main__':
    unittest.main()
