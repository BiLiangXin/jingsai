"""Train-only stable statistics; transform never recomputes original observation."""
import torch
from .contracts import DIMS, MODS, TensorBatch, require


class Normalizer:
    def __init__(self, method):
        require(method in ("identity", "zscore"), "Only two frozen normalizers")
        self.method, self.statistics, self.fit_split = method, {}, None

    def fit(self, batches, *, split):
        require(split == "train", "Normalizer fit accepts TRAIN only")
        totals = {m: (0, torch.zeros(d, dtype=torch.float64), torch.zeros(d, dtype=torch.float64))
                  for m, d in DIMS.items()}
        for batch in batches:
            batch.validate()
            for m in MODS:
                x = batch.features[m][batch.observed[m]].detach().cpu().double()
                if len(x) == 0:
                    continue
                n, mean, m2 = totals[m]
                k = len(x)
                local_mean = x.mean(0)
                local_m2 = ((x - local_mean) ** 2).sum(0)
                delta = local_mean - mean
                totals[m] = (n + k, mean + delta * k / (n + k), m2 + local_m2 + delta.square() * n * k / (n + k))
        for m, (n, mean, m2) in totals.items():
            require(n > 0, "No observed train vectors for " + m)
            std = (m2 / n).clamp_min(0).sqrt()
            require(bool(torch.isfinite(mean).all() & torch.isfinite(std).all()), "Nonfinite train statistics")
            self.statistics[m] = dict(count=n, mean=mean.tolist(), std=std.tolist())
        self.fit_split = "train"
        return self

    def transform(self, batch):
        require(self.fit_split == "train", "Normalizer is not train-fitted")
        batch.validate()
        if self.method == "identity":
            return batch
        x = {}
        for m in MODS:
            value, observed = batch.features[m], batch.observed[m]
            stats = self.statistics[m]
            mean = torch.tensor(stats["mean"], dtype=torch.float64, device=value.device)
            std = torch.tensor(stats["std"], dtype=torch.float64, device=value.device)
            scale = torch.where(std == 0, 1., std)
            changed = value.clone()
            changed[observed] = ((value[observed].double() - mean) / scale).float()
            require(bool(torch.isfinite(changed[observed]).all()), "Normalization overflow")
            x[m] = changed
        return TensorBatch(x, batch.support, batch.observed, batch.classes, batch.values, batch.ordinals)

    def state_dict(self):
        require(self.fit_split == "train", "Normalizer not fitted")
        return dict(method=self.method, fit_split=self.fit_split, statistics=self.statistics)

    @classmethod
    def from_state_dict(cls, state):
        require(state["fit_split"] == "train", "Restored normalizer must be train fitted")
        obj = cls(state["method"])
        require(set(state["statistics"]) == set(MODS), "Normalizer statistics incomplete")
        for m, d in DIMS.items():
            st = state["statistics"][m]
            require(type(st["count"]) is int and st["count"] > 0, "Normalizer count")
            for field in ("mean", "std"):
                v = torch.tensor(st[field], dtype=torch.float64)
                require(v.shape == (d,) and bool(torch.isfinite(v).all()), "Normalizer shape/finite")
                require(field != "std" or bool((v >= 0).all()), "Negative standard deviation")
        obj.statistics, obj.fit_split = state["statistics"], "train"
        return obj
