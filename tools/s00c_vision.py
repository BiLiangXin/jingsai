"""Pure, aggregate-only S00C diagnostics for unaligned feature boundaries.

The zero-row predicate is the frozen S00B mechanical test: every feature
dimension must equal zero exactly. The output describes numerical structure;
it does not classify a row as padding, missing, invalid, or observed.

Only ``train`` and ``valid`` are accepted. Public results contain aggregate
counts and distributions. Ordered per-sample diagnostics are returned
separately for storage under a run's gitignored ``private`` directory.
"""

from __future__ import annotations

from collections import Counter
from math import ceil
from typing import Any

import numpy as np


QUANTILES = (("p0", 0), ("p25", 25), ("p50", 50), ("p75", 75),
             ("p90", 90), ("p99", 99), ("p100", 100))


def _summary(values: Any) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return {"count": 0, "quantiles": {key: None for key, _ in QUANTILES}}
    return {
        "count": int(array.size),
        "quantiles": {key: float(np.percentile(array, percentile))
                      for key, percentile in QUANTILES},
    }


def _histogram(values: Any) -> dict[str, int]:
    return {str(int(key)): int(count)
            for key, count in sorted(Counter(int(x) for x in values).items())}


def _runs(mask: np.ndarray) -> list[tuple[int, int, str]]:
    """Return S00B-equivalent half-open zero-run intervals and kind labels."""
    mask = np.asarray(mask, dtype=bool)
    starts = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
    ends = np.flatnonzero(mask & ~np.r_[mask[1:], False]) + 1
    size = len(mask)
    return [
        (int(start), int(end),
         "whole" if start == 0 and end == size else
         "prefix" if start == 0 else
         "suffix" if end == size else "internal")
        for start, end in zip(starts, ends)
    ]


def _structure(runs: list[tuple[int, int, str]], length: int) -> str:
    if length == 0:
        return "NO_DECLARED_REGION"
    if not runs:
        return "NO_ZERO"
    if len(runs) == 1 and runs[0][2] == "whole":
        return "ALL_ZERO"
    kinds = [kind for _, _, kind in runs]
    internal = kinds.count("internal")
    if internal > 1:
        return "MULTIPLE_INTERNAL_RUNS"
    if internal:
        return "INTERNAL_ZERO_RUN"
    if "prefix" in kinds and "suffix" in kinds:
        return "PREFIX_AND_SUFFIX"
    return "PREFIX_ZERO_ONLY" if "prefix" in kinds else "SUFFIX_ZERO_ONLY"


def _length_bins(lengths: np.ndarray, affected: np.ndarray,
                 after_counts: np.ndarray, sequence_length: int) -> list[dict]:
    # Fixed fractions of stored T make the grouping reproducible at any T.
    boundaries = sorted({0, sequence_length, *(int(sequence_length * share)
                                                 for share in (0.1, 0.2, 0.4, 0.6, 0.8))})
    intervals = [(0, 0)]
    lower = 1
    for boundary in boundaries[1:]:
        upper = min(boundary, sequence_length - 1)
        if lower <= upper:
            intervals.append((lower, upper))
        lower = upper + 1
    if sequence_length > 0:
        intervals.append((sequence_length, sequence_length))
    result = []
    for lo, hi in intervals:
        selected = (lengths >= lo) & (lengths <= hi)
        count = int(np.count_nonzero(selected))
        affected_count = int(np.count_nonzero(affected & selected))
        result.append({
            "min_inclusive": lo,
            "max_inclusive": hi,
            "sample_count": count,
            "affected_sample_count": affected_count,
            "affected_rate": affected_count / count if count else None,
            "after_nonzero_row_count": int(np.sum(after_counts[selected])),
        })
    return result


def _top_fraction_share(counts: np.ndarray, fraction: float) -> dict:
    k = max(1, ceil(len(counts) * fraction))
    total = int(np.sum(counts))
    top = int(np.sum(np.sort(counts)[-k:]))
    return {"sample_count": k, "after_nonzero_row_count": top,
            "share_of_after_nonzero_rows": top / total if total else None}


def diagnose_length_boundary(
    values: np.ndarray, lengths: np.ndarray, *, split: str, modality: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Diagnose one train/valid split; return (public aggregates, private rows).

    ``values`` has shape ``(N,T,D)`` and ``lengths`` shape ``(N,)``. A
    nonzero row is the complement of S00B's exact all-zero predicate. Indices
    are zero-based; ``first_after_offset=0`` means the row at index ``length``.
    Empty statistics use null quantiles, never fabricated zeros.
    """
    if split not in {"train", "valid"}:
        raise ValueError("S00C boundary diagnostics allow train/valid only")
    if modality not in {"audio", "vision"}:
        raise ValueError("modality must be audio or vision")
    data = np.asarray(values)
    declared = np.asarray(lengths)
    if data.ndim != 3 or data.shape[2] < 1:
        raise ValueError("values must have shape (N,T,D), D >= 1")
    n, t, _ = data.shape
    if n < 1 or t < 1:
        raise ValueError("values must have N >= 1 and T >= 1")
    if declared.shape != (n,) or not np.issubdtype(declared.dtype, np.number):
        raise ValueError("lengths must be a numeric vector with N entries")
    if not np.all(np.isfinite(declared)) or not np.all(declared == np.floor(declared)):
        raise ValueError("lengths must be finite integers")
    if np.any((declared < 0) | (declared > t)):
        raise ValueError("lengths must lie in [0,T]")
    if not np.issubdtype(data.dtype, np.number):
        raise ValueError("features must be finite numeric values")
    declared = declared.astype(np.int64, copy=False)

    # Work one sample at a time so audio does not create a second full-sized
    # feature tensor while the official unaligned array is already in memory.
    zero = np.empty((n, t), dtype=bool)
    norms = np.empty((n, t), dtype=np.float64)
    for index in range(n):
        row = data[index]
        if not np.all(np.isfinite(row)):
            raise ValueError("features must be finite numeric values")
        zero[index] = np.all(row == 0, axis=-1)
        norms[index] = np.linalg.norm(row.astype(np.float64, copy=False), axis=-1)
    inside = np.arange(t)[None, :] < declared[:, None]
    after = ~inside
    nonzero = ~zero
    inside_nonzero = inside & nonzero
    after_nonzero = after & nonzero
    after_counts = np.count_nonzero(after_nonzero, axis=1)
    inside_zero_counts = np.count_nonzero(inside & zero, axis=1)
    affected = after_counts > 0
    whole_zero = np.all(zero, axis=1)

    private_rows: list[dict[str, Any]] = []
    inside_structures: Counter[str] = Counter()
    stored_structures: Counter[str] = Counter()
    inside_run_types: Counter[str] = Counter()
    stored_run_types: Counter[str] = Counter()
    inside_run_lengths: dict[str, list[int]] = {kind: [] for kind in
                                                ("whole", "prefix", "suffix", "internal")}
    stored_run_lengths: dict[str, list[int]] = {kind: [] for kind in
                                                ("whole", "prefix", "suffix", "internal")}
    boundary_zero_run_counts: Counter[str] = Counter()
    boundary_zero_row_counts: Counter[str] = Counter()
    samples_with_crossing_zero_run = 0
    after_run_counts: list[int] = []
    after_run_lengths: list[int] = []
    after_run_start_offsets: list[int] = []
    after_run_end_offsets_exclusive: list[int] = []
    after_nonzero_row_offsets: list[int] = []
    after_zero_gap_lengths: list[int] = []
    first_after_offsets: list[int] = []
    last_after_offsets: list[int] = []
    extension_offsets: list[int] = []
    last_nonzero_indices: list[int] = []
    per_sample_norm_ratios: list[float] = []
    samples_with_after_and_inside_zero = 0
    samples_with_no_inside_nonzero_and_after = 0
    boundary_only_count = 0

    for index in range(n):
        length = int(declared[index])
        active_positions = np.flatnonzero(nonzero[index])
        last_nonzero = int(active_positions[-1]) if active_positions.size else None
        if last_nonzero is not None:
            last_nonzero_indices.append(last_nonzero)
        inside_runs = _runs(zero[index, :length])
        inside_structure = _structure(inside_runs, length)
        inside_structures[inside_structure] += 1
        for start, end, kind in inside_runs:
            inside_run_types[kind] += 1
            inside_run_lengths[kind].append(end - start)
        stored_runs = _runs(zero[index])
        stored_structure = _structure(stored_runs, t)
        stored_structures[stored_structure] += 1
        stored_runs_private = []
        has_crossing_run = False
        for start, end, kind in stored_runs:
            stored_run_types[kind] += 1
            stored_run_lengths[kind].append(end - start)
            relation = ("entirely_inside" if end <= length else
                        "entirely_after" if start >= length else
                        "crosses_declared_boundary")
            boundary_zero_run_counts[relation] += 1
            boundary_zero_row_counts[relation] += end - start
            has_crossing_run |= relation == "crosses_declared_boundary"
            stored_runs_private.append({"start": start, "end_exclusive": end,
                                        "kind": kind, "boundary_relation": relation})
        samples_with_crossing_zero_run += int(has_crossing_run)
        # _runs operates on a nonzero mask here; its kind is irrelevant.
        after_runs = [(start + length, end + length)
                      for start, end, _ in _runs(after_nonzero[index, length:])]
        run_starts = [start - length for start, _ in after_runs]
        run_lengths = [end - start for start, end in after_runs]
        zero_gaps = [after_runs[k + 1][0] - after_runs[k][1]
                     for k in range(len(after_runs) - 1)]
        after_run_counts.append(len(after_runs))
        after_run_lengths.extend(run_lengths)
        after_run_start_offsets.extend(run_starts)
        after_run_end_offsets_exclusive.extend(end - length for _, end in after_runs)
        after_nonzero_row_offsets.extend(
            int(position - length) for position in np.flatnonzero(after_nonzero[index]))
        after_zero_gap_lengths.extend(zero_gaps)
        first_after = run_starts[0] if run_starts else None
        last_after = last_nonzero - length if run_starts else None
        extension = last_nonzero + 1 - length if run_starts else None
        if first_after is not None:
            first_after_offsets.append(first_after)
            last_after_offsets.append(last_after)
            extension_offsets.append(extension)
            boundary_only_count += int(after_counts[index] == 1 and first_after == 0)
            samples_with_after_and_inside_zero += int(inside_zero_counts[index] > 0)
            samples_with_no_inside_nonzero_and_after += int(not np.any(inside_nonzero[index]))
        inside_positive_norms = norms[index, inside_nonzero[index]]
        after_positive_norms = norms[index, after_nonzero[index]]
        inside_median = float(np.median(inside_positive_norms)) if inside_positive_norms.size else None
        after_median = float(np.median(after_positive_norms)) if after_positive_norms.size else None
        norm_ratio = (after_median / inside_median
                      if inside_median is not None and inside_median > 0 and after_median is not None
                      else None)
        if norm_ratio is not None:
            per_sample_norm_ratios.append(norm_ratio)
        private_rows.append({
            "index": index,
            "declared_length": length,
            "stored_sequence_length": t,
            "last_nonzero_index": last_nonzero,
            "inside_nonzero_row_count": int(np.count_nonzero(inside_nonzero[index])),
            "inside_zero_row_count": int(inside_zero_counts[index]),
            "inside_zero_structure": inside_structure,
            "inside_zero_runs": [{"start": a, "end_exclusive": b, "kind": kind}
                                 for a, b, kind in inside_runs],
            "stored_zero_structure": stored_structure,
            "stored_zero_runs": stored_runs_private,
            "after_nonzero_row_count": int(after_counts[index]),
            "after_nonzero_runs": [{"start_offset": start - length,
                                    "length": end - start} for start, end in after_runs],
            "after_zero_gap_lengths": zero_gaps,
            "first_after_nonzero_offset": first_after,
            "last_after_nonzero_offset": last_after,
            "last_nonzero_end_extension": extension,
            "inside_nonzero_norm_median": inside_median,
            "after_nonzero_norm_median": after_median,
            "after_to_inside_nonzero_norm_median_ratio": norm_ratio,
            "whole_sequence_zero": bool(whole_zero[index]),
        })

    inside_norms = norms[inside]
    after_norms = norms[after]
    inside_nonzero_norms = norms[inside_nonzero]
    after_nonzero_norms = norms[after_nonzero]
    inside_global_median = (float(np.median(inside_nonzero_norms))
                            if inside_nonzero_norms.size else None)
    after_global_median = (float(np.median(after_nonzero_norms))
                           if after_nonzero_norms.size else None)
    extension_hist = _histogram(extension_offsets)
    dominant_extension = (max(extension_hist, key=lambda key: extension_hist[key])
                          if extension_hist else None)
    public = {
        "split": split,
        "modality": modality,
        "interpretation": "NUMERICAL_STRUCTURE_ONLY; no missing/padding/observation decision",
        "definitions": {
            "zero_row": "all feature dimensions exactly equal zero (S00B predicate)",
            "declared_inside": "zero-based position < official declared length",
            "after_offset": "zero-based row position minus declared length; 0 is first row after boundary",
            "last_nonzero_end_extension": "last_nonzero_index + 1 - declared_length",
            "runs": "contiguous row spans; end indices exclusive",
            "norm": "Euclidean L2 norm of a feature row",
            "off_by_one": "exactly one nonzero after row, at offset 0; descriptive candidate only",
        },
        "sample_count": n,
        "stored_sequence_length": t,
        "declared_length": {"summary": _summary(declared), "histogram": _histogram(declared)},
        "last_nonzero_index": _summary(last_nonzero_indices),
        "whole_sequence_zero": {
            "sample_count": int(np.count_nonzero(whole_zero)),
            "declared_length_zero_count": int(np.count_nonzero(whole_zero & (declared == 0))),
            "declared_length_positive_count": int(np.count_nonzero(whole_zero & (declared > 0))),
            "declared_length_histogram": _histogram(declared[whole_zero]),
        },
        "declared_length_zero": {
            "sample_count": int(np.count_nonzero(declared == 0)),
            "with_nonzero_row_count": int(np.count_nonzero((declared == 0) & ~whole_zero)),
        },
        "inside": {
            "nonzero_row_count": int(np.count_nonzero(inside_nonzero)),
            "zero_row_count": int(np.sum(inside_zero_counts)),
            "zero_rows_per_sample": {"summary": _summary(inside_zero_counts),
                                     "histogram": _histogram(inside_zero_counts)},
            "zero_structure_sample_counts": dict(sorted(inside_structures.items())),
            "zero_run_counts_by_kind": dict(sorted(inside_run_types.items())),
            "zero_run_lengths_by_kind": {
                kind: {"summary": _summary(lengths_for_kind),
                       "histogram": _histogram(lengths_for_kind)}
                for kind, lengths_for_kind in inside_run_lengths.items()
            },
        },
        "stored_zero_structure": {
            "zero_row_count": int(np.count_nonzero(zero)),
            "zero_structure_sample_counts": dict(sorted(stored_structures.items())),
            "zero_run_counts_by_kind": dict(sorted(stored_run_types.items())),
            "zero_run_lengths_by_kind": {
                kind: {"summary": _summary(lengths_for_kind),
                       "histogram": _histogram(lengths_for_kind)}
                for kind, lengths_for_kind in stored_run_lengths.items()
            },
            "declared_boundary_relation": {
                "zero_run_counts": dict(sorted(boundary_zero_run_counts.items())),
                "zero_row_counts": dict(sorted(boundary_zero_row_counts.items())),
                "sample_count_with_crossing_zero_run": samples_with_crossing_zero_run,
                "zero_row_count_inside_declared_length": int(np.sum(inside_zero_counts)),
                "zero_row_count_after_declared_length": int(np.count_nonzero(zero & after)),
            },
        },
        "after": {
            "nonzero_row_count": int(np.sum(after_counts)),
            "affected_sample_count": int(np.count_nonzero(affected)),
            "affected_sample_rate": float(np.mean(affected)),
            "nonzero_rows_per_sample": {"summary": _summary(after_counts),
                                        "histogram": _histogram(after_counts)},
            "nonzero_run_count": len(after_run_lengths),
            "run_count_per_sample": {"summary": _summary(after_run_counts),
                                     "histogram": _histogram(after_run_counts)},
            "run_length": {"summary": _summary(after_run_lengths),
                           "histogram": _histogram(after_run_lengths)},
            "run_start_offset": {"summary": _summary(after_run_start_offsets),
                                 "histogram": _histogram(after_run_start_offsets)},
            "run_end_offset_exclusive": {"summary": _summary(after_run_end_offsets_exclusive),
                                         "histogram": _histogram(after_run_end_offsets_exclusive)},
            "nonzero_row_offset": {"summary": _summary(after_nonzero_row_offsets),
                                   "histogram": _histogram(after_nonzero_row_offsets)},
            "zero_gap_between_runs": {"summary": _summary(after_zero_gap_lengths),
                                      "histogram": _histogram(after_zero_gap_lengths)},
            "first_nonzero_offset": {"summary": _summary(first_after_offsets),
                                     "histogram": _histogram(first_after_offsets)},
            "last_nonzero_offset": {"summary": _summary(last_after_offsets),
                                    "histogram": _histogram(last_after_offsets)},
            "last_nonzero_end_extension": {
                "summary": _summary(extension_offsets),
                "histogram": extension_hist,
                "dominant_offset": int(dominant_extension) if dominant_extension is not None else None,
                "dominant_offset_sample_count": (extension_hist[dominant_extension]
                                                 if dominant_extension is not None else 0),
                "dominant_offset_affected_share": (extension_hist[dominant_extension] / len(extension_offsets)
                                                   if dominant_extension is not None else None),
            },
            "boundary_row_nonzero_sample_count": int(sum(bool(after_nonzero[i, declared[i]])
                                                       for i in range(n) if declared[i] < t)),
            "off_by_one_exact_sample_count": boundary_only_count,
            "samples_with_inside_zero_and_after_nonzero": samples_with_after_and_inside_zero,
            "samples_with_no_inside_nonzero_and_after": samples_with_no_inside_nonzero_and_after,
            "top_1pct_concentration": _top_fraction_share(after_counts, 0.01),
            "top_5pct_concentration": _top_fraction_share(after_counts, 0.05),
            "top_10pct_concentration": _top_fraction_share(after_counts, 0.10),
        },
        "length_bins": _length_bins(declared, affected, after_counts, t),
        "row_norms": {
            "inside_all_rows": _summary(inside_norms),
            "inside_nonzero_rows": _summary(inside_nonzero_norms),
            "after_all_rows": _summary(after_norms),
            "after_nonzero_rows": _summary(after_nonzero_norms),
            "after_to_inside_nonzero_global_median_ratio":
                after_global_median / inside_global_median
                if inside_global_median is not None and inside_global_median > 0
                and after_global_median is not None else None,
            "per_sample_after_to_inside_nonzero_median_ratio": _summary(per_sample_norm_ratios),
            "affected_samples_without_inside_nonzero_for_ratio": samples_with_no_inside_nonzero_and_after,
        },
    }
    return public, private_rows


def diagnose_unaligned_split(
    audio: np.ndarray, audio_lengths: np.ndarray,
    vision: np.ndarray, vision_lengths: np.ndarray, *, split: str,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Diagnose paired audio/vision for one split without exposing rows publicly."""
    audio_public, audio_private = diagnose_length_boundary(
        audio, audio_lengths, split=split, modality="audio")
    vision_public, vision_private = diagnose_length_boundary(
        vision, vision_lengths, split=split, modality="vision")
    if len(audio_private) != len(vision_private):
        raise ValueError("paired audio and vision sample counts differ")
    audio_affected = np.array([row["after_nonzero_row_count"] > 0 for row in audio_private])
    vision_affected = np.array([row["after_nonzero_row_count"] > 0 for row in vision_private])
    public = {
        "split": split,
        "audio": audio_public,
        "vision": vision_public,
        "paired_after_nonzero_sample_counts": {
            "both": int(np.count_nonzero(audio_affected & vision_affected)),
            "audio_only": int(np.count_nonzero(audio_affected & ~vision_affected)),
            "vision_only": int(np.count_nonzero(~audio_affected & vision_affected)),
            "neither": int(np.count_nonzero(~audio_affected & ~vision_affected)),
        },
    }
    return public, {"audio": audio_private, "vision": vision_private}
