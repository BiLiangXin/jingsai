"""R01 frozen pooling/partial-convolution/fusion models, no Q3 module."""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from .contracts import ARCHITECTURES, DIMS, MODS, SEEDS, require, stream_seed, validate_inputs


def safe_mean(x, active):
    require(bool(torch.isfinite(x[active]).all()), "Nonfinite active representation")
    return x.masked_fill(~active[..., None], 0).sum(1) / active.sum(1).clamp_min(1)[:, None]


class R01Model(nn.Module):
    def __init__(self, architecture, seed=17, *, prior=(1/3, 1/3, 1/3), median=0.):
        super().__init__()
        require(architecture in ARCHITECTURES and seed in SEEDS, "Only frozen architecture/seed allowed")
        self.architecture, self.seed = architecture, seed
        p = torch.tensor(prior, dtype=torch.float32)
        require(p.shape == (3,) and bool(torch.isfinite(p).all()) and bool((p >= 0).all())
                and abs(float(p.sum()) - 1) < 1e-6, "Finite train prior required")
        require(-3 <= median <= 3, "Finite train median required")
        self.register_buffer("prior", p)
        self.register_buffer("median", torch.tensor(float(median)))
        self.temporal = architecture in ("R1", "R2", "R1-CAP")
        if architecture.startswith("B-"):
            self.used = MODS if architecture == "B-CAT" else (MODS[("B-T", "B-A", "B-V").index(architecture)],)
            self.projection = nn.Linear(sum(DIMS[m] for m in self.used), 64)
            head_dim = 64
        else:
            self.projections = nn.ModuleDict({m: nn.Linear(DIMS[m], 64) for m in MODS})
            if self.temporal:
                self.convolutions = nn.ModuleDict({m: nn.Conv1d(64, 64, 3, padding=1) for m in MODS})
            if architecture == "R2":
                self.gate = nn.Sequential(nn.Linear(66, 64), nn.Tanh(), nn.Linear(64, 1, bias=False))
            if architecture == "R1-CAP":
                self.residual = nn.Sequential(nn.Linear(198, 16), nn.ReLU(), nn.Linear(16, 64))
            head_dim = 70
        self.classifier = nn.Linear(head_dim, 3)
        self.regressor = nn.Linear(head_dim, 1)
        # Identically named modules have identical initial parameters across matched architectures.
        for name, module in self.named_modules():
            if isinstance(module, (nn.Linear, nn.Conv1d)):
                with torch.random.fork_rng(devices=[]):
                    torch.manual_seed(stream_seed(seed, name))
                    module.reset_parameters()

    def forward(self, inputs):
        x, support, active = validate_inputs(inputs)
        safe = {m: x[m].masked_fill(~active[m][..., None], 0) for m in MODS}
        if self.architecture.startswith("B-"):
            h = F.relu(self.projection(torch.cat([safe_mean(safe[m], active[m]) for m in self.used], 1)))
            logits, value = self.classifier(h), 3 * self.regressor(h).squeeze(-1).tanh()
            alpha = None
        else:
            gs = []
            for m in MODS:
                a = active[m]
                if self.temporal:
                    e = F.relu(self.projections[m](safe[m])).masked_fill(~a[..., None], 0)
                    conv = self.convolutions[m]
                    count = F.conv1d(a[:, None].to(e.dtype), e.new_ones(1, 1, 3), padding=1).clamp_min(1)
                    v = F.conv1d(e.transpose(1, 2), conv.weight, bias=None, padding=1) / count
                    v = F.relu(v + conv.bias[None, :, None]).transpose(1, 2)
                    g = safe_mean(v, a)
                else:
                    g = F.relu(self.projections[m](safe_mean(safe[m], a)))
                gs.append(g.masked_fill(~a.any(1)[:, None], 0))
            g = torch.stack(gs, 1)
            b = torch.stack([active[m].any(1) for m in MODS], 1)
            rho = torch.stack([active[m].sum(1) for m in MODS], 1) / support.sum(1)[:, None]
            metadata = torch.cat((b.to(g.dtype), rho), 1)
            if self.architecture == "R2":
                q = torch.cat((g, b[..., None].to(g.dtype), rho[..., None]), 2)
                scores = self.gate(q).squeeze(-1).masked_fill(~b, -1e9)
                alpha = scores.softmax(1) * b
                alpha = alpha / alpha.sum(1, keepdim=True).clamp_min(1e-12)
            else:
                alpha = b.to(g.dtype) / b.sum(1, keepdim=True).clamp_min(1)
            fused = (g * alpha[..., None]).sum(1)
            if self.architecture == "R1-CAP":
                fused = fused + self.residual(torch.cat((g.flatten(1), metadata), 1))
            h = torch.cat((fused, metadata), 1)
            logits, value = self.classifier(h), 3 * self.regressor(h).squeeze(-1).tanh()
            empty = ~b.any(1)
            logits = torch.where(empty[:, None], self.prior.clamp_min(1e-30).log()[None], logits)
            value = torch.where(empty, self.median, value)
        require(bool(torch.isfinite(logits).all() & torch.isfinite(value).all()), "Nonfinite model output")
        return dict(logits=logits, regression=value, diagnostics={"fusion_weights": alpha})


def parameter_count(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def prior_statistics(batch, *, split):
    require(split == "train", "Prior fit is train only")
    batch.validate()
    probabilities = torch.bincount(batch.classes, minlength=3).double() / len(batch.classes)
    # Even populations use the midpoint median (torch.median alone returns the lower middle).
    median = batch.values.double().quantile(.5)
    return probabilities.tolist(), float(median)


def late_fusion(outputs, available, prior, median):
    require(set(outputs) == set(available) == set(MODS), "Late fusion requires three reused components")
    probabilities = torch.stack([outputs[m]["logits"].softmax(1) for m in MODS], 1)
    values = torch.stack([outputs[m]["regression"] for m in MODS], 1)
    b = torch.stack([available[m].any(1) for m in MODS], 1)
    weights = b.to(values.dtype) / b.sum(1, keepdim=True).clamp_min(1)
    p = (probabilities * weights[..., None]).sum(1)
    y = (values * weights).sum(1)
    empty = ~b.any(1)
    p = torch.where(empty[:, None], torch.as_tensor(prior, dtype=p.dtype, device=p.device)[None], p)
    y = torch.where(empty, torch.as_tensor(median, dtype=y.dtype, device=y.device), y)
    return dict(logits=p.clamp_min(1e-30).log(), regression=y, diagnostics={"reused_models": 3})


class PriorModel(nn.Module):
    def __init__(self, prior, median):
        super().__init__()
        self.register_buffer("prior", torch.tensor(prior, dtype=torch.float32))
        self.register_buffer("median", torch.tensor(float(median)))

    def forward(self, inputs):
        _, support, _ = validate_inputs(inputs)
        return dict(logits=self.prior.clamp_min(1e-30).log()[None].expand(len(support), -1),
                    regression=self.median.expand(len(support)), diagnostics={"learned_parameters": 0})


class LateModel(nn.Module):
    def __init__(self, components, prior, median):
        super().__init__()
        require(set(components) == set(MODS), "Three same-seed/same-normalizer components required")
        require(len({model.seed for model in components.values()}) == 1, "Late seed mismatch")
        self.components = nn.ModuleDict(components)
        self.register_buffer("prior", torch.tensor(prior, dtype=torch.float32))
        self.register_buffer("median", torch.tensor(float(median)))

    def forward(self, inputs):
        validate_inputs(inputs)
        return late_fusion({m: model(inputs) for m, model in self.components.items()},
                           inputs["available"], self.prior, self.median)
