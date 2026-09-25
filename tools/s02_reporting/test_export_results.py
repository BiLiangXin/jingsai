"""Synthetic aggregate fixtures only; no tensors, models, official samples or data."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PROJECT = Path(os.environ.get("S02_PROJECT_ROOT", str(Path.cwd()))).resolve()
spec = importlib.util.spec_from_file_location("s02_export_draft", HERE / "export_results.py")
E = importlib.util.module_from_spec(spec);spec.loader.exec_module(E)
R = E.module_at(PROJECT / "research/r01/reference.py", E.REFERENCE)
S = E.module_at(PROJECT / "src/mosei/s02/selection.py", E.SELECTION)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def write_epochs(folder, epoch, count=11):
    rows=[]
    for i in range(1,count+1):
        row=copy.deepcopy(epoch)
        row.update(epoch=i, selected_epoch=1, checkpoint_saved=i==1,
                   early_stop=i==11, total_elapsed_seconds=i*2.1)
        rows.append(row)
    (folder/"epoch_events.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf8")


def make_fixture(base, mode="complete"):
    base.mkdir()
    cfg = dict(campaign_id="S02-SYNTHETIC-EXPORT-FIXTURE", execution_fit_budget=12, postprocess_budget=15,
        model_seeds=list(E.SEEDS), recipes=list(E.RECIPES), variants=["W0", "W1", "W2"], betas=[-.4, -.2, 0., .2, .4],
        source_sha256=E.SOURCE, test_authorized=False, attachment3_4_authorized=False)
    binding = dict(campaign_id=cfg["campaign_id"], commit="c" * 40, config_hash=E.canonical(cfg), manifest_sha256="d" * 64)
    write(base / "campaign.json", dict(binding=binding, config=cfg, started="2026-09-25T02:00:00+00:00"))
    write(base / "CURRENT_CHAMPION.json", dict(current_champion=E.BASE, seed=17))
    terminal = dict(status="COMPLETED" if mode in ("complete", "promotion") else "BLOCKED", error=None, phase="SELECTION", current="M4-s43",
        fit_completed=12 if mode in ("complete", "promotion") else 3 if mode == "partial" else 0,
        postprocess_completed=0 if mode in ("source_failure", "partial_post") else 15,
        fit_budget=12, postprocess_budget=15, promoted=False, current_champion=E.BASE, runtime_seconds=100.,
        binding=binding, finished="2026-09-25T02:03:00+00:00", authorization_status="CONSUMED", retry_budget=0)
    events = []
    if mode == "source_failure":
        terminal.update(phase="SOURCE", current=None, error="ValueError: " + str(base / "private"))
        events.append(dict(kind="CAMPAIGN_FAILURE", id=None, phase="SOURCE", status="BLOCKED", error=terminal["error"]))
    else:
        write(base / "source_verification.json", dict(source_sha256=E.SOURCE, train_count=3, valid_count=3,
            splits_used=["train", "valid"], test_used=False, special_sets_opened=False,
            monolithic_pickle_deserialized=True, test_fields_accessed=False))
        clean = R.metrics([0, 1, 2], [-1., 0., 1.], [0, 1, 2], [-.8, .2, .8])
        reports = {}
        for condition in R.conditions():
            cid = R.condition_id(condition)
            reports[cid] = [R.attempted_report([0, 1, 2], [-1., 0., 1.], [0, 1, 2], [-.8, .2, .8],
                [0, 1, 2], [-.8, .2, .8], [True, False, True], ordered_rows=[0, 1, 2],
                view_fingerprint=E.sha((cid+str(rep)).encode()), replicate=rep) for rep in range(3 if condition[2] == "random" else 1)]
        evaluation = dict(status="COMPLETED", clean=clean, attempted96=R.checkpoint_score(reports, 17), condition_reports=reports,
            sign_disagreement_clean=dict(disagreement_count=1, total_count=3, fraction=1/3), sign_disagreement_attempted96=1/3)
        components = {}
        prov = dict(code_commit="a"*40, source_sha256=E.SOURCE, execution_config_hash="b"*64, protocol_freeze="R01-FREEZE-01")
        for seed in E.SEEDS:
            components[str(seed)] = {}
            for name in ("cat", "text"):
                raw = f"synthetic cache {name} {seed}".encode();(base / f"component_{name}_s{seed}.pt").write_bytes(raw)
                components[str(seed)][name] = dict(checkpoint_sha256="e"*64, config_hash="f"*64, normalizer_hash="1"*64,
                    parameters=10 if name == "cat" else 5, runtime_seconds=1., provenance=prov, cache_sha256=E.sha(raw))
        write(base / "component_restore_receipt.json", components)
        baseline = S.summarize_candidate(E.BASE, {s: evaluation for s in E.SEEDS}, parameters=10, inference_cost=1.)
        summaries = []
        for pid, candidate in E.POST.items():
            events.append(dict(kind="POSTPROCESS", id=pid, status="RUNNING"))
            for seed in E.SEEDS:
                value = dict(evaluation, seed=seed, candidate=candidate, component_provenance=components[str(seed)],
                             code_commit=binding["commit"], execution_config_hash=binding["config_hash"])
                write(base / pid / f"evaluation_s{seed}.json", value)
                if mode == "partial_post":
                    break
            if mode == "partial_post":
                terminal.update(phase="POSTPROCESS", current=pid, error="RuntimeError: " + str(base / "private"))
                break
            events.append(dict(kind="POSTPROCESS", id=pid, status="COMPLETED", seeds=list(E.SEEDS)))
            text = candidate["variant"] != "W0"
            summaries.append(S.summarize_candidate(pid, {s: evaluation for s in E.SEEDS}, parameters=15 if text else 10, inference_cost=2. if text else 1.))
        provenance = dict(code_commit=binding["commit"], source_sha256=E.SOURCE, execution_config_hash=binding["config_hash"],
                          protocol="S02-RES-01", authorization_manifest_sha256=binding["manifest_sha256"])
        if mode != "partial_post":
            for recipe in E.RECIPES:
                per_seed = {}
                for seed in E.SEEDS:
                    tid=f"{recipe}-s{seed}";folder=base/tid;folder.mkdir()
                    events.append(dict(kind="FIT", id=tid, status="RUNNING"))
                    trial=dict(recipe=recipe, seed=seed, architecture=recipe, normalizer="zscore", execution_config_hash=binding["config_hash"],
                        lr=.001, weight_decay=.0001, batch_size=32, clip_norm=1, max_epochs=100, checkpoint="clean_F_then_MAE",
                        p_corrupt=.25 if recipe in ("M3", "M4") else 0., KD=.1 if recipe=="M4" else 0., tau=2)
                    write(folder / "config.json", dict(config=trial, provenance=provenance))
                    write(folder / "optimizer_started.json", dict(recipe=recipe, seed=seed, time="2026-09-25T02:01:00+00:00", data_kind="OFFICIAL_TRAIN_VALID"))
                    best=b"synthetic checkpoint best";last=b"synthetic checkpoint last"
                    (folder / "best.pt").write_bytes(best);(folder / "last.pt").write_bytes(last)
                    epoch=dict(epoch=1, selected_epoch=1, early_stop=False, checkpoint_saved=True, clean=clean,
                        train_loss=dict(CE=1., weighted_CE=1., MAE=.6, KD=0., total=1.2), train_online_metrics=clean,
                        train_metric_scope="ONLINE_PRE_UPDATE_CURRENT_VIEW_DIAGNOSTIC_NOT_CHECKPOINT_EVALUATION",
                        train_samples=3, learning_rate=.001, valid_supervised_loss=1.2,
                        corruption_counts=dict(rows=3, clean_requested=3, eligible=0, ineligible=0),
                        train_seconds=1., validation_seconds=.5, epoch_seconds=2., total_elapsed_seconds=2.1)
                    write_epochs(folder,epoch,count=1 if mode == "partial" and recipe == "M2" else 11)
                    if mode == "partial" and recipe == "M2":
                        events.append(dict(kind="FIT", id=tid, status="FAILED", error="RuntimeError: " + str(base / "private")))
                        terminal.update(phase="FIT", current=tid, error="RuntimeError: " + str(base / "private"))
                        break
                    value=dict(evaluation, recipe=recipe, seed=seed, parameters=77542, selected_epoch=1, evaluated_epochs=11,
                        checkpoint_sha256=E.sha(best), last_checkpoint_sha256=E.sha(last), config_hash=E.canonical(trial), provenance=provenance,
                        runtime_seconds=3., inference_seconds=2.)
                    if mode == "promotion" and recipe == "M1":
                        value=copy.deepcopy(value);value["clean"]["MAE"]=.1
                        for views in value["condition_reports"].values():
                            for view in views:view["attempted"]["MAE"]=.1
                        value["attempted96"]=R.checkpoint_score(value["condition_reports"],seed)
                        epoch["clean"]=value["clean"]
                        write_epochs(folder,epoch)
                    write(folder / "evaluation.json", value);write(folder / "source_verification.json", dict(before=E.SOURCE, after=E.SOURCE))
                    events.append(dict(kind="FIT", id=tid, status="COMPLETED", checkpoint_sha256=E.sha(best)))
                    per_seed[seed]=value
                summaries.append(S.summarize_candidate(recipe, per_seed, parameters=77542, inference_cost=2. if per_seed else None))
                if mode == "partial" and recipe == "M2":
                    break
        comparison = dict(baseline=baseline, candidates=summaries, selection=S.choose_champion(baseline, summaries, comparison_complete=mode in ("complete", "promotion")),
                          robust_ranking=S.robust_ranking(baseline, summaries), clean_pareto=S.clean_pareto([baseline,*summaries]))
        write(base / "comparison.json", comparison)
        if mode not in ("complete", "promotion"):
            events.append(dict(kind="CAMPAIGN_FAILURE", id=terminal["current"], phase=terminal["phase"], status="BLOCKED", error=terminal["error"]))
    write(base / "campaign_status.json", terminal)
    if mode == "promotion":
        terminal.update(promoted=True,current_champion="M1",promotion_requires_matching_atomic_pointer=True)
        write(base/"campaign_status.json",terminal)
        write(base/"winner_restore.json",dict(status="PASS",winner="M1",seed=17,exact_tensor_values_equal=True,full144_views=True))
        write(base/"CURRENT_CHAMPION.json",dict(current_champion="M1",seed=17,
            terminal_status_sha256=E.fingerprint(base/"campaign_status.json")["sha256"],comparison_sha256=E.fingerprint(base/"comparison.json")["sha256"]))
    (base / "events.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events), encoding="utf-8")
    return base


class ExportChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="s02_aggregate_fixture_");self.root=Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def export(self, mode="complete"):
        campaign=make_fixture(self.root/"private_fixture",mode);output=self.root/"public_export"
        result=E.export(campaign,output,PROJECT)
        return campaign,output,result
    def test_full_grid_complete_manifest_epochs_and_no_private_rows(self):
        campaign,out,result=self.export()
        self.assertEqual(result["fits_completed"],12);self.assertEqual(result["postprocess_completed"],15)
        self.assertEqual(len(list((out/"conditions").glob("*.json"))),19)
        self.assertEqual(len(list((out/"epochs").glob("*.json"))),12)
        summary=json.loads((out/"SUMMARY.json").read_bytes());self.assertEqual(summary["counts"]["COMPLETED"],27)
        manifest=json.loads((out/"MANIFEST.json").read_bytes())
        for r in manifest["files"]:
            self.assertEqual(E.fingerprint(out/r["path"]),{k:r[k] for k in ("size","sha256")})
            raw=(out/r["path"]).read_text();self.assertNotIn(str(campaign),raw);self.assertNotIn('"pairing"',raw)
            self.assertLessEqual((out/r["path"]).stat().st_size,2**20)
        self.assertEqual(json.loads((out/"EPOCH_CURVES.json").read_bytes())["total_completed_epoch_rows"],132)
    def test_partial_failure_preserves_epochs_and_null_unrun_metrics(self):
        _,out,_=self.export("partial")
        fits=json.loads((out/"FITS.json").read_bytes());failed=next(r for r in fits if r["id"]=="M2-s17")
        self.assertEqual(failed["status"],"FAILED");self.assertEqual(failed["completed_epoch_events"],1)
        self.assertIsNone(failed["metrics"]);self.assertTrue(failed["optimizer_attempted"])
        self.assertTrue(all(r["metrics"] is None for r in fits if r["status"]=="NOT_RUN"))
        self.assertEqual(json.loads((out/"EPOCH_CURVES.json").read_bytes())["total_completed_epoch_rows"],34)
    def test_partial_post_keeps_seed_and_no_three_seed_mean(self):
        _,out,_=self.export("partial_post")
        condition=json.loads(next((out/"conditions").glob("*.json")).read_bytes())
        self.assertEqual(condition["status"],"INCOMPLETE_NOT_RANKED")
        self.assertIsNone(condition["conditions"][0]["across_seeds"])
    def test_source_failure_exports_no_fake_training_and_sanitizes_error(self):
        _,out,_=self.export("source_failure")
        summary=json.loads((out/"SUMMARY.json").read_bytes())
        self.assertFalse(summary["optimizer_attempted"]);self.assertEqual(summary["counts"]["NOT_RUN"],27)
        self.assertIsNone(summary["source_verification"]);self.assertEqual(summary["exception_category"],"ValueError")
    def test_checkpoint_tamper_rejected_before_output(self):
        campaign=make_fixture(self.root/"private_fixture");(campaign/"M1-s17"/"best.pt").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"checkpoint hash"):
            E.export(campaign,self.root/"output",PROJECT)
        self.assertFalse((self.root/"output").exists())
    def test_invalid_pairing_population_rejected(self):
        campaign=make_fixture(self.root/"private_fixture","partial_post")
        file=campaign/next(iter(E.POST))/"evaluation_s17.json";value=json.loads(file.read_bytes())
        cid=next(iter(value["condition_reports"]));value["condition_reports"][cid][0]["total_count"]=2;write(file,value)
        with self.assertRaises(ValueError):E.export(campaign,self.root/"output",PROJECT)
    def test_premature_selection_rejected(self):
        campaign=make_fixture(self.root/"private_fixture","partial_post")
        file=campaign/"comparison.json";value=json.loads(file.read_bytes())
        value["selection"]["reason"]="PRESERVE_ORIGINAL_CHAMPION";write(file,value)
        with self.assertRaisesRegex(ValueError,"Premature"):
            E.export(campaign,self.root/"output",PROJECT)
    def test_atomic_pointer_hash_binding_required(self):
        campaign=make_fixture(self.root/"private_fixture")
        file=campaign/"campaign_status.json";value=json.loads(file.read_bytes());value["promoted"]=True
        value["current_champion"]="M1";value["promotion_requires_matching_atomic_pointer"]=True;write(file,value)
        # The unchanged champion pointer must fail before any promotion claim.
        with self.assertRaisesRegex(ValueError,"pointer mismatch"):
            E.export(campaign,self.root/"output",PROJECT)
    def test_verified_promotion_then_stale_transaction_hash_rejected(self):
        campaign,out,_=self.export("promotion")
        self.assertTrue(json.loads((out/"SUMMARY.json").read_bytes())["promoted"])
        file=campaign/"CURRENT_CHAMPION.json";value=json.loads(file.read_bytes());value["comparison_sha256"]="0"*64;write(file,value)
        with self.assertRaisesRegex(ValueError,"transaction incomplete"):
            E.export(campaign,self.root/"rejected",PROJECT)
    def test_equal_metric_later_epoch_cannot_replace_frozen_best(self):
        campaign=make_fixture(self.root/"private_fixture")
        file=campaign/"M1-s17/evaluation.json";value=json.loads(file.read_bytes())
        value["selected_epoch"]=2;write(file,value)
        with self.assertRaisesRegex(ValueError,"Final checkpoint/stop trace"):
            E.export(campaign,self.root/"output",PROJECT)
        self.assertFalse((self.root/"output").exists())
    def test_completed_fit_cannot_end_before_stop_or_epoch_cap(self):
        campaign=make_fixture(self.root/"private_fixture")
        folder=campaign/"M1-s17"
        lines=(folder/"epoch_events.jsonl").read_text().splitlines()[:2]
        (folder/"epoch_events.jsonl").write_text("\n".join(lines)+"\n",encoding="utf8")
        file=folder/"evaluation.json";value=json.loads(file.read_bytes());value["evaluated_epochs"]=2;write(file,value)
        with self.assertRaisesRegex(ValueError,"Final checkpoint/stop trace"):
            E.export(campaign,self.root/"output",PROJECT)
        self.assertFalse((self.root/"output").exists())
    def test_model_inference_cost_is_bound_to_completed_fit_records(self):
        campaign=make_fixture(self.root/"private_fixture")
        file=campaign/"comparison.json";value=json.loads(file.read_bytes())
        next(c for c in value["candidates"] if c["id"]=="M1")["inference_cost"]=3.
        for item in [value["baseline"],*value["candidates"]]:item["per_seed"]={int(k):v for k,v in item["per_seed"].items()}
        value["selection"]=S.choose_champion(value["baseline"],value["candidates"],comparison_complete=True)
        value["robust_ranking"]=S.robust_ranking(value["baseline"],value["candidates"])
        write(file,value)
        with self.assertRaisesRegex(ValueError,"Model inference cost"):
            E.export(campaign,self.root/"output",PROJECT)
    def test_null_pearson_reason_and_nonfinite_metrics_rejected(self):
        with self.assertRaisesRegex(ValueError,"reason"):
            E.clean_score(dict(Accuracy=.5,macro_F1=.5,MAE=.5,Pearson=None,Pearson_reason=None))
        with self.assertRaisesRegex(ValueError,"finite"):
            E.score(dict(macro_F1=float("nan"),MAE=.5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
