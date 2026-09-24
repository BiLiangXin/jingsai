"""Compute a proposed finite resource envelope from real synthetic measurements."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def estimate(profile):
    if profile["status"] != "SYNTHETIC_ONLY_COMPLETED":
        raise ValueError("Completed synthetic resource profile required")
    train_steps, valid_batches = math.ceil(3395 / 32), math.ceil(728 / 32)
    measurements = {r["architecture"]: r for r in profile["samples"] if r["batch_size"] == 32 and r["status"] == "PASS"}
    mask = max(profile["cpu_mask_profile"]["train_batch32_seconds"])
    factor, epoch_overhead, per_fit_io = 3., 10., 600.
    rows = []
    for name, r in measurements.items():
        views = 1 if name.startswith("B-") else 145  # explicit clean plus attempted144
        train_mask = mask if name in ("R0", "R1", "R2", "R1-CAP") else 0.
        raw_epoch = train_steps * (r["step_max_seconds"] + train_mask) + valid_batches * views * r["forward_max_seconds"]
        estimated_seconds = 100 * (factor * raw_epoch + epoch_overhead) + per_fit_io
        fits = 6 if name.startswith("B-") else 3
        rows.append(dict(architecture=name, fits=fits, measured_step_max_seconds=r["step_max_seconds"],
                         measured_forward_max_seconds=r["forward_max_seconds"], validation_views=views,
                         estimated_epoch_upper_seconds=factor * raw_epoch + epoch_overhead,
                         estimated_fit_upper_hours=estimated_seconds / 3600))
    per_fit = math.ceil(max(r["estimated_fit_upper_hours"] for r in rows))
    library_seconds = profile["cpu_mask_profile"]["valid_library_8_samples_seconds"] * 728 / 8 * factor
    total_estimate = sum(r["fits"] * r["estimated_fit_upper_hours"] for r in rows) + library_seconds/3600 + 1.
    # Round upwards to whole 12-hour planning blocks, independent of predictive outcomes.
    total_cap = math.ceil(total_estimate / 12) * 12
    return dict(status="PROPOSED_NUMERIC_RESOURCE_CAP", approved=False,
                measured_scope="SYNTHETIC_ONLY; no official data epoch has been timed",
                aggregate_count_source="docs/S00D_DATA_CONTRACT.md (historical public aggregate; not reopened data)",
                train_count=3395, valid_count=728, batch_size=32, train_steps_per_epoch=train_steps,
                valid_batches_per_view=valid_batches, max_epochs=100, patience=10,
                conservative_runtime_multiplier=factor, additional_cpu_metrics_transfer_seconds_per_epoch=epoch_overhead,
                per_fit_io_checkpoint_allowance_seconds=per_fit_io,
                stage_preprocess_and_reused_baseline_allowance_hours=1.,
                estimated_valid_library_seconds=library_seconds,
                planning_fit_estimates=rows, estimated_total_39_fit_upper_hours=total_estimate,
                resource_walltime_cap_hours=total_cap, per_fit_walltime_cap_hours=per_fit,
                total_39_fit_cap_hours=total_cap, storage_cap_gib=5., gpu_memory_guard_fraction=.8,
                recommended_batch=32, max_tested_safe_batch=profile["max_tested_safe_batch"],
                physical_max_batch="UNKNOWN", official_epoch_seconds=None, official_fit_hours=None,
                oom_boundary=profile["oom_boundary"], official_model_experiments="NOT_RUN", metrics=None,
                limits=["Planning upper estimates are not mathematical or empirical official-runtime bounds.",
                        "Patience may shorten work but no early-stopping discount is used.",
                        "Global cap may stop the campaign before39fits finish; never silently switch to24/30.",
                        "Per-fit cap is a maximum, not expected elapsed time; its39fold sum is not the phase-weighted total estimate.",
                        "Owner must approve numeric caps and training separately. No outcome-based budget change."])


def deadline_estimate(profile, scaled):
    if scaled["status"] != "SYNTHETIC_ONLY_COMPLETED" or not scaled["source_unchanged_during_measurement"]:
        raise ValueError("Source-bound complete synthetic epoch profile required")
    measured = {r["architecture"]: r for r in scaled["samples"]}
    micro = {r["architecture"]: r for r in profile["samples"] if r["batch_size"] == 32 and r["status"] == "PASS"}
    rows = []
    factor = 1.25  # Complete-path dense50 timing plus25% fluctuation margin; separate IO/setup allowances below.
    for name in micro:
        source = measured.get(name, measured["R0"])
        ratio = max(1., micro[name]["step_max_seconds"] / micro["R0"]["step_max_seconds"],
                    micro[name]["forward_max_seconds"] / micro["R0"]["forward_max_seconds"]) if name not in measured else 1.
        epoch = (max(source["train_epoch_seconds"]) + max(source["checkpoint_validation_seconds"])) * ratio
        # 100 epochs without any early-stop discount, extra0.25s checkpoint/epoch,
        # a final restored-checkpoint grid, measured setup and60s additional IO/fit.
        seconds = factor * (100 * (epoch + .25) + source["final_validation_seconds"] * ratio +
                            source["unattributed_fixed_seconds"]) + 60
        rows.append(dict(architecture=name, fits=6 if name.startswith("B-") else 3,
            measurement_basis="DIRECT_SCALED_SYNTHETIC" if name in measured else "INFERRED_FROM_R0_AND_MICRO_RATIO",
            ratio=ratio, measured_or_inferred_epoch_seconds=epoch, estimated_fit_upper_hours=seconds/3600))
    totals = {str(budget): sum(r["fits"] * r["estimated_fit_upper_hours"] for r in rows
             if budget == 39 or r["architecture"].startswith("B-") or (budget == 30 and r["architecture"] in ("C0","R0"))) + .5
              for budget in (24,30,39)}
    caps = {k: math.ceil(v) for k,v in totals.items()}
    return dict(status="PROPOSED_NUMERIC_RESOURCE_CAP", approved=False, evidence="INFERRED_FROM_VERIFIED_SYNTHETIC_TIMING",
        frozen_core_budget=39, execution_fit_budget=30, registered_fits=39,
        train_count=3395, valid_count=728, max_epochs=100, patience=10, early_stop_discount=0,
        multiplier=factor, checkpoint_allowance_seconds_per_epoch=.25, additional_io_seconds_per_fit=60,
        stage_setup_and_reused_baseline_allowance_hours=.5, planning_fit_estimates=rows,
        estimated_total_fit_hours=totals, proposed_total_caps_hours=caps,
        resource_walltime_cap_hours=caps["30"], per_fit_walltime_cap_hours=math.ceil(max(
            r["estimated_fit_upper_hours"] for r in rows if r["architecture"] in ("C0","R0"))),
        total_39_fit_cap_hours=caps["39"], total_39_fit_cap_status="COMPARISON_ONLY_NOT_ACTIVE_WITH_DEADLINE",
        storage_cap_gib=5., gpu_memory_guard_fraction=.8, recommended_batch=32,
        max_tested_safe_batch=profile["max_tested_safe_batch"], physical_max_safe_batch="UNKNOWN",
        oom_boundary=profile["oom_boundary"], paper_submission_deadline="2026-09-27T00:00:00+08:00",
        latest_compute_finish="2026-09-25T18:00:00+08:00", reserved_paper_revision_hours=30,
        official_epoch_seconds=None, official_fit_hours=None, metrics=None, official_model_experiments="NOT_RUN",
        limits=["Planning estimates are not guaranteed official runtime bounds; no official data was timed.",
                "No predictive outcome, early stopping assumption or best-seed discount enters the budget.",
                "30fit proposal defers9temporal/gating fits;39registry records remainNOT_RUN.",
                "If approval arrives too late for the full proposed cap, choose24before any experiment and rebind authority.",
                "Never change budget after seeing results; cap stop preserves all failed/incomplete attempts.",
                "Attempt1's72h proposal is superseded by user deadline and scaled complete-path measurement."])


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--profile", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--scaled", type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Preserve previous resource estimates")
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    result = deadline_estimate(profile, json.loads(args.scaled.read_text(encoding="utf-8"))) if args.scaled else estimate(profile)
    if args.scaled:
        result["source_scaled_profile_sha256"] = hashlib.sha256(args.scaled.read_bytes()).hexdigest()
    result["estimator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["source_profile_sha256"] = hashlib.sha256(args.profile.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("status", "resource_walltime_cap_hours", "per_fit_walltime_cap_hours", "estimated_total_fit_hours")}))
