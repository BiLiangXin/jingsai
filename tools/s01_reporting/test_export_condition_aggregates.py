"""Full 96/144 synthetic condition-export checks; no model or official data IO."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("condition_export", HERE / "export_condition_aggregates.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
MAIN_SPEC = importlib.util.spec_from_file_location("main_export_fixtures", HERE / "test_export_campaign.py")
MAIN_FIXTURES = importlib.util.module_from_spec(MAIN_SPEC)
MAIN_SPEC.loader.exec_module(MAIN_FIXTURES)
REFERENCE = MAIN_FIXTURES.PROJECT_ROOT / "research/r01/reference.py"
REF = M.reference_at(REFERENCE)
PREREG = json.loads((MAIN_FIXTURES.PROJECT_ROOT / "docs/EXPERIMENT_REGISTER.json").read_text(encoding="utf-8"))["s01_preregistered_fits"]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def synthetic_grid(seed):
    reports = {}
    for condition in REF.conditions():
        cid = REF.condition_id(condition)
        views = []
        for replica in range(3 if condition[2] == "random" else 1):
            # Random replicates intentionally differ; no extra condition weight.
            damaged_classes = [2, None, 0] if condition[2] == "random" else [0, None, 2]
            damaged_values = [1., None, -1.] if condition[2] == "random" else [-1., None, 1.]
            view = REF.attempted_report([0, 1, 2], [-1., 0., 1.], [0, 1, 2], [-1., 0., 1.],
                damaged_classes, damaged_values, [True, False, True], ordered_rows=[0, 1, 2],
                view_fingerprint=M.sha((cid+":"+str(replica)).encode()), replicate=replica)
            views.append(view)
        reports[cid] = views
    return reports


class ConditionTests(unittest.TestCase):
    def setUp(self):
        self.base = MAIN_FIXTURES.ExportTests(methodName="test_source_failure_no_fit")
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.root, self.campaign, self.binding = self.base.root, self.base.campaign, self.base.binding
        self.events = self.base.events

    def fit(self, index, mutate=None):
        self.base.fit(index)
        row = PREREG[index]
        normalizer = row["normalizer"] if row["normalizer"] != "common_preselected" else "identity"
        grid = synthetic_grid(row["seed"])
        if mutate:
            mutate(grid)
        computed = REF.aggregate({row["seed"]: grid}, expected_seeds=(row["seed"],))
        trial = self.campaign / row["trial_id"]
        cfg = dict(row["config"], normalizer=normalizer)
        cfg_hash = M.sha(json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())
        value = json.loads((trial / "evaluation.json").read_text(encoding="utf-8"))
        value.update(attempted96=computed["per_seed"][row["seed"]], condition_reports=grid,
            checkpoint="C:\\private\\SYNTHETIC_CHECKPOINT_DO_NOT_EXPORT.pt")
        write(trial / "evaluation.json", value)
        self.events[-1]["metrics"]["attempted96"] = value["attempted96"]

    def run_export(self):
        self.base.finish("FAILED")
        self.base.export()
        dest = self.root / "safe_conditions"
        receipt = M.export_conditions(self.campaign, dest, REFERENCE, self.root / "safe_export")
        return receipt, json.loads((dest / "CONDITION_AGGREGATES.json").read_text(encoding="utf-8")), dest

    def test_complete_grid_weights_coverage_and_no_fingerprints(self):
        # First three frozen trial records are one architecture/normalizer, all seeds.
        for index in (0, 1, 2):
            self.fit(index)
        receipt, result, dest = self.run_export()
        self.assertEqual(receipt["complete_configurations"], 1)
        configuration = result["configurations"][0]
        self.assertEqual(len(configuration["conditions"]), 96)
        self.assertEqual(sum(c["random_replicates"] for c in configuration["conditions"]), 144)
        self.assertAlmostEqual(configuration["attempted96_across_seeds"]["macro_F1"]["mean"], 5/6)
        for condition in configuration["conditions"]:
            self.assertEqual((condition["eligible_count"], condition["total_count"], condition["CLEAN_ONCE_fallback_count"]), (2, 3, 1))
        self.assertEqual(len(configuration["factor_descriptives"]), 14)
        self.assertEqual(len((dest / "CONDITIONS_PER_SEED.csv").read_text().splitlines()), 289)
        self.assertEqual(len((dest / "CONDITIONS_ACROSS_SEEDS.csv").read_text().splitlines()), 97)
        text = "\n".join(p.read_text(encoding="utf-8") for p in dest.iterdir())
        self.assertNotIn("SYNTHETIC_CHECKPOINT_DO_NOT_EXPORT", text)
        self.assertNotIn('"pairing"', text)
        for view in synthetic_grid(17).values():
            for report in view:
                for fingerprint in (report["pairing"][k] for k in ("population", "eligibility", "view")):
                    self.assertNotIn(fingerprint, text)

    def test_incomplete_seed_set_has_no_across_seed_summary(self):
        self.fit(0)
        _, result, dest = self.run_export()
        configuration = result["configurations"][0]
        self.assertEqual(configuration["status"], "INCOMPLETE_SEED_SET_NOT_RANKED")
        self.assertIsNone(configuration["attempted96_across_seeds"])
        self.assertTrue(all(c["across_seeds"] is None for c in configuration["conditions"]))
        self.assertTrue(all(c["across_seeds"] is None for c in configuration["factor_descriptives"]))
        self.assertEqual(len((dest / "CONDITIONS_PER_SEED.csv").read_text().splitlines()), 97)

    def test_cross_configuration_pairing_and_missing_view_rejected(self):
        self.fit(0)
        self.fit(3, lambda grid: grid["T:0.1:front"][0]["pairing"].update(view="f"*64))
        with self.assertRaises(M.ConditionExportError):
            self.run_export()
        # Independent frozen validator also rejects missing random replicate.
        malformed = synthetic_grid(17)
        malformed["T:0.1:random"].pop()
        with self.assertRaises(ValueError):
            REF.aggregate({17: malformed}, expected_seeds=(17,))

    def test_missing_source_or_checkpoint_or_main_manifest_rejected(self):
        self.fit(0)
        self.base.finish("FAILED")
        self.base.export()
        for path in (self.campaign / "source_verification.json", self.campaign / PREREG[0]["trial_id"] / "best.pt", self.campaign / "campaign_status.json"):
            raw = path.read_bytes()
            path.unlink()
            with self.assertRaises(M.ConditionExportError):
                M.export_conditions(self.campaign, self.root / "rejected_export", REFERENCE, self.root / "safe_export")
            path.write_bytes(raw)
        summary_path = self.root / "safe_export/SUMMARY.json"
        summary = json.loads(summary_path.read_text())
        summary["COMPLETED_FITS"] = 99
        write(summary_path, summary)
        with self.assertRaisesRegex(M.ConditionExportError, "manifest verification"):
            M.export_conditions(self.campaign, self.root / "rejected_export", REFERENCE, self.root / "safe_export")


if __name__ == "__main__":
    unittest.main(verbosity=2)
