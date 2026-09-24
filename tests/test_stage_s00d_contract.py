"""Synthetic S00D contract checks; no official files are opened."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mosei.data.data_contract import validate_label_contract
from mosei.data.dataset import create_aligned_dataset, training_batches
from mosei.data.masks import CorruptionMask, structural_zero_mask, support_from_text_bert
from mosei.data.normalization import IdentityNormalizer, TrainOnlyZScoreNormalizer
from mosei.data.pooling import masked_mean, masked_sum


def fixture(n=4, lengths=None):
    lengths = lengths or [2] * n
    bert = np.zeros((n, 3, 50), dtype=np.int64)
    for i, length in enumerate(lengths):
        bert[i, 1, :length] = 1
    text = np.ones((n, 50, 768), dtype=np.float32)
    audio = np.ones((n, 50, 74), dtype=np.float64)
    vision = np.ones((n, 50, 35), dtype=np.float64)
    audio[0, 0] = 0
    vision[0, 1] = 0
    values = np.array([-1.0, 0.0, 1.0, -0.25][:n], dtype=np.float64)
    classes = np.where(values < 0, 0, np.where(values == 0, 1, 2)).astype(np.float64)
    item = {"text": text, "audio": audio, "vision": vision, "text_bert": bert,
            "classification_labels": classes, "regression_labels": values,
            "id": ["private"] * n, "raw_text": ["private"] * n}
    return {"train": item, "valid": {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in item.items()},
            "test": object()}


class ContractTests(unittest.TestCase):
    def test_01_support_from_channel_1(self):
        self.assertEqual(support_from_text_bert(fixture()["train"]["text_bert"]).sum(), 8)

    def test_02_nonbinary_rejected(self):
        x = fixture()["train"]["text_bert"]; x[0, 1, 0] = 2
        with self.assertRaises(ValueError): support_from_text_bert(x)

    def test_03_nonprefix_rejected(self):
        x = fixture()["train"]["text_bert"]; x[0, 1, 0] = 0
        with self.assertRaises(ValueError): support_from_text_bert(x)

    def test_04_zero_length_rejected(self):
        x = fixture()["train"]["text_bert"]; x[0, 1] = 0
        with self.assertRaises(ValueError): support_from_text_bert(x)

    def test_05_shape_rejected(self):
        with self.assertRaises(ValueError): support_from_text_bert(np.zeros((2, 2, 50), dtype=int))

    def test_06_float_channel_rejected(self):
        with self.assertRaises(ValueError): support_from_text_bert(fixture()["train"]["text_bert"].astype(float))

    def test_07_structural_zero_exact(self):
        self.assertEqual(structural_zero_mask(np.array([[0., 0.], [0., 1e-40]])).tolist(), [True, False])

    def test_08_zero_not_padding(self):
        d = create_aligned_dataset(fixture(), "train")
        self.assertTrue(d.masks.audio_structural_zero_mask[0, 0])
        self.assertFalse(d.masks.padding_mask[0, 0])

    def test_09_zero_not_corruption(self):
        d = create_aligned_dataset(fixture(), "train")
        self.assertFalse(d.batch([0]).corruption.audio_corruption_mask.any())

    def test_10_observed_mask(self):
        d = create_aligned_dataset(fixture(), "train")
        self.assertFalse(d.masks.audio_observed_mask[0, 0])
        self.assertFalse(d.masks.vision_observed_mask[0, 1])
        self.assertTrue(d.masks.text_observed_mask[0, 0])

    def test_11_shared_support(self):
        m = create_aligned_dataset(fixture(), "train").masks
        self.assertTrue(np.array_equal(m.text_support_mask, m.audio_support_mask))
        self.assertTrue(np.array_equal(m.text_support_mask, m.vision_support_mask))

    def test_12_padding_excluded_sum(self):
        d = create_aligned_dataset(fixture(), "train"); b = d.batch([0])
        altered = b.text.copy(); altered[:, 2:] = 1e20
        np.testing.assert_array_equal(masked_sum(b.text, b.text_support_mask), masked_sum(altered, b.text_support_mask))

    def test_13_nonzero_text_tail_excluded_mean(self):
        d = create_aligned_dataset(fixture(), "train"); b = d.batch([0])
        altered = b.text.copy(); altered[:, 2:] = -3456.0
        np.testing.assert_array_equal(masked_mean(b.text, b.text_support_mask), masked_mean(altered, b.text_support_mask))

    def test_14_zero_count_pool_safe(self):
        out = masked_mean(np.ones((1, 2, 3)), np.zeros((1, 2), dtype=bool))
        np.testing.assert_array_equal(out, np.zeros((1, 3)))

    def test_15_normalizer_train_only(self):
        d = create_aligned_dataset(fixture(), "train")
        self.assertEqual(TrainOnlyZScoreNormalizer().fit(d).fit_split, "train")

    def test_16_normalizer_valid_fit_rejected(self):
        with self.assertRaises(ValueError): TrainOnlyZScoreNormalizer().fit(create_aligned_dataset(fixture(), "valid"))

    def test_17_identity_valid_fit_rejected(self):
        with self.assertRaises(ValueError): IdentityNormalizer().fit(create_aligned_dataset(fixture(), "valid"))

    def test_18_test_factory_quarantined_before_index(self):
        class Guard(dict):
            def __getitem__(self, key):
                if key == "test": raise AssertionError("test indexed")
                return super().__getitem__(key)
        with self.assertRaises(ValueError): create_aligned_dataset(Guard(fixture()), "test")

    def test_19_test_fit_rejected(self):
        d = create_aligned_dataset(fixture(), "train")
        object.__setattr__(d, "split", "test")
        with self.assertRaises(ValueError): TrainOnlyZScoreNormalizer().fit(d)

    def test_20_std_zero_safe(self):
        d = create_aligned_dataset(fixture(), "train"); n = TrainOnlyZScoreNormalizer().fit(d)
        self.assertGreater(n.stats["text"]["zero_std_feature_count"], 0)
        self.assertTrue(np.isfinite(n.transform(d.batch([0])).text).all())

    def test_21_nan_rejected(self):
        source = fixture(); source["train"]["audio"][0, 0, 0] = np.nan
        with self.assertRaises(ValueError): create_aligned_dataset(source, "train")

    def test_22_inf_rejected(self):
        source = fixture(); source["train"]["vision"][0, 0, 0] = np.inf
        with self.assertRaises(ValueError): create_aligned_dataset(source, "train")

    def test_23_label_contract(self):
        c, r = validate_label_contract(np.array([0, 1, 2]), np.array([-1., 0., 1.]))
        self.assertEqual((c.tolist(), r.tolist()), ([0, 1, 2], [-1., 0., 1.]))

    def test_24_neutral_exact_zero(self):
        with self.assertRaises(ValueError): validate_label_contract(np.array([1]), np.array([1e-8]))

    def test_25_model_input_allowlist(self):
        inputs = create_aligned_dataset(fixture(), "train").batch([0]).model_inputs
        self.assertEqual(set(inputs), {"text", "audio", "vision", "text_support_mask", "audio_support_mask",
                                        "vision_support_mask", "text_observed_mask", "audio_observed_mask",
                                        "vision_observed_mask", "padding_mask"})

    def test_26_batch_shapes_dtypes(self):
        b = create_aligned_dataset(fixture(), "train").batch([0, 1])
        self.assertEqual((b.text.shape, b.audio.shape, b.vision.shape), ((2, 50, 768), (2, 50, 74), (2, 50, 35)))
        self.assertEqual((b.text.dtype, b.audio.dtype, b.vision.dtype), (np.float32, np.float32, np.float32))

    def test_27_source_no_mutation(self):
        source = fixture(); original = source["train"]["text"].copy()
        d = create_aligned_dataset(source, "train"); TrainOnlyZScoreNormalizer().fit(d).transform(d.batch([0]))
        np.testing.assert_array_equal(source["train"]["text"], original)

    def test_28_attachment_guard(self):
        class Guard(dict):
            def __getitem__(self, key):
                if key not in {"train", "valid"}: raise AssertionError("outside authorized split")
                return super().__getitem__(key)
        create_aligned_dataset(Guard(fixture()), "train")

    def test_29_reload_consistency(self):
        d = create_aligned_dataset(fixture(), "train"); n = TrainOnlyZScoreNormalizer().fit(d)
        reloaded = TrainOnlyZScoreNormalizer.from_state_dict(n.state_dict())
        np.testing.assert_array_equal(n.transform(d.batch([0])).audio, reloaded.transform(d.batch([0])).audio)

    def test_30_deterministic_training_shuffle(self):
        d = create_aligned_dataset(fixture(), "train")
        a = [b.regression_target.tolist() for b in training_batches(d, 2, seed=42)]
        b = [b.regression_target.tolist() for b in training_batches(d, 2, seed=42)]
        self.assertEqual(a, b)

    def test_31_valid_training_loader_rejected(self):
        with self.assertRaises(ValueError): list(training_batches(create_aligned_dataset(fixture(), "valid"), 2, seed=1))

    def test_32_corruption_padding_rejected(self):
        m = create_aligned_dataset(fixture(), "train").masks
        c = CorruptionMask.empty(m); c.text_corruption_mask[0, 10] = True
        with self.assertRaises(ValueError): c.validate_against(m)

    def test_33_corruption_natural_zero_rejected(self):
        m = create_aligned_dataset(fixture(), "train").masks
        c = CorruptionMask.empty(m); c.audio_corruption_mask[0, 0] = True
        with self.assertRaises(ValueError): c.validate_against(m)

    def test_34_normalizer_nonobserved_unchanged(self):
        d = create_aligned_dataset(fixture(), "train"); b = d.batch([0]); out = TrainOnlyZScoreNormalizer().fit(d).transform(b)
        np.testing.assert_array_equal(out.audio[~b.audio_observed_mask], b.audio[~b.audio_observed_mask])

    def test_35_normalizer_excludes_zero_rows(self):
        d = create_aligned_dataset(fixture(), "train"); n = TrainOnlyZScoreNormalizer().fit(d)
        self.assertEqual(n.stats["audio"]["count"], int(d.masks.audio_observed_mask.sum()))

    def test_36_torch_bridge_separation(self):
        b = create_aligned_dataset(fixture(), "train").batch([0])
        with patch.dict(sys.modules, {"torch": None}):
            with self.assertRaises(RuntimeError): b.to_torch()


if __name__ == "__main__":
    unittest.main()
