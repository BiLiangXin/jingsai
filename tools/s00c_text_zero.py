"""Pure, aggregate S00C diagnostics for one aligned train or valid split.

The caller is responsible for the authorized data source and split boundary.
This module accepts arrays already in memory. It never opens a data file,
modifies an input, assigns padding/missing meaning, or returns sample rows.
Zero means that every feature in a stored row is *exactly* zero, as in S00B.
"""
from __future__ import annotations

from collections import Counter

import numpy as np


RUN_BINS = ((1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 4, "4"), (5, 5, "5"),
            (6, 10, "6-10"), (11, 20, "11-20"), (21, 10**9, ">20"))
SIMILARITY_THRESHOLD = 0.999  # Descriptive cosine threshold; no support rule.


def _zero_rows(values: np.ndarray) -> np.ndarray:
    """Match S00B zero_rows: exact equality across the feature dimension."""
    return np.all(values == 0, axis=-1)


def _zero_runs(mask: np.ndarray) -> list[tuple[int, int, str]]:
    """Match S00B zero_runs: half-open intervals, full stored sequence."""
    mask = np.asarray(mask, dtype=bool)
    starts = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
    ends = np.flatnonzero(mask & ~np.r_[mask[1:], False]) + 1
    return [(int(a), int(b), "whole" if a == 0 and b == len(mask) else
             "prefix" if a == 0 else "suffix" if b == len(mask) else "internal")
            for a, b in zip(starts, ends)]


def _zero_structure(mask: np.ndarray) -> str:
    """Preserve S00B's mutually exclusive structure categories."""
    runs = _zero_runs(mask)
    if not runs:
        return "NO_ZERO"
    if len(runs) == 1 and runs[0][2] == "whole":
        return "ALL_ZERO"
    kinds = [run[2] for run in runs]
    internal = kinds.count("internal")
    if internal > 1:
        return "MULTIPLE_INTERNAL_RUNS"
    if internal:
        return "INTERNAL_ZERO_RUN"
    if "prefix" in kinds and "suffix" in kinds:
        return "PREFIX_AND_SUFFIX"
    return "PREFIX_ZERO_ONLY" if "prefix" in kinds else "SUFFIX_ZERO_ONLY"


def _run_bin(length: int) -> str:
    return next(label for low, high, label in RUN_BINS if low <= length <= high)


def _summary(values: np.ndarray) -> dict:
    """Small JSON-safe distribution of row-level values; empty means unknown."""
    values = np.asarray(values, dtype=np.float64).ravel()
    if not len(values):
        return {"count": 0, "mean": None, "std": None, "p10": None,
                "median": None, "p90": None}
    return {"count": int(len(values)), "mean": float(np.mean(values)),
            "std": float(np.std(values)), "p10": float(np.quantile(values, 0.1)),
            "median": float(np.median(values)), "p90": float(np.quantile(values, 0.9))}


def _validated_arrays(text_bert: object, text: object, audio: object,
                      vision: object) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    bert, txt, aud, vis = (np.asarray(x) for x in (text_bert, text, audio, vision))
    if bert.ndim != 3 or bert.shape[1] < 2:
        raise ValueError("text_bert must have shape (N, channels>=2, T)")
    n, _, t = bert.shape
    if n < 1 or t < 1:
        raise ValueError("aligned split must have at least one sample and position")
    for name, value in (("text", txt), ("audio", aud), ("vision", vis)):
        if value.ndim != 3 or value.shape[:2] != (n, t) or value.shape[2] < 1:
            raise ValueError(f"{name} must have shape (N, T, D>=1), aligned with text_bert")
    for name, value in (("text_bert", bert), ("text", txt), ("audio", aud), ("vision", vis)):
        if not np.issubdtype(value.dtype, np.number) or not bool(np.all(np.isfinite(value))):
            raise ValueError(f"{name} must contain finite numeric values")
    return bert, txt, aud, vis


def _candidate_mask(bert: np.ndarray) -> tuple[dict, np.ndarray | None]:
    raw = bert[:, 1, :]
    binary = np.isin(raw, (0, 1))
    all_binary = bool(np.all(binary))
    report = {
        "status": "UNKNOWN",
        "meaning": "Channel 1 is an attention-mask candidate, not a final text support rule",
        "channel_index": 1,
        "text_bert_shape": list(bert.shape),
        "text_bert_dtype": str(bert.dtype),
        "sample_count": int(bert.shape[0]),
        "stored_position_count": int(bert.shape[2]),
        "binary_value_fraction": float(np.mean(binary)),
        "nonbinary_position_count": int(np.count_nonzero(~binary)),
    }
    if not all_binary:
        report["reason"] = "Channel 1 contains nonbinary values"
        return report, None
    active = raw == 1
    bad = np.any(np.diff(active.astype(np.int8), axis=1) == 1, axis=1)
    report["non_prefix_sample_count"] = int(np.count_nonzero(bad))
    report["continuous_active_prefix_all_samples"] = bool(not np.any(bad))
    if np.any(bad):
        report["reason"] = "At least one binary row is not a continuous active prefix"
        return report, None
    lengths = active.sum(axis=1)
    report.update({
        "status": "INFERRED",
        "candidate_active_position_count": int(active.sum()),
        "candidate_inactive_position_count": int(active.size - active.sum()),
        "candidate_active_length_summary": _summary(lengths),
        "candidate_active_length_histogram": {str(int(k)): int(v) for k, v in
                                              sorted(Counter(lengths.tolist()).items())},
        "zero_candidate_active_length_sample_count": int(np.count_nonzero(lengths == 0)),
    })
    return report, active


def _row_metrics(text: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # One sample at a time avoids a second full N x T x D array for abs/square.
    norms = np.empty(text.shape[:2], dtype=np.float64)
    mean_abs = np.empty_like(norms)
    signed_mean = np.empty_like(norms)
    for i, rows in enumerate(text):
        norms[i] = np.sqrt(np.einsum("td,td->t", rows, rows, dtype=np.float64))
        mean_abs[i] = np.mean(np.abs(rows), axis=1, dtype=np.float64)
        signed_mean[i] = np.mean(rows, axis=1, dtype=np.float64)
    return norms, mean_abs, signed_mean


def _region_metrics(region: np.ndarray, zeros: np.ndarray,
                    norms: np.ndarray, mean_abs: np.ndarray,
                    signed_mean: np.ndarray) -> dict:
    return {
        "position_count": int(np.count_nonzero(region)),
        "nonzero_row_count": int(np.count_nonzero(region & ~zeros)),
        "zero_row_count": int(np.count_nonzero(region & zeros)),
        "nonzero_row_fraction": (float(np.mean(~zeros[region])) if np.any(region) else None),
        "row_l2_norm": _summary(norms[region]),
        "row_mean_absolute_value": _summary(mean_abs[region]),
        "row_signed_mean": _summary(signed_mean[region]),
    }


def _tail_repetition(text: np.ndarray, active: np.ndarray,
                     norms: np.ndarray) -> dict:
    paired_samples = all_identical = adjacent_exact = adjacent_high = 0
    adjacent_pairs = cosine_defined = first_last_exact = 0
    cosine_values: list[np.ndarray] = []
    for i, length in enumerate(active.sum(axis=1)):
        tail = text[i, int(length):]
        if len(tail) < 2:
            continue
        paired_samples += 1
        exact = np.all(tail[1:] == tail[:-1], axis=1)
        adjacent_exact += int(np.count_nonzero(exact))
        adjacent_pairs += len(exact)
        all_identical += int(bool(np.all(exact)))
        first_last_exact += int(bool(np.array_equal(tail[0], tail[-1])))
        dots = np.einsum("td,td->t", tail[1:], tail[:-1], dtype=np.float64)
        adjacent_norm_products = norms[i, int(length) + 1:] * norms[i, int(length):-1]
        defined = adjacent_norm_products > 0
        cosine_defined += int(np.count_nonzero(defined))
        cosines = np.divide(dots, adjacent_norm_products,
                            out=np.zeros_like(dots), where=defined)
        adjacent_high += int(np.count_nonzero(defined & (cosines >= SIMILARITY_THRESHOLD)))
        cosine_values.append(cosines[defined])
    cosine_distribution = _summary(np.concatenate(cosine_values) if cosine_values else np.empty(0))
    return {
        "criterion": "Adjacent candidate-inactive rows within the same sample",
        "high_cosine_similarity_threshold": SIMILARITY_THRESHOLD,
        "samples_with_at_least_two_inactive_rows": paired_samples,
        "samples_with_all_inactive_rows_exactly_identical": all_identical,
        "samples_with_first_and_last_inactive_rows_exactly_identical": first_last_exact,
        "adjacent_inactive_pair_count": adjacent_pairs,
        "adjacent_exact_equal_pair_count": adjacent_exact,
        "adjacent_cosine_defined_pair_count": cosine_defined,
        "adjacent_cosine_similarity": cosine_distribution,
        "adjacent_high_cosine_pair_count": adjacent_high,
    }


def _cross_table(active: np.ndarray, zero: np.ndarray) -> dict:
    return {"active_zero": int(np.count_nonzero(active & zero)),
            "active_nonzero": int(np.count_nonzero(active & ~zero)),
            "inactive_zero": int(np.count_nonzero(~active & zero)),
            "inactive_nonzero": int(np.count_nonzero(~active & ~zero))}


def _modality_zero_report(zero: np.ndarray, active: np.ndarray | None) -> dict:
    categories: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    lengths: dict[str, Counter[str]] = {x: Counter() for x in ("whole", "prefix", "suffix", "internal")}
    sample_flags: Counter[str] = Counter()
    overlap_run_count: Counter[str] = Counter()
    overlap_position_count: Counter[str] = Counter()
    for i, row in enumerate(zero):
        categories[_zero_structure(row)] += 1
        runs = _zero_runs(row)
        kinds = Counter(kind for _, _, kind in runs)
        for flag, condition in (("whole", kinds["whole"] > 0),
                                ("prefix", kinds["prefix"] > 0),
                                ("suffix", kinds["suffix"] > 0),
                                ("both_ends", kinds["prefix"] > 0 and kinds["suffix"] > 0),
                                ("internal", kinds["internal"] > 0),
                                ("multiple_internal", kinds["internal"] > 1)):
            sample_flags[flag] += int(condition)
        for start, end, kind in runs:
            locations[kind] += 1
            lengths[kind][_run_bin(end - start)] += 1
            if active is not None:
                overlap = int(np.count_nonzero(active[i, start:end]))
                overlap_run_count[kind] += int(overlap > 0)
                overlap_position_count[kind] += overlap
    report = {
        "meaning": "Stored all-zero rows and runs only; not missing or padding",
        "sample_count": int(len(zero)),
        "stored_position_count": int(zero.shape[1]),
        "all_zero_sample_count": int(np.count_nonzero(np.all(zero, axis=1))),
        "total_zero_row_count": int(np.count_nonzero(zero)),
        "s00b_structure_category_counts": {k: int(v) for k, v in sorted(categories.items())},
        "sample_flag_counts": {k: int(sample_flags[k]) for k in
                               ("whole", "prefix", "suffix", "both_ends", "internal", "multiple_internal")},
        "zero_run_count_by_location": {k: int(locations[k]) for k in
                                       ("whole", "prefix", "suffix", "internal")},
        "zero_run_length_histogram_by_location": {
            kind: {label: int(count) for label, count in sorted(lengths[kind].items())}
            for kind in ("whole", "prefix", "suffix", "internal")},
        "candidate_active_overlap": None,
    }
    if active is not None:
        report["candidate_active_overlap"] = {
            **_cross_table(active, zero),
            "zero_run_count_overlapping_candidate_active_by_location": {
                k: int(overlap_run_count[k]) for k in ("whole", "prefix", "suffix", "internal")},
            "zero_run_position_count_overlapping_candidate_active_by_location": {
                k: int(overlap_position_count[k]) for k in ("whole", "prefix", "suffix", "internal")},
        }
    return report


def diagnose_aligned_split(text_bert: object, text: object, audio: object,
                           vision: object) -> tuple[dict, dict]:
    """Return `(text_public, zero_public)` for one aligned train/valid split.

    Outputs contain only aggregate counts and distributions, with no raw rows,
    sample identifiers, token values or labels. The caller adds the split key.
    """
    bert, txt, aud, vis = _validated_arrays(text_bert, text, audio, vision)
    candidate, active = _candidate_mask(bert)
    zeros = {name: _zero_rows(array) for name, array in
             (("text", txt), ("audio", aud), ("vision", vis))}
    text_public = {
        "scope": "one aligned train/valid split; caller records which split",
        "interpretation": "Numerical evidence only; no final padding, observation or missing definition",
        "candidate_mask": candidate,
        "text_features": {"status": "UNKNOWN", "reason": "No binary continuous-prefix candidate mask"},
        "mask_zero_cross": None,
    }
    if active is not None:
        norms, mean_abs, signed_mean = _row_metrics(txt)
        text_public["text_features"] = {
            "status": "VERIFIED",
            "active": _region_metrics(active, zeros["text"], norms, mean_abs, signed_mean),
            "inactive": _region_metrics(~active, zeros["text"], norms, mean_abs, signed_mean),
            "inactive_tail_repetition": _tail_repetition(txt, active, norms),
        }
        text_public["mask_zero_cross"] = {
            name: _cross_table(active, zero) for name, zero in zeros.items()
        }
        text_public["mask_zero_cross"]["audio_vision_both_zero_within_candidate_active"] = int(
            np.count_nonzero(active & zeros["audio"] & zeros["vision"]))
        text_public["mask_zero_cross"]["all_three_zero_within_candidate_active"] = int(
            np.count_nonzero(active & zeros["text"] & zeros["audio"] & zeros["vision"]))
    zero_public = {
        "scope": "one aligned train/valid split; caller records which split",
        "interpretation": "Exact structural zeros in stored rows; no causal or missingness meaning",
        "candidate_mask_status": candidate["status"],
        "audio": _modality_zero_report(zeros["audio"], active),
        "vision": _modality_zero_report(zeros["vision"], active),
    }
    return text_public, zero_public
