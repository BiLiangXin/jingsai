"""S02 descriptive ranking and conservative recorded-metric promotion proposal.

Pure functions only: never read predictions, fit thresholds, or update pointers.
Root must restore the proposed winner before atomically changing its registry.
"""
from __future__ import annotations

import math
import statistics

SEEDS = (17, 29, 43)
TOLERANCE = 1e-8
FIELDS = (("clean", "Accuracy", 1), ("clean", "macro_F1", 1),
          ("clean", "MAE", -1), ("clean", "Pearson", 1),
          ("attempted96", "macro_F1", 1), ("attempted96", "MAE", -1))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def numeric(value, lo, hi):
    require(type(value) in (int, float) and math.isfinite(value) and lo <= value <= hi,
            "Invalid metric or resource number")
    return value


def _record(value):
    result = {"clean": {}, "attempted96": {}}
    for scope, key, _ in FIELDS:
        observed = value[scope][key]
        if key == "Pearson" and observed is None:
            require(value[scope].get("Pearson_reason") in
                    ("insufficient_n", "zero_target_variance", "zero_prediction_variance"),
                    "Undefined Pearson requires its explicit reason")
            result[scope][key] = None
            result[scope]["Pearson_reason"] = value[scope]["Pearson_reason"]
        else:
            result[scope][key] = numeric(observed, -1 - 1e-12 if key == "Pearson" else 0,
                                          6 if key == "MAE" else 1 + (1e-12 if key == "Pearson" else 0))
            if key == "Pearson":
                require(value[scope].get("Pearson_reason") is None, "Finite Pearson reason must be null")
                result[scope]["Pearson_reason"] = None
    return result


def summarize_candidate(candidate_id, seed_records, *, parameters, inference_cost=None):
    require(isinstance(candidate_id, str) and candidate_id and len(candidate_id) <= 120,
            "Stable candidate ID required")
    require(type(parameters) is int and parameters >= 0, "Nonnegative parameter count required")
    if inference_cost is not None:
        numeric(inference_cost, 0, float("inf"))
    require(all(type(seed) is int for seed in seed_records) and set(seed_records) <= set(SEEDS),
            "Unexpected or non-integer seed")
    complete = {seed: _record(row) for seed, row in seed_records.items() if row.get("status") == "COMPLETED"}
    result = dict(id=candidate_id, complete=set(complete) == set(SEEDS),
                  completed_seeds=sorted(complete), per_seed=complete, means=None, seed_sd=None,
                  parameters=parameters, inference_cost=inference_cost)
    if not result["complete"]:
        return result
    means, sd = {"clean": {}, "attempted96": {}}, {"clean": {}, "attempted96": {}}
    for scope, key, _ in FIELDS:
        values = [complete[seed][scope][key] for seed in SEEDS]
        if any(value is None for value in values):
            means[scope][key] = sd[scope][key] = None
            means[scope]["Pearson_reason"] = "one_or_more_prespecified_seed_Pearson_undefined"
        else:
            means[scope][key] = math.fsum(values) / 3
            sd[scope][key] = statistics.stdev(values)
            if key == "Pearson":
                means[scope]["Pearson_reason"] = None
    result.update(means=means, seed_sd=sd)
    return result


def _cost(candidate):
    return candidate["inference_cost"] if candidate["inference_cost"] is not None else float("inf")


def promotion_eligibility(champion, candidate):
    require(champion["complete"], "Complete three-seed baseline required")
    if not candidate["complete"]:
        return dict(eligible=False, reasons=["INCOMPLETE_SEED_SET"], strict_gains=[])
    reasons, gains = [], []
    for level, old, new in (("THREE_SEED_MEAN", champion["means"], candidate["means"]),
                            ("FIXED_SEED17", champion["per_seed"][17], candidate["per_seed"][17])):
        for scope, key, direction in FIELDS:
            left, right = old[scope][key], new[scope][key]
            label = level + ":" + scope + ":" + key
            if left is None or right is None:
                # Undefined correlation cannot prove all-metric noninferiority.
                reasons.append(label + ":UNDEFINED_COMPARISON")
                continue
            difference = direction * (right - left)
            if difference < -TOLERANCE:
                reasons.append(label + ":DEGRADED")
            if difference > TOLERANCE:
                gains.append(label)
    if not gains:
        reasons.append("NO_STRICT_IMPROVEMENT_ABOVE_NUMERIC_TOLERANCE")
    return dict(eligible=not reasons, reasons=reasons, strict_gains=gains)


def choose_champion(champion, candidates, *, comparison_complete):
    require(type(comparison_complete) is bool and champion["complete"], "Explicit completed-comparison state required")
    require(len({candidate["id"] for candidate in candidates}) == len(candidates), "Duplicate candidate ID")
    if not comparison_complete:
        return dict(selected_id=champion["id"], promotion_proposed=False,
                    reason="COMPARISON_STILL_OPEN", eligibility=[])
    eligible, diagnostics = [], []
    for candidate in candidates:
        result = promotion_eligibility(champion, candidate)
        diagnostics.append(dict(id=candidate["id"], **result))
        if result["eligible"]:
            eligible.append(candidate)
    eligible.sort(key=lambda c: (-c["means"]["attempted96"]["macro_F1"],
                                c["means"]["attempted96"]["MAE"],
                                -c["means"]["clean"]["macro_F1"], c["means"]["clean"]["MAE"],
                                _cost(c), c["id"]))
    selected = eligible[0]["id"] if eligible else champion["id"]
    return dict(selected_id=selected, promotion_proposed=bool(eligible),
                reason="RESTORE_WINNER_BEFORE_ATOMIC_POINTER_UPDATE" if eligible else "PRESERVE_ORIGINAL_CHAMPION",
                eligibility=diagnostics)


def robust_ranking(champion, candidates):
    require(champion["complete"], "Complete baseline required")
    clean = champion["means"]["clean"]
    eligible = [c for c in candidates if c["complete"] and
                c["means"]["clean"]["macro_F1"] >= clean["macro_F1"] - .01 and
                c["means"]["clean"]["MAE"] <= clean["MAE"] + .05]
    eligible.sort(key=lambda c: (-c["means"]["attempted96"]["macro_F1"], c["means"]["attempted96"]["MAE"],
                                c["parameters"], _cost(c), c["id"]))
    return [c["id"] for c in eligible]


def clean_pareto(candidates):
    complete = [c for c in candidates if c["complete"]]
    known = [c for c in complete if c["means"]["clean"]["Pearson"] is not None]
    def dominates(left, right):
        differences = [direction * (left["means"]["clean"][key] - right["means"]["clean"][key])
                       for scope, key, direction in FIELDS if scope == "clean"]
        return all(d >= -TOLERANCE for d in differences) and any(d > TOLERANCE for d in differences)
    frontier = [c["id"] for c in known if not any(other["id"] != c["id"] and dominates(other, c) for other in known)]
    return dict(pareto_ids=sorted(frontier),
                undefined_Pearson_not_ordered=sorted(c["id"] for c in complete if c["means"]["clean"]["Pearson"] is None),
                incomplete_not_ordered=sorted(c["id"] for c in candidates if not c["complete"]))
