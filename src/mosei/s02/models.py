"""S02 fixed residual-attention candidates and bounded output combinations.

No data readers, fitting loops, optimizer steps, checkpoint writes or authority.
All predictor inputs use the existing continuous-feature/support/available API.
"""
from __future__ import annotations

import math
import torch
from torch import nn
from torch.nn import functional as F

from mosei.s01.contracts import DIMS, MODS, SEEDS, require, stream_seed, validate_inputs

RECIPES = ("M1", "M2", "M3", "M4")
BETAS = (-.4, -.2, 0., .2, .4)
VARIANTS = ("W0", "W1", "W2")
ARCHITECTURE = dict(projection=64, attention_hidden=32, attention_output_bias=False,
                    gate_input=198, gate_hidden=32, gate_output=2,
                    residual_dimension=64, residual_bias=False,
                    residual_initialization="ALL_ZERO", head_input=64,
                    empty_modality="ZERO_POOL", empty_all="TRAIN_PRIOR_MEDIAN")


def safe_masked_softmax(scores, active):
    require(scores.ndim == 2 and active.shape == scores.shape and active.dtype == torch.bool,
            "Masked softmax shape/type")
    require(scores.is_floating_point() and scores.device == active.device,
            "Masked softmax dtype/device")
    require(bool(torch.isfinite(scores[active]).all()), "Nonfinite active attention score")
    any_active = active.any(1, keepdim=True)
    logits = scores.masked_fill(~active, float("-inf"))
    # The all-empty branch explicitly avoids softmax([-inf,...,-inf]).
    logits = torch.where(any_active, logits, torch.zeros_like(logits))
    return logits.softmax(1).masked_fill(~active, 0)


class AttentionPool(nn.Module):
    def __init__(self):
        super().__init__()
        self.hidden = nn.Linear(64, 32)
        self.score = nn.Linear(32, 1, bias=False)

    def forward(self, representations, active):
        require(representations.ndim == 3 and representations.shape[-1] == 64 and
                active.shape == representations.shape[:2], "Attention representation shape")
        require(bool(torch.isfinite(representations[active]).all()), "Nonfinite active representation")
        safe = representations.masked_fill(~active[..., None], 0)
        scores = self.score(self.hidden(safe).tanh()).squeeze(-1)
        weights = safe_masked_softmax(scores, active)
        return (safe * weights[..., None]).sum(1), weights


class ResidualAttentionModel(nn.Module):
    """Identical architecture/init across M1..M4; recipe changes live in training."""
    def __init__(self, recipe="M1", seed=17, *, prior=(1/3, 1/3, 1/3), median=0.):
        super().__init__()
        require(recipe in RECIPES and seed in SEEDS, "Fixed S02 recipe/seed required")
        self.architecture = self.recipe = recipe
        self.seed = seed
        p = torch.tensor(prior, dtype=torch.float32)
        require(p.shape == (3,) and bool(torch.isfinite(p).all()) and bool((p >= 0).all())
                and abs(float(p.sum()) - 1) < 1e-6, "Finite train class prior required")
        require(type(median) in (int, float) and math.isfinite(median) and -3 <= median <= 3,
                "Finite train median required")
        self.register_buffer("prior", p)
        self.register_buffer("median", torch.tensor(float(median), dtype=torch.float32))
        self.projections = nn.ModuleDict({m: nn.Linear(DIMS[m], 64) for m in MODS})
        self.pools = nn.ModuleDict({m: AttentionPool() for m in MODS})
        self.gate = nn.Sequential(nn.Linear(198, 32), nn.Tanh(), nn.Linear(32, 2))
        self.residuals = nn.ModuleDict({m: nn.Linear(64, 64, bias=False) for m in MODS[1:]})
        self.classifier, self.regressor = nn.Linear(64, 3), nn.Linear(64, 1)
        for name, module in self.named_modules():
            if isinstance(module, nn.Linear):
                with torch.random.fork_rng(devices=[]):
                    torch.manual_seed(stream_seed(seed, "s02:" + name))
                    module.reset_parameters()
        for module in self.residuals.values():
            nn.init.zeros_(module.weight)

    def forward(self, inputs):
        x, support, available = validate_inputs(inputs)
        pooled, attentions = [], {}
        for modality in MODS:
            active = available[modality]
            safe = x[modality].masked_fill(~active[..., None], 0)
            projected = F.gelu(self.projections[modality](safe))
            h, attentions[modality] = self.pools[modality](projected, active)
            pooled.append(h)
        visible = torch.stack(pooled, 1)
        b = torch.stack([available[m].any(1) for m in MODS], 1)
        rho = torch.stack([available[m].sum(1) for m in MODS], 1).to(visible.dtype)
        rho = rho / support.sum(1, keepdim=True)
        # Only current A-derived availability enters the gate; no original O/C.
        gate_input = torch.cat((visible.flatten(1), b.to(visible.dtype), rho), 1)
        gates = self.gate(gate_input).sigmoid()
        fused = visible[:, 0]
        for index, modality in enumerate(MODS[1:]):
            residual = self.residuals[modality](visible[:, index + 1])
            fused = fused + b[:, index + 1, None] * gates[:, index, None] * residual
        logits = self.classifier(fused)
        values = 3 * self.regressor(fused).squeeze(-1).tanh()
        empty = ~b.any(1)
        logits = torch.where(empty[:, None], self.prior.clamp_min(1e-30).log()[None], logits)
        values = torch.where(empty, self.median, values)
        require(bool(torch.isfinite(logits).all() & torch.isfinite(values).all()), "Nonfinite S02 output")
        return dict(logits=logits, regression=values,
                    diagnostics=dict(attention=attentions, residual_gates=gates, b=b, rho=rho))


def class_weights_train(classes, *, split):
    """sqrt(N/(3*n_c)), clipped before train-sample-weighted normalization."""
    require(split == "train", "Class weights fit on TRAIN only")
    require(classes.ndim == 1 and classes.numel() > 0 and classes.dtype == torch.long and
            bool(((classes >= 0) & (classes <= 2)).all()), "Strict three-class targets required")
    counts = torch.bincount(classes.detach().cpu(), minlength=3).double()
    n = counts.sum()
    raw = torch.where(counts > 0, (n / (3 * counts.clamp_min(1))).sqrt(), torch.full_like(counts, 2.))
    raw = raw.clamp(.5, 2.)
    weights = raw / ((raw * counts).sum() / n)
    require(bool(torch.isfinite(weights).all()), "Nonfinite class weights")
    return weights.float().to(classes.device)


def supervised_loss(output, classes, values, *, class_weights=None):
    logits, prediction = output["logits"], output["regression"]
    require(logits.shape == (len(classes), 3) and prediction.shape == values.shape == classes.shape
            and classes.ndim == 1 and classes.numel() > 0 and classes.dtype == torch.long,
            "Supervision shape/type")
    require(bool(torch.isfinite(logits).all() & torch.isfinite(prediction).all() & torch.isfinite(values).all())
            and bool((prediction.abs() <= 3).all()) and bool((values.abs() <= 3).all()), "Finite bounded supervision required")
    expected = torch.where(values < 0, 0, torch.where(values == 0, 1, 2))
    require(torch.equal(classes, expected), "Strict y==0 Neutral target mapping required")
    losses = F.cross_entropy(logits, classes, reduction="none")
    if class_weights is not None:
        require(class_weights.shape == (3,) and bool(torch.isfinite(class_weights).all())
                and bool((class_weights > 0).all()), "Finite fixed train class weights required")
        # Global train normalization already gives sample-weighted mean one.
        # Do not introduce a batch-dependent weight-sum denominator.
        losses = losses * class_weights.to(logits)[classes]
    result = losses.mean() + (prediction - values).abs().mean() / 3
    require(bool(torch.isfinite(result)), "Nonfinite supervised loss")
    return result


def distillation_loss(student_logits, teacher_logits, *, split, tau=2., weight=.1):
    """Fixed train-only teacher-to-current-student-view KL, with stop-gradient."""
    require(split == "train", "Teacher soft targets may be used on TRAIN only")
    require(tau == 2. and weight == .1, "Fixed S02 KD tau/weight required")
    require(student_logits.ndim == 2 and student_logits.shape[1] == 3 and
            student_logits.shape == teacher_logits.shape and student_logits.shape[0] > 0,
            "KD shape")
    require(student_logits.device == teacher_logits.device and
            bool(torch.isfinite(student_logits).all() & torch.isfinite(teacher_logits).all()), "Finite same-device KD logits required")
    target = F.softmax(teacher_logits.detach() / tau, dim=1)
    result = weight * tau**2 * F.kl_div(F.log_softmax(student_logits / tau, dim=1), target, reduction="batchmean")
    require(bool(torch.isfinite(result)), "Nonfinite KD loss")
    return result


def _check_output(value):
    logits, regression = value["logits"], value["regression"]
    require(logits.ndim == 2 and logits.shape[1] == 3 and regression.shape == (len(logits),)
            and len(logits) > 0 and logits.device == regression.device,
            "Component output shape/device")
    require(bool(torch.isfinite(logits).all() & torch.isfinite(regression).all())
            and bool((regression.abs() <= 3).all()), "Finite component outputs required")
    return logits.detach(), regression.detach()


def combine_outputs(cat_output, text_output, *, variant, beta=0.):
    require(variant in VARIANTS and type(beta) in (int, float) and beta in BETAS,
            "Only fixed W0/W1/W2 and five Neutral biases allowed")
    cat_logits, cat_value = _check_output(cat_output)
    text_logits, text_value = _check_output(text_output)
    require(cat_logits.shape == text_logits.shape and cat_logits.device == text_logits.device,
            "Paired expert population/device mismatch")
    if variant == "W2":
        logits = ((cat_logits.softmax(1) + text_logits.softmax(1)) * .5).clamp_min(1e-30).log()
        values = (cat_value + text_value) * .5
    else:
        logits, values = cat_logits, cat_value if variant == "W0" else text_value
    if beta != 0:
        logits = logits.clone()
        logits[:, 1] += beta
    return dict(logits=logits, regression=values, diagnostics=dict(variant=variant, beta_N=float(beta)))


def postprocessing_candidates():
    tags = ("m04", "m02", "zero", "p02", "p04")
    return [dict(id=variant + "-bN-" + tag, variant=variant, beta=beta)
            for variant in VARIANTS for beta, tag in zip(BETAS, tags)]


def sign_disagreement(output):
    logits, values = _check_output(output)
    regression_class = torch.where(values < 0, 0, torch.where(values == 0, 1, 2))
    count = int((logits.argmax(1) != regression_class).sum())
    return dict(disagreement_count=count, total_count=len(values), fraction=count / len(values))
