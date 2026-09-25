import unittest

from mosei.autoqc.core import audit_window, unique_exact_matches, valid_interval, words


class AutoQcCoreTests(unittest.TestCase):
    def test_normalization_preserves_negation_digits_order(self):
        self.assertEqual(words("No, don't 12!"), ["no", "don't", "12"])

    def test_unique_and_ambiguous(self):
        self.assertEqual(unique_exact_matches(["a", "b"], ["a", "b"])["unique"], {0: 0, 1: 1})
        x = unique_exact_matches(["a", "a"], ["a"])
        self.assertEqual(x["unique"], {})
        self.assertEqual(x["ambiguous_ref"], [0, 1])
        self.assertEqual(unique_exact_matches(["not", "good"], ["good"])["disagreement"], .5)

    def test_dual_single_conflict_and_abstain(self):
        a = {0: (1., 1.3), 1: (1.4, 1.7)}
        b = [(1.02, 1.31), (1.42, 1.69)]
        good = audit_window(["a", "b"], ["a", "b"], a, b, [0, 1], 0, 2)
        self.assertEqual(good["acoustic_basis"], "DUAL_CONSISTENT_ESTIMATE")
        self.assertEqual(audit_window(["a"], ["a"], {}, [b[0]], [0], 0, 2)["acoustic_basis"], "SINGLE_ASR_ESTIMATE")
        self.assertEqual(audit_window(["a"], ["a"], {0: (0, .2)}, [(1, 1.3)], [0], 0, 2)["acoustic_basis"], "ESTIMATOR_CONFLICT")
        self.assertEqual(audit_window(["a"], [], a, None, [0], 0, 2)["acoustic_basis"], "NOT_EVALUATED")
        self.assertEqual(audit_window(["a"], [], a, [], [0], 0, 2)["acoustic_basis"], "ESTIMATOR_CONFLICT")
        self.assertEqual(audit_window(["a"], ["a"], {}, [b[0]], [], 0, 2)["acoustic_basis"], "TEXT_ONLY")

    def test_invalid_intervals(self):
        self.assertFalse(valid_interval((float("nan"), 1), 0, 2))
        self.assertFalse(valid_interval((1, .5), 0, 2))
        self.assertFalse(valid_interval((.1, 2.1), 0, 2))
        self.assertTrue(valid_interval((.1, 1), 0, 2))


if __name__ == "__main__":
    unittest.main()
