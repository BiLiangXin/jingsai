"""Execute the exact frozen mask/reference rules; no second random implementation."""
from __future__ import annotations

import importlib.util
import math
import torch
from .contracts import ROOT, MODS, SEEDS, digest, require

_spec = importlib.util.spec_from_file_location("frozen_r01_reference", ROOT / "research/r01/reference.py")
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)
SHORT = dict(zip(MODS, ("T", "A", "V")))


def _mask_lists(batch):
    batch.validate()
    return (batch.support.cpu().tolist(), {SHORT[m]: batch.observed[m].cpu().tolist() for m in MODS})


def train_availability(batch, seed, epoch):
    s, o = _mask_lists(batch)
    draws = [reference.train_attempt(row, {m: mask[i] for m, mask in o.items()}, seed, epoch, ordinal)
             for i, (row, ordinal) in enumerate(zip(s, batch.ordinals))]
    available = {m: torch.tensor([d["A"][SHORT[m]] for d in draws], dtype=torch.bool,
                                 device=batch.support.device) for m in MODS}
    return available, dict(attempted=len(draws), ineligible=sum(d["status"] == "INELIGIBLE" for d in draws),
                           clean_requested=sum(d["status"] == "CLEAN_REQUESTED" for d in draws))


class ValidationLibrary:
    """Private masks only; seeds/models/epochs absent from valid generation keys."""
    def __init__(self, batch):
        s, o = _mask_lists(batch)
        self.ordinals, self.views = list(batch.ordinals), {}
        self.mask_fingerprint = digest([s, o, self.ordinals])
        for condition in reference.conditions():
            cid = reference.condition_id(condition)
            self.views[cid] = []
            for rep in range(3 if condition[2] == "random" else 1):
                rows = [reference.generate(row, {m: mask[i] for m, mask in o.items()}, condition,
                                           ordinal=ordinal, replicate=rep)
                        for i, (row, ordinal) in enumerate(zip(s, self.ordinals))]
                available = {m: torch.tensor([r["A"][SHORT[m]] for r in rows], dtype=torch.bool) for m in MODS}
                eligible = [r["status"] == "ELIGIBLE" for r in rows]
                fingerprint = digest(dict(condition=cid, replicate=rep, root=1103,
                                          ordinals=self.ordinals, corruption=[r["C"] for r in rows]))
                self.views[cid].append(dict(available=available, eligible=eligible, fingerprint=fingerprint,
                                           replicate=rep))

    def validate_population(self, batch):
        s, o = _mask_lists(batch)
        require(self.mask_fingerprint == digest([s, o, batch.ordinals]), "Validation population/masks changed")


def metric_report(batch, classes, values):
    return reference.metrics(batch.classes.cpu().tolist(), batch.values.cpu().tolist(),
                             classes.cpu().tolist(), values.cpu().tolist())


class CheckpointSelector:
    def __init__(self):
        self.trace = []

    def update(self, f, mae):
        require(len(self.trace) < 100, "Maximum epochs reached")
        self.trace.append((float(f), float(mae)))
        result = reference.choose_checkpoint(self.trace)
        return dict(save=result["best_epoch"] == len(self.trace), stop=result["stop_epoch"] is not None,
                    **result)


def seed_mean(scores):
    require(set(scores) == set(SEEDS), "All three prespecified seeds required")
    for row in scores.values():
        require(all(math.isfinite(row[k]) for k in ("macro_F1", "MAE")), "Nonfinite seed score")
    return {k: math.fsum(scores[s][k] for s in SEEDS) / 3 for k in ("macro_F1", "MAE")}


def select_normalizer(clean_bcat):
    require(set(clean_bcat) == {"identity", "zscore"}, "Both B-CAT normalizers required")
    means = {k: seed_mean(v) for k, v in clean_bcat.items()}
    return min(means, key=lambda k: (-means[k]["macro_F1"], means[k]["MAE"], k != "identity"))


def summarize_configuration(config_id, records, *, objective):
    require(objective in ("clean", "attempted96"), "Selection objective")
    require(set(records) == set(SEEDS), "No best seed selection")
    clean = seed_mean({s: records[s]["clean"] for s in SEEDS})
    if objective == "clean":
        score = clean
    else:
        require(all("condition_reports" in records[s] for s in SEEDS), "Paired full condition reports required")
        aggregated = reference.aggregate({s: records[s]["condition_reports"] for s in SEEDS})
        require(all(records[s]["attempted96"] == aggregated["per_seed"][s] for s in SEEDS),
                "Stored attempted96 score differs from paired reports")
        score = aggregated["across_seeds"]
    params = {records[s]["parameters"] for s in SEEDS}
    require(len(params) == 1, "Configuration capacity changed across seeds")
    return dict(id=config_id, F=score["macro_F1"], MAE=score["MAE"],
                clean_F=clean["macro_F1"], clean_MAE=clean["MAE"], parameters=params.pop())


def final_choice(configurations, baseline_id):
    """B* is locked first. Robust mean ranking then exactly one seed17 guard."""
    require(baseline_id in configurations, "Locked B* required")
    base = summarize_configuration(baseline_id, configurations[baseline_id], objective="clean")
    candidates = [summarize_configuration(cid, records, objective="attempted96")
                  for cid, records in configurations.items() if cid != baseline_id]
    ranked = reference.rank_configs(candidates, dict(F=base["F"], MAE=base["MAE"])) if candidates else []
    winner_id = ranked[0]["id"] if ranked else baseline_id
    def record(cid):
        clean = configurations[cid][17]["clean"]
        return dict(configuration=cid, seed=17, clean_F=clean["macro_F1"], clean_MAE=clean["MAE"])
    return reference.select_final(record(winner_id), record(baseline_id))
