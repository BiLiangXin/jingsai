"""Data-free CPU forward/autograd checks; no optimizer step or model fitting."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
import torch
from torch.nn import functional as F
from mosei.s01.contracts import DIMS, MODS, synthetic_batch, configure_runtime

from mosei.s02 import models as M
from mosei.s02 import selection as S
configure_runtime()


def candidate(cid="BASE", adjustments=None, seeds=(17, 29, 43), cost=1., parameters=10):
    rows = {}
    for seed in seeds:
        row = dict(status="COMPLETED", clean=dict(Accuracy=.6, macro_F1=.55, MAE=.7, Pearson=.5, Pearson_reason=None),
                   attempted96=dict(macro_F1=.5, MAE=.8))
        for scope, key, value in (adjustments or {}).get(seed, []):
            row[scope][key] = value
        rows[seed] = row
    return S.summarize_candidate(cid, rows, parameters=parameters, inference_cost=cost)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.batch = synthetic_batch(3, seed=901, dense=True)
        self.inputs = self.batch.inputs()

    def test_fixed_shapes_parameters_and_shared_recipe_initialization(self):
        models = [M.ResidualAttentionModel(recipe) for recipe in M.RECIPES]
        self.assertEqual(sum(p.numel() for p in models[0].parameters()), 77542)
        for model in models[1:]:
            for name, tensor in models[0].state_dict().items():
                self.assertTrue(torch.equal(tensor, model.state_dict()[name]))
        output = models[0](self.inputs)
        self.assertEqual(output["logits"].shape, (3, 3))
        self.assertTrue(bool((output["regression"].abs() <= 3).all()))
        self.assertEqual(len(M.RECIPES) * len(M.SEEDS), 12)

    def test_attention_all_empty_and_inactive_nan_gradient(self):
        scores = torch.tensor([[float("nan"), float("nan")], [1., float("nan")]], requires_grad=True)
        active = torch.tensor([[False, False], [True, False]])
        weights = M.safe_masked_softmax(scores, active)
        self.assertTrue(torch.equal(weights, torch.tensor([[0., 0.], [1., 0.]])))
        weights.sum().backward()
        self.assertTrue(bool(torch.isfinite(scores.grad).all()))
        with self.assertRaisesRegex(ValueError, "active attention"):
            M.safe_masked_softmax(scores, torch.ones_like(active))

    def test_empty_model_train_prior_median_and_inactive_nan(self):
        available = {m: torch.zeros_like(self.batch.support) for m in MODS}
        inputs = dict(features={m: torch.full_like(self.batch.features[m], float("nan")) for m in MODS},
                      support=self.batch.support, available=available)
        model = M.ResidualAttentionModel(prior=(.2, .3, .5), median=-.25)
        result = model(inputs)
        self.assertTrue(torch.equal(result["regression"], torch.full((3,), -.25)))
        self.assertTrue(torch.allclose(result["logits"].softmax(1), torch.tensor([[.2, .3, .5]]).expand(3, -1)))
        for weights in result["diagnostics"]["attention"].values():
            self.assertEqual(int(torch.count_nonzero(weights)), 0)
        (result["logits"].sum() + result["regression"].sum()).backward()
        self.assertTrue(all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters()))

    def test_active_nan_and_extra_predictor_information_rejected(self):
        bad = copy.deepcopy(self.inputs)
        bad["features"]["text"][0, 0, 0] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            M.ResidualAttentionModel()(bad)
        with self.assertRaisesRegex(ValueError, "allowlist"):
            M.ResidualAttentionModel()({**self.inputs, "labels": self.batch.classes})

    def test_zero_residual_init_preserves_text_backbone_and_av_path_can_operate(self):
        model = M.ResidualAttentionModel()
        first = model(self.inputs)["logits"]
        changed = copy.deepcopy(self.inputs)
        changed["features"]["audio"] *= 12
        changed["features"]["vision"] -= 9
        self.assertTrue(torch.equal(first, model(changed)["logits"]))
        no_text = copy.deepcopy(self.inputs)
        no_text["available"]["text"][:] = False
        no_text["features"]["text"][:] = float("nan")
        before = model(no_text)["logits"]
        with torch.no_grad():
            model.residuals["audio"].weight.copy_(torch.eye(64))
        after = model(no_text)["logits"]
        self.assertFalse(torch.equal(before, after))
        self.assertTrue(bool(torch.isfinite(after).all()))

    def test_class_weight_formula_train_only_and_missing_class(self):
        classes = torch.tensor([0] * 9 + [1] * 2 + [2], dtype=torch.long)
        weights = M.class_weights_train(classes, split="train")
        raw = torch.sqrt(torch.tensor(12.) / (3 * torch.tensor([9., 2., 1.]))).clamp(.5, 2.)
        expected = raw / ((raw * torch.tensor([9., 2., 1.])).sum() / 12)
        self.assertTrue(torch.allclose(weights, expected))
        self.assertAlmostEqual(float(weights[classes].mean()), 1., places=6)
        missing = M.class_weights_train(torch.tensor([0, 0, 2]), split="train")
        self.assertTrue(bool(torch.isfinite(missing).all()))
        for split in ("valid", "test"):
            with self.assertRaisesRegex(ValueError, "TRAIN"):
                M.class_weights_train(classes, split=split)

    def test_weighted_ce_uses_train_normalized_sample_mean(self):
        output = dict(logits=torch.tensor([[1., 2., 3.], [3., 1., 0.], [0., 1., 0.]]), regression=torch.tensor([-.5, .2, .3]))
        classes, y = torch.tensor([0, 1, 2]), torch.tensor([-1., 0., 1.])
        weights = torch.tensor([.5, 1., 2.])
        expected = (F.cross_entropy(output["logits"], classes, reduction="none") * weights[classes]).mean() + (output["regression"] - y).abs().mean() / 3
        self.assertTrue(torch.equal(M.supervised_loss(output, classes, y, class_weights=weights), expected))
        with self.assertRaisesRegex(ValueError, "Neutral"):
            M.supervised_loss(output, torch.tensor([0, 1, 1]), y)

    def test_kd_teacher_stop_gradient_and_fixed_train_scope(self):
        student = torch.tensor([[2., 1., -1.], [0., 1., 3.]], requires_grad=True)
        teacher = torch.tensor([[1., 2., 3.], [2., 1., 0.]], requires_grad=True)
        loss = M.distillation_loss(student, teacher, split="train")
        expected = .1 * 4 * F.kl_div(F.log_softmax(student/2, dim=1), F.softmax(teacher.detach()/2, dim=1), reduction="batchmean")
        self.assertTrue(torch.equal(loss, expected))
        loss.backward()
        self.assertIsNone(teacher.grad)
        self.assertTrue(bool(torch.isfinite(student.grad).all()))
        with self.assertRaisesRegex(ValueError, "TRAIN"):
            M.distillation_loss(student, teacher, split="valid")
        with self.assertRaisesRegex(ValueError, "Fixed"):
            M.distillation_loss(student, teacher, split="train", weight=.2)

    def test_fixed_postprocess_grid_w0_w1_identity_and_w2(self):
        grid = M.postprocessing_candidates()
        self.assertEqual(len(grid), 15)
        self.assertEqual(len({c["id"] for c in grid}), 15)
        cat = dict(logits=torch.tensor([[.1, .2, .3], [2., 0., -1.]]), regression=torch.tensor([.2, -.3]))
        text = dict(logits=torch.tensor([[.3, .2, .1], [-1., 0., 2.]]), regression=torch.tensor([-.4, .1]))
        w0, w1 = (M.combine_outputs(cat, text, variant=v) for v in ("W0", "W1"))
        self.assertTrue(torch.equal(w0["logits"], cat["logits"]))
        self.assertTrue(torch.equal(w0["regression"], cat["regression"]))
        self.assertTrue(torch.equal(w1["logits"], cat["logits"]))
        self.assertTrue(torch.equal(w1["regression"], text["regression"]))
        w2 = M.combine_outputs(cat, text, variant="W2")
        self.assertTrue(torch.allclose(w2["logits"].softmax(1), .5*(cat["logits"].softmax(1)+text["logits"].softmax(1))))
        self.assertTrue(torch.equal(w2["regression"], (cat["regression"]+text["regression"])/2))
        biased = M.combine_outputs(cat, text, variant="W0", beta=.4)
        self.assertTrue(torch.equal(biased["logits"][:, [0, 2]], cat["logits"][:, [0, 2]]))
        self.assertTrue(torch.equal(biased["regression"], cat["regression"]))
        with self.assertRaises(ValueError):
            M.combine_outputs(cat, text, variant="W0", beta=.1)

    def test_output_combiner_scope_and_sign_disagreement(self):
        output = dict(logits=torch.tensor([[2., 0., 0.], [0., 2., 0.], [0., 0., 2.]]),
                      regression=torch.tensor([-.1, .2, 0.]))
        result = M.sign_disagreement(output)
        self.assertEqual(result, dict(disagreement_count=2, total_count=3, fraction=2/3))
        bad = dict(logits=output["logits"], regression=torch.tensor([float("nan"), .1, .2]))
        with self.assertRaisesRegex(ValueError, "Finite"):
            M.combine_outputs(output, bad, variant="W1")
        with self.assertRaisesRegex(ValueError, "population/device"):
            M.combine_outputs(output, dict(logits=torch.zeros(2, 3), regression=torch.zeros(2)), variant="W2")


class SelectionTests(unittest.TestCase):
    def test_incomplete_seed_set_mean_is_null(self):
        value = candidate("PARTIAL", seeds=(17, 29))
        self.assertFalse(value["complete"])
        self.assertIsNone(value["means"])
        self.assertFalse(S.promotion_eligibility(candidate(), value)["eligible"])
        with self.assertRaisesRegex(ValueError, "integer seed"):
            S.summarize_candidate("INVALID", {17.0: {}}, parameters=1)

    def test_tradeoff_and_seed17_degradation_keep_champion(self):
        changes = {s: [("attempted96", "macro_F1", .6), ("clean", "MAE", .71)] for s in S.SEEDS}
        bad = candidate("TRADEOFF", changes)
        decision = S.choose_champion(candidate(), [bad], comparison_complete=True)
        self.assertEqual(decision["selected_id"], "BASE")
        changes = {17: [("clean", "macro_F1", .54)], 29: [("clean", "macro_F1", .6)], 43: [("clean", "macro_F1", .6)]}
        self.assertFalse(S.promotion_eligibility(candidate(), candidate("LUCKY_MEAN", changes))["eligible"])

    def test_strict_mean_and_seed17_improvement_proposes_restore_first(self):
        changes = {s: [("attempted96", "macro_F1", .6)] for s in S.SEEDS}
        value = candidate("BETTER", changes)
        decision = S.choose_champion(candidate(), [value], comparison_complete=True)
        self.assertTrue(decision["promotion_proposed"])
        self.assertEqual(decision["selected_id"], "BETTER")
        self.assertIn("RESTORE", decision["reason"])
        self.assertEqual(S.choose_champion(candidate(), [value], comparison_complete=False)["selected_id"], "BASE")

    def test_tolerance_is_not_a_gain_and_null_pearson_rejected(self):
        tiny = candidate("TINY", {s: [("clean", "macro_F1", .55+5e-9)] for s in S.SEEDS})
        self.assertFalse(S.promotion_eligibility(candidate(), tiny)["eligible"])
        unknown = candidate("UNKNOWN", {17: [("clean", "Pearson", None), ("clean", "Pearson_reason", "zero_prediction_variance"), ("attempted96", "macro_F1", .7)]})
        self.assertIsNone(unknown["means"]["clean"]["Pearson"])
        self.assertFalse(S.promotion_eligibility(candidate(), unknown)["eligible"])

    def test_deterministic_cost_id_ties_and_robust_guard(self):
        changes = {s: [("attempted96", "macro_F1", .6)] for s in S.SEEDS}
        expensive, cheap = candidate("A", changes, cost=2), candidate("B", changes, cost=1)
        self.assertEqual(S.choose_champion(candidate(), [expensive, cheap], comparison_complete=True)["selected_id"], "B")
        outside = candidate("OUTSIDE", {s: [("clean", "macro_F1", .5)] for s in S.SEEDS})
        self.assertNotIn("OUTSIDE", S.robust_ranking(candidate(), [outside, cheap]))
        self.assertEqual(S.robust_ranking(candidate(), [expensive, cheap]), ["B", "A"])

    def test_pareto_retains_tradeoff_and_rejects_nonfinite(self):
        higher_f = candidate("HIGHER_F", {s: [("clean", "macro_F1", .6), ("clean", "MAE", .8)] for s in S.SEEDS})
        self.assertEqual(S.clean_pareto([candidate(), higher_f])["pareto_ids"], ["BASE", "HIGHER_F"])
        with self.assertRaisesRegex(ValueError, "Invalid metric"):
            candidate("NAN", {17: [("clean", "Accuracy", float("nan"))]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
