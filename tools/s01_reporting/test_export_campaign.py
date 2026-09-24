"""Synthetic aggregate exporter fixtures. No training or official data reads."""
import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("safe_export", HERE / "export_campaign.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
PROJECT_ROOT = Path(os.environ.get("S01_REPORTING_PROJECT", str(HERE.parents[1]))).resolve()
TEST_TMP_ROOT = Path(os.environ.get("S01_REPORTING_TEST_TMP", tempfile.gettempdir())).resolve()
CANONICAL = json.loads((PROJECT_ROOT / "docs/EXPERIMENT_REGISTER.json").read_text(encoding="utf-8"))["s01_preregistered_fits"]
AT = "2026-09-24T21:00:00+00:00"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def metric(pearson=0.5, reason=None):
    return dict(Accuracy=1., macro_F1=1., weighted_F1=1., MAE=.2, Pearson=pearson, Pearson_reason=reason,
                n=3, confusion=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                per_class=[dict(**{"class": k}, precision=1., recall=1., F1=1., support=1) for k in range(3)])


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="export_fixture_", dir=TEST_TMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.campaign = self.root / "campaign"
        self.campaign.mkdir()
        self.registry = self.root / "repository/docs/EXPERIMENT_REGISTER.json"
        write(self.registry, {"s01_preregistered_fits": CANONICAL})
        self.binding = dict(campaign_id="S01-SYNTHETIC-FIXTURE-ONLY", authorization_mode=M.MODE,
            commit="a"*40, execution_config_sha256="b"*64, authorized_manifest_sha256="c"*64,
            execution_fit_budget=30, resource_walltime_cap_hours=12, per_fit_walltime_cap_hours=2,
            latest_compute_finish="2026-09-25T18:00:00+08:00")
        self.provenance = dict(code_commit="a"*40, source_sha256=M.EXPECTED_SOURCE,
            execution_config_hash="b"*64, protocol_freeze="R01-FREEZE-01")
        write(self.campaign / "campaign.json", dict(authorization=dict(binding=self.binding),
            execution_fit_budget=30, preregistered=CANONICAL, deferred_trial_ids=[r["trial_id"] for r in CANONICAL[30:]]))
        self.events = []

    def source(self):
        write(self.campaign / "source_verification.json", dict(sha256=M.EXPECTED_SOURCE, train_count=3, valid_count=3,
              splits_used=["train", "valid"], test_used=False, special_sets_opened=False))

    def fit(self, index, status="COMPLETED"):
        row = CANONICAL[index]
        trial = self.campaign / row["trial_id"]
        trial.mkdir()
        normalizer = row["normalizer"] if row["normalizer"] != "common_preselected" else "identity"
        cfg_hash = M.sha(M.canonical(dict(row["config"], normalizer=normalizer)))
        start = dict(trial_id=row["trial_id"], previous_status="NOT_RUN", status="RUNNING", timestamp=AT,
            retry_count=0, architecture=row["architecture"], normalizer=normalizer, seed=row["seed"],
            config_hash=cfg_hash, code_commit="a"*40, source_sha256=M.EXPECTED_SOURCE, metrics=None)
        self.events.append(start)
        write(trial / "optimizer_started.json", dict(data_kind="OFFICIAL_TRAIN_VALID", architecture=row["architecture"], seed=row["seed"], started_at=AT))
        if status == "RUNNING":
            return
        if status != "COMPLETED":
            self.events.append(dict(trial_id=row["trial_id"], previous_status="RUNNING", status=status, timestamp=AT,
                retry_count=0, runtime_seconds=3., metrics=None, failure_reason="ValueError: Resource wall-time cap reached at C:\\private\\secret-data.pkl"))
            return
        (trial / "best.pt").write_bytes(b"SYNTHETIC TEST BYTES, NOT A MODEL")
        cp_sha = M.sha((trial / "best.pt").read_bytes())
        attempted = dict(macro_F1=.5, MAE=.8)
        epoch = dict(epoch=1, data_kind="OFFICIAL_TRAIN_VALID", clean=metric(), objective_score=attempted)
        (trial / "epoch_events.jsonl").write_text(json.dumps(epoch) + "\n", encoding="utf-8")
        result = dict(trial_id=row["trial_id"], architecture=row["architecture"], normalizer=normalizer, seed=row["seed"],
            evidence="VERIFIED_OFFICIAL_VALID_RESULT", provenance=self.provenance, config_hash=cfg_hash,
            checkpoint_sha256=cp_sha, checkpoint="C:\\private\\secret-model.pt", clean=metric(), attempted96=attempted,
            condition_reports={"DO_NOT_EXPORT": [{"ordinal": 123, "label": -2, "mask": [False]}]},
            selected_epoch=1, evaluated_epochs=1, parameters=20, runtime_seconds=2., started_at=AT, finished_at=AT)
        write(trial / "evaluation.json", result)
        self.events.append(dict(trial_id=row["trial_id"], previous_status="RUNNING", status="COMPLETED", timestamp=AT,
            retry_count=0, runtime_seconds=3., selected_epoch=1, checkpoint_sha256=cp_sha,
            checkpoint="C:\\private\\secret-model.pt", metrics=dict(clean=metric(), attempted96=attempted)))

    def finish(self, status="PARTIAL_RESOURCE_STOP", source=True):
        if source:
            self.source()
        (self.campaign / "events.jsonl").write_text("".join(json.dumps(row)+"\n" for row in self.events), encoding="utf-8")
        counts = {s: sum(r["status"] == s for r in self.events) for s in ("RUNNING", "COMPLETED", "FAILED", "RESOURCE_CAP_STOP")}
        write(self.campaign / "campaign_status.json", dict(campaign_id=self.binding["campaign_id"], execution_fit_budget=30,
            claimed=True, status=status, counts=counts, runtime_seconds=123., official_data_training_performed=bool(self.events),
            error=None if status == "COMPLETED" else "ValueError: Resource wall-time cap reached in C:\\private\\secret.log"))

    def export(self, watchdog=None):
        dest = self.root / "safe_export"
        receipt = M.export_campaign(self.campaign, dest, self.registry, watchdog)
        return receipt, {p.name: json.loads(p.read_text(encoding="utf-8")) for p in dest.glob("*.json")}

    def selection(self, chosen="C0-identity"):
        ids = sorted({a+"-"+n for a in M.ARCHS[:4] for n in M.NORMALIZERS} | {"LATE-identity", "LATE-zscore", "PRIOR"})
        reports = {cid: {str(s): dict(clean=metric(None, "zero_prediction_variance") if cid == "PRIOR" else metric(), parameters=0 if cid == "PRIOR" else 20) for s in M.SEEDS} for cid in ids}
        ranked = [dict(id=cid, F=1., MAE=.2, clean_F=1., clean_MAE=.2, parameters=0 if cid == "PRIOR" else 20) for cid in ids]
        write(self.campaign / "baseline_lock.json", dict(common_normalizer="identity", B_star=ids[0], provenance=self.provenance, ranked=ranked, baseline_clean_reports=reports))
        write(self.campaign / "selection.json", dict(common_normalizer="identity", B_star=ids[0], provenance=self.provenance, executed_budget=30,
            decision=dict(configuration=chosen, seed=17, reason="WINNER_FIXED_SEED_GUARD_PASS")))

    def test_source_failure_no_fit(self):
        self.finish("FAILED", source=False)
        _, result = self.export()
        summary = result["SUMMARY.json"]
        self.assertEqual(summary["OFFICIAL_DATA_TRAINING_PERFORMED"], "NO")
        self.assertIsNone(summary["source_verification"])
        self.assertEqual(len(result["FITS.json"]["fits"]), 39)
        self.assertTrue(all(r["status"] == "NOT_RUN" and r["metrics"] is None for r in result["FITS.json"]["fits"]))

    def test_partial_safe_aggregate_and_failed_marker(self):
        self.fit(0)
        self.fit(1, "RESOURCE_CAP_STOP")
        self.finish()
        _, result = self.export()
        summary = result["SUMMARY.json"]
        self.assertEqual((summary["EXECUTED_FITS"], summary["COMPLETED_FITS"], summary["RESOURCE_CAP_STOP_FITS"]), (2, 1, 1))
        self.assertEqual(result["FITS.json"]["fits"][1]["successful_optimizer_step_proven"], "UNKNOWN")
        self.assertIsNone(result["FITS.json"]["fits"][1]["metrics"])
        public = json.dumps(result)
        for prohibited in ("secret-model", "secret-data", "secret.log", "DO_NOT_EXPORT", "ordinal", "condition_reports", "C:\\\\private"):
            self.assertNotIn(prohibited, public)

    def test_all30_completed_and_seed_aggregation(self):
        for i in range(30):
            self.fit(i)
        self.finish("COMPLETED")
        self.selection()
        _, result = self.export()
        self.assertEqual(result["SUMMARY.json"]["COMPLETED_FITS"], 30)
        self.assertEqual(result["SUMMARY.json"]["counts"]["NOT_RUN"], 9)
        self.assertEqual(len(result["CONFIGURATION_SUMMARY.json"]["configurations"]), 10)
        self.assertEqual(result["CONFIGURATION_SUMMARY.json"]["configurations"][0]["mean_metrics"]["clean"]["macro_F1"]["seed_sd_ddof1"], 0.)

    def test_pearson_null_reason_and_nonfinite_rejected(self):
        with self.assertRaises(M.ExportError):
            M.clean_metrics(metric(None, None))
        with self.assertRaises(M.ExportError):
            M.clean_metrics(metric(float("nan"), None))
        with self.assertRaises(M.ExportError):
            M.clean_metrics(metric(.5, "zero_prediction_variance"))
        self.assertIsNone(M.clean_metrics(metric(None, "zero_prediction_variance"))["Pearson"])

    def test_checkpoint_tampering_rejected(self):
        self.fit(0)
        self.finish("FAILED")
        (self.campaign / CANONICAL[0]["trial_id"] / "best.pt").write_bytes(b"changed bytes")
        with self.assertRaises(M.ExportError):
            self.export()

    def test_missing_final_status_requires_watchdog(self):
        self.fit(0, "RUNNING")
        self.source()
        (self.campaign / "events.jsonl").write_text("".join(json.dumps(row)+"\n" for row in self.events), encoding="utf-8")
        with self.assertRaises(M.ExportError):
            self.export()
        watchdog = self.root / "watchdog.json"
        write(watchdog, dict(campaign_id=self.binding["campaign_id"], watchdog_fired=True, automatic_retry=False,
            exit_code=1, stop_reason="TOTAL_OR_ABSOLUTE_WALLTIME_CAP", started_at=AT, finished_at=AT,
            command=["C:\\private\\private-interpreter.exe"]))
        _, result = self.export(watchdog)
        self.assertEqual(result["SUMMARY.json"]["S01_EXECUTION_STATUS"], "PARTIAL_RESOURCE_STOP")
        self.assertEqual(result["SUMMARY.json"]["INCOMPLETE_FITS_WITHOUT_TERMINAL_EVENT"], 1)

    def test_no_overwrite(self):
        self.finish("FAILED", source=False)
        self.export()
        with self.assertRaises(M.ExportError):
            self.export()

    def test_extra_event_outside_selected_budget_rejected(self):
        self.fit(30, "RUNNING")
        self.finish("FAILED")
        with self.assertRaises(M.ExportError):
            self.export()

    def test_deferred_unrun_selection_rejected(self):
        for index in range(30):
            self.fit(index)
        self.finish("COMPLETED")
        self.selection("R2-identity")
        with self.assertRaisesRegex(M.ExportError, "outside authorized"):
            self.export()

    def test_partial_seed_selection_rejected(self):
        for index in range(25):
            self.fit(index)
        self.finish("FAILED")
        self.selection("C0-identity")
        with self.assertRaisesRegex(M.ExportError, "three completed"):
            self.export()


if __name__ == "__main__":
    unittest.main(verbosity=2)
