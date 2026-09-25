"""Aggregate private QC outputs without publishing sample text or identifiers."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser()
    for key in ("q1-audit", "prefix", "swap", "output"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    root = Path(a.q1_audit)
    records = read(root / "Q1_SOURCE_AUDIT_PRIVATE.json")
    diagnostics = read(root / "CONTROLLED_PERTURBATION_PRIVATE.json")
    prefix = read(Path(a.prefix) / "PREFIX_CONTROL_RESULTS_PRIVATE.json")
    swap = read(Path(a.swap) / "SWAP_PRIVATE.json")
    if len(records) != 100 or len(prefix) != 12 or len(swap) != 12:
        raise ValueError("CONTROL_COUNT_MISMATCH")
    ablation = {name: sum(bool(r[name]) for r in records)
                for name in ("qc0_mechanical", "qc1_asr_lexical", "qc2_time_pts_abstention")}
    if not (ablation["qc2_time_pts_abstention"] <= ablation["qc1_asr_lexical"] <= ablation["qc0_mechanical"]):
        raise ValueError("ABLATION_NESTING_FAILED")
    by_ordinal = defaultdict(dict)
    for row in diagnostics:
        by_ordinal[row["ordinal"]][row["fault_type"]] = row
    contrast = {}
    for kind in sorted({r["fault_type"] for r in diagnostics} - {"unchanged_copy"}):
        contrast[kind] = {}
        for level in ("qc0", "qc1", "qc2"):
            pairs = [(cases["unchanged_copy"], cases[kind]) for cases in by_ordinal.values()
                     if "unchanged_copy" in cases and kind in cases]
            eligible = [(base, changed) for base, changed in pairs if base[level]]
            contrast[kind][level] = {"pairs": len(pairs), "baseline_accepted": len(eligible),
                                     "newly_rejected": sum(not changed[level] for _, changed in eligible),
                                     "detection_fraction": sum(not changed[level] for _, changed in eligible) / len(eligible)
                                     if eligible else None}
    prefix_errors = [r["max_shift_equivariance_error_seconds"] for r in prefix
                     if r["max_shift_equivariance_error_seconds"] is not None]
    boundary = [r["max_boundary_delta"] for r in records if r["max_boundary_delta"] is not None]
    sensitivity = {str(t): sum(r["qc1_asr_lexical"] and r["dual_time_coverage"] == 1
                               and r["max_boundary_delta"] is not None and r["max_boundary_delta"] <= t
                               and r["max_nearest_pts_gap"] is not None and r["max_nearest_pts_gap"] <= .1
                               for r in records) for t in (.1, .25, .5)}
    aggregate = {"status": "VERIFIED_AUTOMATED_DIAGNOSTIC",
                 "q1_processed": len(records), "asr_complete": sum(r["asr_status"] == "COMPLETE" for r in records),
                 "source_h_pass": sum(r["source_h"]["all"] for r in records),
                 "q1_original_forced_alignment_pass": sum(r["q1_original_alignment_status"] == "COMPUTED_TEMPORAL_CHECKS_PASS" for r in records),
                 "ablation": ablation, "acoustic_basis": dict(Counter(r["acoustic_basis"] for r in records)),
                 "boundary_max_delta_seconds_median": median(boundary) if boundary else None,
                 "boundary_max_delta_seconds_max": max(boundary) if boundary else None,
                 "q1_descriptive_delta_sensitivity": sensitivity,
                 "unchanged_copy": {level: {"count": sum("unchanged_copy" in cases for cases in by_ordinal.values()),
                                            "rejected": sum(not cases["unchanged_copy"][level] for cases in by_ordinal.values()
                                                            if "unchanged_copy" in cases)}
                                    for level in ("qc0", "qc1", "qc2")},
                 "matched_pair_perturbation_contrast": contrast,
                 "prefix_one_second_silence": {"attempted": len(prefix),
                                                "with_unique_matches": len(prefix_errors),
                                                "median_max_shift_error_seconds": median(prefix_errors) if prefix_errors else None,
                                                "max_shift_error_seconds": max(prefix_errors) if prefix_errors else None},
                 "duration_matched_audio_swap": {"attempted": len(swap),
                                                  "eligible": sum("source_binding_detected" in r for r in swap),
                                                  "source_hash_detected": sum(r.get("source_binding_detected", False) for r in swap)},
                 "natural_alignment_accuracy": None,
                 "limitations": ["No word-level timing truth; this is not alignment accuracy.",
                                 "Source hash detection of swapped audio is a binding check, not ASR recognition.",
                                 "Baseline QC2 acceptance is low; report unchanged-copy rejection with perturbation detection.",
                                 "The 0.10/0.25/0.50 grid is descriptive, not a tuned threshold or risk guarantee."]}
    Path(a.output).write_text(json.dumps(aggregate, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    print(json.dumps({"q1_processed": len(records), "qc2": ablation["qc2_time_pts_abstention"]}))


if __name__ == "__main__":
    main()
