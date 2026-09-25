"""S02 data-free execution regressions: synthetic CPU tensors and mocked authority.

No official data, saved weights, host claim ledger, Git/network command, or GPU
query is used. Authority fixtures never constitute permission for real data.
"""
from __future__ import annotations
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch

sys.dont_write_bytecode = True
_repo = Path(__file__).resolve().parents[1]
if not (_repo / "src/mosei/s02").is_dir():
    _repo = Path(__file__).resolve().parent.parent / "jingsai_official"
sys.path.insert(0, str(_repo / "src"))
import torch
from mosei.s01.contracts import MODS, digest, synthetic_batch
from mosei.s01.protocol import ValidationLibrary
from mosei.s01.models import R01Model
from mosei.s01.normalization import Normalizer
from mosei.s02 import authorization as A, common as C, evaluation as V, engine as E, execution as X
from mosei.s02.models import postprocessing_candidates


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf8")


class OutsideFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="s02_data_free_")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(torch.cuda, "is_available", return_value=False))
        self.stack.enter_context(patch.object(torch.cuda, "mem_get_info", side_effect=AssertionError("GPU query forbidden in these tests")))
        self.stack.enter_context(patch.object(A, "ACTIVE", None))

    def authority_fixture(self):
        self.repo, self.output, self.backup, self.claims = [self.home / name for name in ("repo", "new_output", "backup", "claims")]
        self.backup.mkdir()
        self.claims.mkdir()
        (self.backup / "payload.json").write_bytes(b'{"SYNTHETIC_FIXTURE":true}\n')
        self.config = dict(task_id=A.TASK, status="ACTIVE_AUTHORIZED", training_authorized=True,
            authorization_id="S02-EXEC-AUTH-01", execution_fit_budget=12, postprocess_budget=15, retry_training_budget=0,
            model_seeds=[17, 29, 43], recipes=["M1", "M2", "M3", "M4"], variants=["W0", "W1", "W2"],
            betas=[-.4, -.2, 0., .2, .4], resource_walltime_cap_hours=4, per_fit_walltime_cap_minutes=45,
            latest_compute_finish=C.CUTOFF, test_authorized=False, attachment3_4_authorized=False,
            q3_authorized=False, source_sha256=C.SOURCE_HASH, train_mask_root=2207, valid_mask_root=1103,
            nominal_conditions=96, views=144, device="cuda", campaign_id="S02-SYNTHETIC-AUTHORITY-FIXTURE",
            private_output_sha256=A.path_digest(self.output), backup_root_sha256=A.path_digest(self.backup),
            instruction_sha256="a" * 64)
        write(self.repo / "configs/s02_execution.json", self.config)
        write(self.repo / "configs/s01_execution.json", dict(training_authorized=False, authorization_status="CONSUMED"))
        write(self.repo / "docs/S02_EXEC_AUTH_01.json", dict(config_hash=digest(self.config), authorization_id="S02-EXEC-AUTH-01", instruction_sha256="a" * 64))
        self.contract = "| D-DATA-01 | FROZEN_FOR_BASELINE | SYNTHETIC CONTRACT FIXTURE |\n"
        (self.repo / "DECISIONS.md").write_text(self.contract, encoding="utf8")
        write(self.repo / "reports/s02_preparation/BACKUP_MANIFEST.json", dict(status="PASS", old_best_count=30, old_last_count=30,
            files=[dict(path="payload.json", size=(self.backup / "payload.json").stat().st_size, sha256=C.sha(self.backup / "payload.json"))]))
        write(self.repo / "reports/s02_preparation/RESTORE_RECEIPT.json", dict(status="PASS", scope="SYNTHETIC_FIXTURE_ONLY"))
        self.fake_git_overrides = {}
        def fake_git(*args):
            if args in self.fake_git_overrides:
                return self.fake_git_overrides[args]
            if args == ("branch", "--show-current"):
                return "codex/mosei-auto"
            if args == ("remote", "get-url", "origin"):
                return "https://github.com/BiLiangXin/jingsai.git"
            if args == ("status", "--porcelain"):
                return ""
            if args == ("rev-parse", "HEAD"):
                return "b" * 40
            if args == ("ls-remote", "origin", "refs/heads/codex/mosei-auto"):
                return "b" * 40 + "\trefs/heads/codex/mosei-auto"
            if args[0] == "diff":
                return ""
            if args == ("show", A.BASE + ":DECISIONS.md"):
                return self.contract
            raise AssertionError("Unexpected Git command in data-free test")
        self.stack.enter_context(patch.object(A, "ROOT", self.repo))
        self.stack.enter_context(patch.object(A, "claims_root", return_value=self.claims))
        self.stack.enter_context(patch.object(A, "git", side_effect=fake_git))
        self.stack.enter_context(patch.object(A, "verify_manifest", return_value="c" * 64))
        self.time = self.stack.enter_context(patch.object(A, "now", return_value=dt.datetime.fromisoformat("2026-09-25T08:00:00+08:00")))

    def preflight(self):
        return A.preflight(self.config, self.output, self.backup)


class S02AuthorityTests(OutsideFixture):
    def setUp(self):
        super().setUp()
        self.authority_fixture()

    def test_exact_12_fit_15_candidate_preflight(self):
        bound = self.preflight()
        self.assertEqual(bound["config_hash"], digest(self.config))
        candidates = postprocessing_candidates()
        self.assertEqual(len(candidates), 15)
        self.assertEqual(len({r["id"] for r in candidates}), 15)
        self.assertEqual({(r["variant"], r["beta"]) for r in candidates}, {(v, b) for v in self.config["variants"] for b in self.config["betas"]})
        self.assertFalse(self.output.exists())

    def test_scope_caps_and_closed_authority_reject_mutations(self):
        mutations = dict(execution_fit_budget=13, postprocess_budget=16, retry_training_budget=1,
            model_seeds=[17], recipes=["M1", "M2", "M3", "M4", "M5"], variants=["W0", "W1", "W2", "W3"],
            betas=[-.4, -.2, 0., .2, .4, .6], resource_walltime_cap_hours=5, per_fit_walltime_cap_minutes=46,
            test_authorized=True, attachment3_4_authorized=True, q3_authorized=True, training_authorized=False,
            status="CONSUMED", task_id="S01_FROZEN_BASELINE_EXECUTION", device="cpu", views=145,
            nominal_conditions=97, valid_mask_root=1104, train_mask_root=2208)
        for key, value in mutations.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                A.validate_config({**self.config, key: value})

    def test_s01_campaign_identifier_rejected(self):
        with self.assertRaisesRegex(ValueError, "Separate S02"):
            A.validate_config({**self.config, "campaign_id": "S01-SYNTHETIC-CONSUMED"})

    def test_deadline_and_incomplete_four_hour_window_rejected(self):
        for instant in ("2026-09-25T18:00:00+08:00", "2026-09-25T14:00:01+08:00"):
            self.time.return_value = dt.datetime.fromisoformat(instant)
            with self.subTest(instant=instant), self.assertRaises(ValueError):
                self.preflight()

    def test_existing_output_and_backup_nested_output_rejected(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "New outside"):
            self.preflight()
        nested = self.backup / "new"
        cfg = {**self.config, "private_output_sha256": A.path_digest(nested)}
        with self.assertRaisesRegex(ValueError, "New outside"):
            A.preflight(cfg, nested, self.backup)

    def test_opening_consumed_s01_is_not_s02_authority(self):
        for old in (dict(training_authorized=True, authorization_status="CONSUMED"), dict(training_authorized=False, authorization_status="ACTIVE")):
            write(self.repo / "configs/s01_execution.json", old)
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, "S01 must remain closed"):
                self.preflight()

    def test_wrong_branch_dirty_tree_and_remote_rejected(self):
        cases = [(('branch', '--show-current'), 'main'), (('status', '--porcelain'), ' M unrelated.txt'),
                 (('ls-remote', 'origin', 'refs/heads/codex/mosei-auto'), 'd' * 40 + '\trefs/heads/codex/mosei-auto')]
        for command, value in cases:
            self.fake_git_overrides = {command: value}
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.preflight()

    def test_changed_backup_bytes_block_preflight(self):
        (self.backup / "payload.json").write_bytes(b"changed synthetic backup bytes")
        with self.assertRaisesRegex(ValueError, "Backup mutated"):
            self.preflight()

    def test_failed_restore_or_manifest_blocks_preflight(self):
        write(self.repo / "reports/s02_preparation/RESTORE_RECEIPT.json", dict(status="FAIL"))
        with self.assertRaisesRegex(ValueError, "Restore required"):
            self.preflight()
        with patch.object(A, "verify_manifest", side_effect=ValueError("reviewed manifest changed")), self.assertRaisesRegex(ValueError, "manifest changed"):
            self.preflight()

    def test_claim_isolation_replay_and_active_scope(self):
        binding = self.preflight()
        A.claim(self.config, binding)
        for split, optimizer in (("train", False), ("train", True), ("valid", False)):
            A.require_active(self.config, split=split, optimizer=optimizer)
        for split, optimizer in (("test", False), ("attachment3", False), ("attachment4", False), ("valid", True)):
            with self.subTest(split=split, optimizer=optimizer), self.assertRaisesRegex(ValueError, "forbidden"):
                A.require_active(self.config, split=split, optimizer=optimizer)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.preflight()
        with self.assertRaisesRegex(ValueError, "Process already"):
            A.claim(self.config, binding)
        with patch.object(A, "ACTIVE", None), self.assertRaises(FileExistsError):
            A.claim(self.config, binding)
        other = {**self.config, "campaign_id": "S02-OTHER-SYNTHETIC-CAMPAIGN"}
        with self.assertRaisesRegex(ValueError, "claimed process"):
            A.require_active(other, split="train")

    def test_unclaimed_or_tampered_process_cannot_read_train(self):
        with self.assertRaisesRegex(ValueError, "claimed process"):
            A.require_active(self.config, split="train")
        binding = self.preflight()
        A.claim(self.config, binding)
        path = self.claims / (self.config["campaign_id"] + ".json")
        value = json.loads(path.read_bytes())
        value["pid"] = os.getpid() + 100
        write(path, value)
        with self.assertRaisesRegex(ValueError, "Claim changed"):
            A.require_active(self.config, split="valid")

    def test_source_open_is_after_active_authority(self):
        missing_source = self.home / "aligned_50.pkl"
        with patch.object(X.auth, "require_active", side_effect=ValueError("not authorized")), self.assertRaisesRegex(ValueError, "not authorized"):
            X.load_official(self.config, missing_source, lambda: None)
        self.assertFalse(missing_source.exists())


class S02ResourcesAndMaskTests(OutsideFixture):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(C, "now", return_value=dt.datetime.fromisoformat("2026-09-25T08:00:00+08:00")))
        self.clock = self.stack.enter_context(patch.object(C.time, "monotonic", return_value=100.))

    def test_no_larger_total_cap_or_changed_cutoff(self):
        for kwargs in (dict(hours=4.1), dict(hours=0), dict(cutoff="2026-09-26T18:00:00+08:00")):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                C.Budget(self.home, **kwargs)

    def test_per_fit_45_minute_and_total_four_hour_stops(self):
        budget = C.Budget(self.home)
        budget.start_fit()
        self.assertEqual(budget.fit_deadline, 2800.)
        self.clock.return_value = 2800.
        with self.assertRaisesRegex(C.ResourceStop, "Per-fit"):
            budget()
        budget.end_fit()
        budget()
        self.clock.return_value = 14500.
        with self.assertRaisesRegex(C.ResourceStop, "Campaign"):
            budget()

    def test_absolute_deadline_and_storage_stop(self):
        with patch.object(C, "now", return_value=dt.datetime.fromisoformat(C.CUTOFF)), self.assertRaises(C.ResourceStop):
            C.Budget(self.home)
        budget = C.Budget(self.home)
        huge = types.SimpleNamespace(is_file=lambda: True, stat=lambda: types.SimpleNamespace(st_size=5 * 2**30 + 1))
        budget.output = types.SimpleNamespace(rglob=lambda _: [huge])
        self.clock.return_value = 106.
        with self.assertRaisesRegex(C.ResourceStop, "Storage"):
            budget()

    def test_corruption_determinism_and_ordinal_order_invariance(self):
        batch = synthetic_batch(4, 4711)
        left, lc = E.train_available(batch, 17, 2)
        right, rc = E.train_available(batch, 17, 2)
        self.assertEqual(lc, rc)
        for m in MODS:
            self.assertTrue(torch.equal(left[m], right[m]))
            self.assertFalse(bool((left[m] & ~batch.observed[m]).any()))
        order = [3, 1, 0, 2]
        permuted, _ = E.train_available(batch.take(order), 17, 2)
        for m in MODS:
            self.assertTrue(torch.equal(permuted[m], left[m][order]))

    def test_one_in_four_corruption_draw_and_clean_once_no_resampling(self):
        batch = synthetic_batch(4, 11)
        batch.support[:] = False
        batch.support[:, 0] = True
        batch.observed["text"] = batch.support.clone()
        batch.observed["audio"][:] = False
        batch.observed["vision"][:] = False
        batch.validate()
        def choice(count, *parts):
            return parts[-2] % 4 if parts[-1] == "clean_or_corrupt" else 0
        original = E.reference.generate
        with patch.object(E.reference, "choose", side_effect=choice), patch.object(E.reference, "generate", wraps=original) as generate:
            available, counts = E.train_available(batch, 17, 0)
        self.assertEqual(counts, dict(rows=4, clean_requested=3, eligible=0, ineligible=1))
        self.assertEqual(generate.call_count, 1)
        for m in MODS:
            self.assertTrue(torch.equal(available[m], batch.observed[m]))


class S02CacheTests(OutsideFixture):
    def setUp(self):
        super().setUp()
        self.batch = synthetic_batch(2, 78)
        self.library = ValidationLibrary(self.batch)
        output = dict(logits=torch.zeros(2, 3), regression=torch.zeros(2))
        self.cache = dict(clean=copy.deepcopy(output), population=digest(self.batch.ordinals), mask_fingerprint=self.library.mask_fingerprint,
            views={cid: [dict(output=copy.deepcopy(output), fingerprint=row["fingerprint"], replicate=row["replicate"]) for row in rows]
                   for cid, rows in self.library.views.items()})

    def test_complete96_144_cache_accepted(self):
        self.assertEqual(len(self.cache["views"]), 96)
        self.assertEqual(sum(map(len, self.cache["views"].values())), 144)
        V.validate_cache(self.cache, self.batch, self.library)

    def test_changed_order_population_or_mask_rejected(self):
        for key in ("population", "mask_fingerprint"):
            value = {**self.cache, key: "0" * 64}
            with self.subTest(key=key), self.assertRaises(ValueError):
                V.validate_cache(value, self.batch, self.library)
        with self.assertRaises(ValueError):
            V.validate_cache(self.cache, self.batch.take([1, 0]), self.library)
        changed = copy.deepcopy(self.batch)
        changed.observed["audio"][0, 0] = ~changed.observed["audio"][0, 0]
        with self.assertRaisesRegex(ValueError, "population/masks"):
            V.validate_cache(self.cache, changed, self.library)

    def test_wrong_condition_replicate_view_or_length_rejected(self):
        first = next(iter(self.cache["views"]))
        for kind in ("condition", "replicate_count", "replicate_id", "fingerprint", "length"):
            cache = copy.deepcopy(self.cache)
            if kind == "condition":
                del cache["views"][first]
            elif kind == "replicate_count":
                cache["views"][first].append(copy.deepcopy(cache["views"][first][0]))
            elif kind == "replicate_id":
                cache["views"][first][0]["replicate"] = 99
            elif kind == "fingerprint":
                cache["views"][first][0]["fingerprint"] = "0" * 64
            else:
                cache["views"][first][0]["output"]["regression"] = torch.zeros(1)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                V.validate_cache(cache, self.batch, self.library)

    def test_full_winner_restore_rejects_one_changed_value_or_mask(self):
        X.exact_output_values(self.cache, copy.deepcopy(self.cache))
        for part in ("clean", "view"):
            changed = copy.deepcopy(self.cache)
            output = changed["clean"] if part == "clean" else next(iter(changed["views"].values()))[0]["output"]
            output["regression"][0] = .1
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, "predictions differ"):
                X.exact_output_values(self.cache, changed)
        changed = copy.deepcopy(self.cache)
        next(iter(changed["views"].values()))[0]["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "masks mismatch"):
            X.exact_output_values(self.cache, changed)


class S02FailurePersistenceTests(OutsideFixture):
    def run_failure(self, *, resource=False):
        output = self.home / "campaign"
        cfg = dict(campaign_id="S02-SYNTHETIC-FAILURE-ONLY")
        binding = dict(campaign_id=cfg["campaign_id"], commit="b" * 40, config_hash=digest(cfg))
        budget = lambda: None
        with patch.object(X.auth, "preflight", return_value=binding), patch.object(X.auth, "claim"), \
             patch.object(X, "Budget", side_effect=C.ResourceStop("synthetic startup cap") if resource else None, return_value=budget), \
             patch.object(X, "load_official", side_effect=OSError("synthetic source failure")) as load, redirect_stdout(io.StringIO()):
            status = X.execute(cfg, self.home / "DO_NOT_READ", output, self.home / "NO_BACKUP_READ")
        if resource:
            load.assert_not_called()
        return status, output

    def test_budget_constructor_stop_is_durable_and_keeps_old_pointer(self):
        status, output = self.run_failure(resource=True)
        record = json.loads((output / "campaign_status.json").read_bytes())
        pointer = json.loads((output / "CURRENT_CHAMPION.json").read_bytes())
        self.assertEqual(status, "PARTIAL_RESOURCE_STOP")
        self.assertEqual(record["phase"], "RESOURCE_PREFLIGHT")
        self.assertEqual(record["fit_completed"], 0)
        self.assertFalse(record["promoted"])
        self.assertEqual(record["authorization_status"], "CONSUMED")
        self.assertEqual(pointer["current_champion"], "S01-B-CAT-zscore")
        events = [json.loads(x) for x in (output / "events.jsonl").read_text().splitlines()]
        self.assertFalse(any(x.get("status") == "COMPLETED" for x in events))

    def test_source_exception_is_durable_and_cannot_mark_completed(self):
        status, output = self.run_failure()
        record = json.loads((output / "campaign_status.json").read_bytes())
        pointer = json.loads((output / "CURRENT_CHAMPION.json").read_bytes())
        self.assertEqual(status, "BLOCKED")
        self.assertEqual(record["fit_completed"], record["postprocess_completed"])
        self.assertEqual(record["fit_completed"], 0)
        self.assertFalse(record["promoted"])
        self.assertEqual(pointer["current_champion"], "S01-B-CAT-zscore")
        self.assertIn("synthetic source failure", record["error"])

    def test_existing_trial_rejected_before_any_gpu_model_construction(self):
        folder = self.home / "existing_trial"
        folder.mkdir()
        with patch.object(E, "require_active"), patch.object(E, "ResidualAttentionModel", side_effect=AssertionError("Must reject before GPU/model")), self.assertRaisesRegex(ValueError, "New fixed trial"):
            E.fit(dict(recipes=["M1"], model_seeds=[17, 29, 43]), "M1", 17, None, None, None, None, None, folder, {}, None)


class S02ActualComponentPipelineTests(OutsideFixture):
    """Run actual CPU normalization/inference/combination, with no saved weights."""

    def setUp(self):
        super().setUp()
        old_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, old_threads)
        train = synthetic_batch(2, 2301, dense=True)
        for m in MODS:
            train.features[m] = 7 * train.features[m] + 5
        self.cat_norm = Normalizer("zscore").fit([train], split="train")
        self.text_norm = Normalizer("identity").fit([train], split="train")
        self.batch = synthetic_batch(2, 2701, dense=True)
        self.batch.support[:, 12:] = False
        self.batch.observed = {m: self.batch.support.clone() for m in MODS}
        self.batch.observed["audio"][:, 5] = False
        self.batch.features["audio"][:, 5] = 0
        self.batch.validate()
        self.library = ValidationLibrary(self.batch)
        # Real generator + real population validator, one paired view for speed.
        # The separate full-cache tests cover the complete 96/144 population.
        chosen = next((cid, row) for cid, rows in self.library.views.items() for row in rows
                      if all(row["eligible"])
                      and bool((self.batch.observed["text"] & ~row["available"]["text"]).any())
                      and bool((self.batch.observed["audio"] & ~row["available"]["audio"]).any()))
        self.cid, self.row = chosen
        self.library.views = {self.cid: [self.row]}
        self.cat, self.text = R01Model("B-CAT", 17).eval(), R01Model("B-T", 17).eval()

    def collect_pair(self, batch):
        return (V.collect_views(self.cat, self.cat_norm.transform(batch), self.library, lambda: None),
                V.collect_views(self.text, self.text_norm.transform(batch), self.library, lambda: None))

    def test_actual_component_views_share_masks_and_keep_own_normalizers(self):
        calls = {"cat": [], "text": []}
        def hook(name):
            def capture(model, args):
                value = args[0]
                calls[name].append({"keys": set(value),
                    "features": {m: value["features"][m].clone() for m in MODS},
                    "available": {m: value["available"][m].clone() for m in MODS},
                    "support": value["support"].clone()})
            return capture
        hooks = [self.cat.register_forward_pre_hook(hook("cat")),
                 self.text.register_forward_pre_hook(hook("text"))]
        try:
            cat, text = self.collect_pair(self.batch)
        finally:
            for handle in hooks:
                handle.remove()
        self.assertEqual(len(calls["cat"]), 2)
        self.assertEqual(len(calls["text"]), 2)
        cat_input = self.cat_norm.transform(self.batch)
        for index, (left, right) in enumerate(zip(calls["cat"], calls["text"])):
            self.assertEqual(left["keys"], {"features", "support", "available"})
            self.assertEqual(right["keys"], left["keys"])
            self.assertTrue(torch.equal(left["support"], right["support"]))
            for m in MODS:
                expected = self.batch.observed[m] if index == 0 else self.row["available"][m]
                self.assertTrue(torch.equal(left["available"][m], expected))
                self.assertTrue(torch.equal(right["available"][m], expected))
                self.assertTrue(torch.equal(left["features"][m], cat_input.features[m]))
                self.assertTrue(torch.equal(right["features"][m], self.batch.features[m]))
        # A swapped normalizer must change actual expert predictions in this
        # deliberately nontrivial fixture, so the isolation check is sensitive.
        wrong_cat = V.collect_views(self.cat, self.text_norm.transform(self.batch), self.library, lambda: None)
        wrong_text = V.collect_views(self.text, self.cat_norm.transform(self.batch), self.library, lambda: None)
        self.assertFalse(torch.equal(cat["clean"]["logits"], wrong_cat["clean"]["logits"]))
        self.assertFalse(torch.equal(text["clean"]["regression"], wrong_text["clean"]["regression"]))

    def test_actual_pipeline_w1_heads_are_exact_expert_outputs(self):
        cat, text = self.collect_pair(self.batch)
        combined = V.combined_cache(cat, text, dict(variant="W1", beta=0.), self.batch, self.library)
        pairs = [(combined["clean"], cat["clean"], text["clean"]),
                 (combined["views"][self.cid][0]["output"], cat["views"][self.cid][0]["output"],
                  text["views"][self.cid][0]["output"])]
        for output, cat_output, text_output in pairs:
            self.assertTrue(torch.equal(output["logits"], cat_output["logits"]))
            self.assertTrue(torch.equal(output["regression"], text_output["regression"]))
        self.assertEqual(combined["views"][self.cid][0]["fingerprint"], self.row["fingerprint"])

    def test_actual_hidden_feature_changes_do_not_reach_either_expert(self):
        original_cat, original_text = self.collect_pair(self.batch)
        changed = copy.deepcopy(self.batch)
        for m in MODS:
            artificial_hidden = changed.observed[m] & ~self.row["available"][m]
            changed.features[m][artificial_hidden] = 100000.
            # NaN is allowed only outside original observation, never as a way
            # to skip a finite-original-input check in normalization.
            changed.features[m][~changed.observed[m]] = float("nan")
        changed.validate()
        cat, text = self.collect_pair(changed)
        for old, new in ((original_cat, cat), (original_text, text)):
            for field in ("logits", "regression"):
                self.assertTrue(torch.equal(old["views"][self.cid][0]["output"][field],
                                            new["views"][self.cid][0]["output"][field]))
        # Reopening a hidden value must be observable in the clean predictions.
        self.assertFalse(torch.equal(original_cat["clean"]["logits"], cat["clean"]["logits"]))
        for m in MODS:
            self.assertTrue(torch.equal(changed.observed[m], self.batch.observed[m]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
