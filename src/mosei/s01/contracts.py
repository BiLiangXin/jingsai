"""Tensor interface: original observation and artificial availability stay separate."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
MODS = ("text", "audio", "vision")
DIMS = dict(zip(MODS, (768, 74, 35)))
SEEDS = (17, 29, 43)
ARCHITECTURES = ("B-T", "B-A", "B-V", "B-CAT", "C0", "R0", "R1", "R2", "R1-CAP")


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def stream_seed(seed, name):
    return int(digest([int(seed), name])[:15], 16)


def validate_inputs(inputs):
    require(set(inputs) == {"features", "support", "available"}, "Predictor allowlist violation")
    x, s, a = (inputs[k] for k in ("features", "support", "available"))
    require(set(x) == set(a) == set(MODS), "Three continuous modalities required")
    require(s.dtype == torch.bool and s.ndim == 2 and s.shape[1] == 50 and s.shape[0] > 0,
            "Support must be boolean B x 50")
    require(bool(s.any(1).all()) and not bool((~s[:, :-1] & s[:, 1:]).any()),
            "Nonempty prefix support required")
    for m in MODS:
        require(x[m].shape == (*s.shape, DIMS[m]) and x[m].dtype == torch.float32,
                "Continuous float32 dimensions required")
        require(a[m].shape == s.shape and a[m].dtype == torch.bool,
                "Boolean availability dimensions required")
        require(x[m].device == a[m].device == s.device, "Input device mismatch")
        require(not bool((a[m] & ~s).any()), "Availability outside support")
        require(bool(torch.isfinite(x[m][a[m]]).all()), "Active nonfinite feature")
    return x, s, a


@dataclass
class TensorBatch:
    features: dict
    support: torch.Tensor
    observed: dict
    classes: torch.Tensor
    values: torch.Tensor
    ordinals: list[int]

    def validate(self):
        validate_inputs(self.inputs())
        require(torch.equal(self.observed["text"], self.support), "Original text observed = support")
        n = len(self.support)
        require(self.classes.shape == self.values.shape == (n,), "Target vector shape")
        require(self.classes.dtype == torch.int64 and self.values.is_floating_point(), "Target dtype")
        require(bool(torch.isfinite(self.values).all()) and bool((self.values.abs() <= 3).all()), "Target range")
        expected = torch.where(self.values < 0, 0, torch.where(self.values == 0, 1, 2))
        require(torch.equal(self.classes, expected), "Strict neutral class mapping")
        require(len(self.ordinals) == n and len(set(self.ordinals)) == n
                and all(type(i) is int and i >= 0 for i in self.ordinals), "Private ordinal alignment")
        return self

    def inputs(self, available=None):
        return dict(features=self.features, support=self.support,
                    available=self.observed if available is None else available)

    def take(self, indices):
        ix = torch.as_tensor(indices, device=self.support.device, dtype=torch.long)
        return TensorBatch({m: self.features[m][ix] for m in MODS}, self.support[ix],
                           {m: self.observed[m][ix] for m in MODS}, self.classes[ix],
                           self.values[ix], [self.ordinals[int(i)] for i in indices])

    def to(self, device):
        return TensorBatch({m: self.features[m].to(device) for m in MODS}, self.support.to(device),
                           {m: self.observed[m].to(device) for m in MODS},
                           self.classes.to(device), self.values.to(device), list(self.ordinals))


def from_aligned(batch, ordinals):
    bridge = batch.to_torch()
    x, y = bridge["model_inputs"], bridge["targets"]
    return TensorBatch({m: x[m] for m in MODS}, x["text_support_mask"],
                       {m: x[m + "_observed_mask"] for m in MODS},
                       y["classification_target"], y["regression_target"], list(ordinals)).validate()


def synthetic_batch(n=4, seed=1701, *, dense=False):
    """Closed synthetic factory; no path, dataset or caller-provided feature argument."""
    require(type(n) is int and n > 0, "Positive synthetic batch size")
    g = torch.Generator().manual_seed(seed)
    lengths = torch.full((n,), 50) if dense else torch.randint(1, 51, (n,), generator=g)
    s = torch.arange(50)[None, :] < lengths[:, None]
    x = {m: torch.randn(n, 50, DIMS[m], generator=g) for m in MODS}
    o = {"text": s.clone()}
    for m in MODS[1:]:
        zero = torch.zeros_like(s) if dense else torch.rand(n, 50, generator=g) < .2
        x[m][zero] = 0
        o[m] = s & ~zero
    y = torch.tensor([-1., 0., 1., .25])[torch.arange(n) % 4]
    c = torch.where(y < 0, 0, torch.where(y == 0, 1, 2)).long()
    return TensorBatch(x, s, o, c, y, list(range(n))).validate()


def finite_scalar(x, name):
    require(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x), name)
    return x


def configure_runtime():
    """Fixed runtime used by both resource measurement and the future executor."""
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
