import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from autoqc_a4 import check_unchanged_card, feature_path, unmapped_ordinary_or_unknown


class A4ContractTests(unittest.TestCase):
    def fixture(self):
        window = {"feature_start": 1, "feature_end_exclusive": 3, "signed_full_minus_deleted": -.25}
        card = {"sample_id": "synthetic", "polarity": "Neutral", "intensity": 0.1,
                "class_main_modality": "text", "reg_main_modality": "vision",
                "class_phi": {"T": .1, "A": -.2, "V": .3},
                "reg_phi": {"T": -.1, "A": .2, "V": .4},
                "windows": [{"target": "class", "original": window},
                            {"target": "reg", "original": window}]}
        row = {"sample_id": "synthetic", "polarity": "Neutral", "intensity": "0.1",
               "class_main_modality": "text", "reg_main_modality": "vision",
               "class_windows_json": json.dumps([window]), "reg_windows_json": json.dumps([window])}
        for target in ("class", "reg"):
            for modality in ("T", "A", "V"):
                row[f"{target}_phi_{modality}"] = str(card[target + "_phi"][modality])
        return card, row

    def test_frozen_values_and_fail_closed(self):
        card, row = self.fixture()
        check_unchanged_card(card, row)
        for key, changed in (("polarity", "Positive"), ("class_phi_T", "0.2"),
                             ("class_windows_json", "[]")):
            modified = dict(row)
            modified[key] = changed
            with self.assertRaises(ValueError):
                check_unchanged_card(card, modified)

    def test_unmapped_reason_abstention(self):
        self.assertFalse(unmapped_ordinary_or_unknown([{"reason": "SPECIAL_TOKEN_NO_DIRECT_WORD_SPAN"},
                                                       {"reason": "PUNCTUATION_NO_WORD_SPAN"}]))
        self.assertTrue(unmapped_ordinary_or_unknown([{"reason": "UNMAPPED_ORDINARY"}]))
        self.assertTrue(unmapped_ordinary_or_unknown([{}]))

    def test_relative_feature_binding(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "videos").mkdir()
            video = root / "videos" / "01.mp4"
            feature = root / "01.pkl"
            feature.write_bytes(b"synthetic")
            self.assertEqual(feature_path({"source_file": "aligned/01.pkl"}, video), feature)
            with self.assertRaises(ValueError):
                feature_path({"source_file": "aligned/02.pkl"}, video)


if __name__ == "__main__":
    unittest.main()
