"""Synthetic aggregate rendering tests; never access an official campaign/data."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


R = module("renderer", "render_results_report.py")
F = module("export_fixtures", "test_export_campaign.py")


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = F.ExportTests("test_source_failure_no_fit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def build(self, complete=False, partial=False):
        f = self.fixture
        if complete:
            for i in range(30):
                f.fit(i)
            f.finish("COMPLETED")
            f.selection()
        elif partial:
            f.fit(0)
            f.fit(1, "RESOURCE_CAP_STOP")
            f.finish()
        else:
            f.finish("FAILED", source=False)
        f.export()
        self.source = f.root / "safe_export"
        self.output = f.root / "rendered"
        self.edit("SUMMARY.json", lambda value: value.update(data_kind="SYNTHETIC_TEST_FIXTURE"))

    def edit(self, name, change):
        path = self.source / name
        value = json.loads(path.read_text(encoding="utf-8"))
        change(value)
        path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")

    def render(self):
        receipt = R.render(self.source, self.output)
        text = (self.output / "RESULTS.md").read_text(encoding="utf-8")
        with (self.output / "CONFIGURATION_TABLE.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        return receipt, text, rows

    def select_reference(self, cid):
        def choice(value):
            value["baseline"]["B_star"] = cid
            value["selection"]["configuration"] = cid
        def summary(value):
            value["B_STAR"] = cid
            value["selection"]["configuration"] = cid
        self.edit("BASELINE_AND_SELECTION.json", choice)
        self.edit("SUMMARY.json", summary)

    def test_complete30_exact_rows_seed17_and_hashes(self):
        self.build(complete=True)
        receipt, text, rows = self.render()
        self.assertEqual(len(rows), 16)
        self.assertEqual(sum(row["status"] == "NOT_RUN" for row in rows), 3)
        self.assertEqual(sum(int(row["additional_fits_in_full_protocol"]) for row in rows), 39)
        self.assertIn("仅合成渲染测试夹具", text)
        self.assertIn("C0-identity", text)
        self.assertIn("固定 seed：**17**", text)
        self.assertIn("| clean | +0.000000 | +0.000000 |", text)
        self.assertFalse(receipt["selection_recomputed"])
        for entry in receipt["files"]:
            raw = (self.output / entry["path"]).read_bytes()
            self.assertEqual(R.digest(raw), entry["sha256"])
            self.assertEqual(len(raw), entry["size_bytes"])
        self.assertNotIn("C:\\private", text)

    def test_prior_selected_metrics_and_null_reason(self):
        self.build(complete=True)
        self.select_reference("PRIOR")
        _, text, rows = self.render()
        self.assertIn("| Pearson | null（zero_prediction_variance） |", text)
        self.assertIn("没有可训练模型 checkpoint", text)
        prior = next(row for row in rows if row["configuration"] == "PRIOR")
        self.assertEqual(prior["clean_macro_F1_seed_sd_ddof1"], "0")

    def test_late_selected_reuses_three_components(self):
        self.build(complete=True)
        self.select_reference("LATE-identity")
        _, text, _ = self.render()
        self.assertIn("LATE 复用三个单模态 seed17 checkpoint", text)
        for architecture in ("B-T", "B-A", "B-V"):
            self.assertIn("| " + architecture + " | `", text)

    def test_partial_no_partial_mean_or_final_selection(self):
        self.build(partial=True)
        _, text, rows = self.render()
        row = next(row for row in rows if row["configuration"] == "B-T-identity")
        self.assertEqual(row["status"], "INCOMPLETE_SEED_SET")
        self.assertEqual(row["clean_macro_F1_mean"], "")
        self.assertIn("没有完整、已锁定的最终模型选择", text)
        self.assertNotIn("Δmacro-F1", text)

    def test_failed_first_fit_not_mislabeled_not_run(self):
        f = self.fixture
        f.fit(0, "FAILED")
        f.finish("FAILED")
        f.export()
        self.source, self.output = f.root / "safe_export", f.root / "rendered"
        self.edit("SUMMARY.json", lambda value: value.update(data_kind="SYNTHETIC_TEST_FIXTURE"))
        _, _, rows = self.render()
        self.assertEqual(rows[0]["status"], "INCOMPLETE_SEED_SET")

    def test_source_failure_preserves_nulls(self):
        self.build()
        _, text, rows = self.render()
        self.assertIn("源数据核验记录缺失", text)
        self.assertTrue(all(row["clean_macro_F1_mean"] == "" for row in rows))

    def test_nan_rejected_before_output_creation(self):
        self.build()
        path = self.source / "SUMMARY.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"runtime_seconds": 123.0', '"runtime_seconds": NaN'), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            self.render()
        self.assertFalse(self.output.exists())

    def test_duplicate_key_rejected(self):
        self.build()
        path = self.source / "SUMMARY.json"
        path.write_text('{"duplicate":1,"duplicate":2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.render()

    def test_summary_count_disagreement_rejected(self):
        self.build(partial=True)
        self.edit("SUMMARY.json", lambda value: value.update(COMPLETED_FITS=2))
        with self.assertRaisesRegex(ValueError, "counts disagree"):
            self.render()

    def test_selected_seed29_rejected(self):
        self.build(complete=True)
        for filename in ("SUMMARY.json", "BASELINE_AND_SELECTION.json"):
            self.edit(filename, lambda value: value["selection"].update(seed=29))
        with self.assertRaisesRegex(ValueError, "Invalid final selection"):
            self.render()

    def test_configuration_mean_mismatch_rejected(self):
        self.build(complete=True)
        self.edit("CONFIGURATION_SUMMARY.json", lambda value: value["configurations"][0]["mean_metrics"]["clean"]["macro_F1"].update(mean=.9))
        with self.assertRaisesRegex(ValueError, "mean/SD mismatch"):
            self.render()

    def test_null_pearson_without_reason_rejected(self):
        self.build(complete=True)
        self.edit("FITS.json", lambda value: value["fits"][0]["metrics"]["clean"].update(Pearson=None, Pearson_reason=None))
        with self.assertRaisesRegex(ValueError, "Null Pearson"):
            self.render()

    def test_duplicate_registered_seed_identity_rejected(self):
        self.build()
        self.edit("FITS.json", lambda value: value["fits"][1].update(seed=17))
        with self.assertRaisesRegex(ValueError, "identity set"):
            self.render()

    def test_completed_without_selection_rejected(self):
        self.build(complete=True)
        for filename in ("SUMMARY.json", "BASELINE_AND_SELECTION.json"):
            self.edit(filename, lambda value: value.update(selection=None))
        with self.assertRaisesRegex(ValueError, "lacks final selection"):
            self.render()

    def test_overwrite_and_repository_output_rejected(self):
        self.build()
        self.render()
        with self.assertRaisesRegex(ValueError, "New separate"):
            self.render()
        repo = self.fixture.root / "fake_repo"
        (repo / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Git repository"):
            R.render(self.source, repo / "new_results")


if __name__ == "__main__":
    unittest.main(verbosity=2)
