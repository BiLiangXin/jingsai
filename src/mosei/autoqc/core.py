"""Deterministic text/time evidence comparison for S06.

The two acoustic estimators are not ground truth and may share errors.
"""
from __future__ import annotations

import math
import re
import unicodedata
from statistics import median

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)*|[0-9]+")


def words(text: str) -> list[str]:
    """NFKC/lowercase, boundary punctuation removal, no semantic rewrites."""
    return WORD_RE.findall(unicodedata.normalize("NFKC", text).lower())


def _edit_tables(ref: list[str], hyp: list[str]):
    n, m = len(ref), len(hyp)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    paths = [[0] * (m + 1) for _ in range(n + 1)]
    paths[0][0] = 1
    for i in range(n + 1):
        for j in range(m + 1):
            if i == j == 0:
                continue
            choices = []
            if i:
                choices.append((cost[i - 1][j] + 1, paths[i - 1][j]))
            if j:
                choices.append((cost[i][j - 1] + 1, paths[i][j - 1]))
            if i and j:
                choices.append((cost[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]), paths[i - 1][j - 1]))
            best = min(x[0] for x in choices)
            cost[i][j] = best
            paths[i][j] = sum(k for c, k in choices if c == best)
    back_cost = [[0] * (m + 1) for _ in range(n + 1)]
    back_paths = [[0] * (m + 1) for _ in range(n + 1)]
    back_paths[n][m] = 1
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            choices = []
            if i < n:
                choices.append((back_cost[i + 1][j] + 1, back_paths[i + 1][j]))
            if j < m:
                choices.append((back_cost[i][j + 1] + 1, back_paths[i][j + 1]))
            if i < n and j < m:
                choices.append((back_cost[i + 1][j + 1] + (ref[i] != hyp[j]), back_paths[i + 1][j + 1]))
            best = min(x[0] for x in choices)
            back_cost[i][j] = best
            back_paths[i][j] = sum(k for c, k in choices if c == best)
    return cost, paths, back_cost, back_paths


def unique_exact_matches(ref: list[str], hyp: list[str]) -> dict:
    """Only report a word pair if every minimum-cost DP path contains it."""
    if not ref:
        return {"edit_distance": len(hyp), "disagreement": None,
                "unique": {}, "ambiguous_ref": [], "reason": "EMPTY_REFERENCE"}
    cost, paths, back_cost, back_paths = _edit_tables(ref, hyp)
    total = paths[len(ref)][len(hyp)]
    unique = {}
    ambiguous = []
    for i, token in enumerate(ref):
        candidates = []
        for j, candidate in enumerate(hyp):
            if token != candidate:
                continue
            if cost[i][j] + back_cost[i + 1][j + 1] != cost[-1][-1]:
                continue
            paths_with_edge = paths[i][j] * back_paths[i + 1][j + 1]
            candidates.append((j, paths_with_edge))
        certain = [j for j, count in candidates if count == total]
        if len(certain) == 1:
            unique[i] = certain[0]
        elif candidates:
            ambiguous.append(i)
    return {"edit_distance": cost[-1][-1],
            "disagreement": cost[-1][-1] / len(ref),
            "unique": unique, "ambiguous_ref": ambiguous,
            "reason": "OK"}


def valid_interval(pair, lower: float, upper: float) -> bool:
    if pair is None or len(pair) != 2:
        return False
    a, b = pair
    try:
        return all(math.isfinite(float(v)) for v in (a, b, lower, upper)) and lower <= float(a) < float(b) <= upper
    except (TypeError, ValueError):
        return False


def audit_window(ref_words: list[str], hyp_words: list[str],
                 a_times: dict[int, tuple[float, float]],
                 b_times: list[tuple[float, float] | None] | None,
                 target: list[int], audio_start: float, audio_end: float,
                 *, max_disagreement: float = .35, max_delta: float = .25) -> dict:
    match = unique_exact_matches(ref_words, hyp_words)
    target = sorted(set(target))
    if not target:
        return {"acoustic_basis": "TEXT_ONLY", "reason_codes": ["NO_ORDINARY_TARGET_WORD"],
                "transcript_disagreement": match["disagreement"], "unique_word_fraction": None,
                "max_boundary_delta": None}
    if any(i < 0 or i >= len(ref_words) for i in target):
        raise ValueError("TARGET_INDEX_OUT_OF_RANGE")
    matched = [i for i in target if i in match["unique"]]
    fraction = len(matched) / len(target)
    reason = []
    if match["disagreement"] is None:
        reason.append("EMPTY_REFERENCE")
    elif match["disagreement"] > max_disagreement:
        reason.append("TRANSCRIPT_DISAGREEMENT")
    if len(matched) != len(target):
        reason.append("AMBIGUOUS_OR_UNMATCHED_WORD")
    b_valid = {}
    for i in matched:
        j = match["unique"][i]
        pair = b_times[j] if b_times is not None and j < len(b_times) else None
        if valid_interval(pair, audio_start, audio_end):
            b_valid[i] = pair
    if len(b_valid) != len(target):
        reason.append("ASR_TIME_MISSING_OR_INVALID")
    a_valid = {i: a_times[i] for i in target
               if i in a_times and valid_interval(a_times[i], audio_start, audio_end)}
    deltas = [max(abs(a_valid[i][0] - b_valid[i][0]), abs(a_valid[i][1] - b_valid[i][1]))
              for i in target if i in a_valid and i in b_valid]
    if b_times is None:
        reason.append("ASR_NOT_EVALUATED")
        status = "NOT_EVALUATED"
    elif len(b_valid) == len(target) and not a_valid and not reason:
        status = "SINGLE_ASR_ESTIMATE"
    elif len(b_valid) == len(target) and len(a_valid) == len(target) and not reason:
        status = "DUAL_CONSISTENT_ESTIMATE" if max(deltas) <= max_delta else "ESTIMATOR_CONFLICT"
        if status == "ESTIMATOR_CONFLICT":
            reason.append("BOUNDARY_DELTA_EXCEEDS_THRESHOLD")
    elif a_valid or b_valid:
        status = "ESTIMATOR_CONFLICT" if b_times is not None and a_valid else "TEXT_ONLY"
    else:
        status = "TEXT_ONLY" if b_times is not None else "NOT_EVALUATED"
    return {"acoustic_basis": status, "reason_codes": reason,
            "transcript_disagreement": match["disagreement"],
            "unique_word_fraction": fraction,
            "dual_time_coverage": len(deltas) / len(target),
            "median_boundary_delta": median(deltas) if deltas else None,
            "max_boundary_delta": max(deltas) if deltas else None,
            "matched_ref_indices": matched,
            "ambiguous_ref_indices": [i for i in target if i in match["ambiguous_ref"]]}
