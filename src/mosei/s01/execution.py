"""Future official finite scheduler. Authority is checked before any source read."""
from __future__ import annotations

import hashlib
import datetime
import json
import os
import subprocess
import time
from pathlib import Path

import torch

from .authorization import claim_campaign, require_official_authority
from .contracts import ROOT, MODS, SEEDS, digest, from_aligned, require
from .engine import evaluate, fit
from .models import LateModel, PriorModel, parameter_count, prior_statistics
from .normalization import Normalizer
from .protocol import ValidationLibrary, final_choice, reference, select_normalizer, summarize_configuration
from .registry import EventRegistry, validate_preregistration


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def load_official(config, source, *, output_dir=None, device=None):
    require_official_authority(config, split="train", optimizer=True, output_dir=output_dir, device=device)
    require_official_authority(config, split="valid", output_dir=output_dir, device=device)
    path = Path(source)
    require(path.name == "aligned_50.pkl", "Only the frozen aligned source is accepted")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    require(h.hexdigest() == config["official_source_sha256"], "Official source fingerprint changed")
    # Trusted competition pickle only, reachable exclusively after verified owner authority.
    import pickle
    from mosei.data.dataset import create_aligned_dataset
    with path.open("rb") as stream:
        container = pickle.load(stream)
    datasets = {split: create_aligned_dataset(container, split) for split in ("train", "valid")}
    batches = {split: from_aligned(data.batch(list(range(len(data)))), list(range(len(data))))
               for split, data in datasets.items()}
    return batches, h.hexdigest()


def execute_core(config, source, output_dir, *, device="cuda"):
    authorization = require_official_authority(config, split="train", optimizer=True,
                                              output_dir=output_dir, device=device, launch=True)
    require(config["core_budget"] == 39 and config["retry_training_budget"] == 0, "Only frozen core; no retry expansion")
    require(config["disabled_blocks"] == ["D", "T", "L"], "Optional blocks must stay disabled")
    require(0 < config["gpu_memory_guard_fraction"] < 1, "Memory guard fraction")
    output = Path(output_dir).resolve()
    require(not output.exists(), "Use a new private execution directory")
    require(not output.is_relative_to(ROOT.resolve()), "Official artifacts must remain outside the public repository")
    registry = json.loads((ROOT / "docs/EXPERIMENT_REGISTER.json").read_text(encoding="utf-8"))["s01_preregistered_fits"]
    validate_preregistration(registry)
    require(config["execution_fit_budget"] in (24, 30, 39), "Frozen resource downgrade only")
    claim_campaign(authorization)
    output.mkdir(parents=True)
    events = EventRegistry(output / "events.jsonl", registry)
    write_json(output / "campaign.json", dict(authorization=authorization,
        execution_fit_budget=config["execution_fit_budget"], preregistered=registry,
        deferred_trial_ids=[t["trial_id"] for t in registry[config["execution_fit_budget"]:]]))
    # The total clock includes source hashing, preprocessing and validation-library construction.
    remaining = (datetime.datetime.fromisoformat(config["latest_compute_finish"]) -
                 datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    deadline = time.monotonic() + min(config["resource_walltime_cap_hours"] * 3600, remaining)
    data, source_hash = load_official(config, source, output_dir=output, device=device)
    train, valid = data["train"], data["valid"]
    prior, median = prior_statistics(train, split="train")
    provenance = dict(code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
                      source_sha256=source_hash, execution_config_hash=digest(config), protocol_freeze="R01-FREEZE-01")
    normalizers = {name: Normalizer(name).fit([train], split="train") for name in ("identity", "zscore")}
    library = ValidationLibrary(valid)
    records, models = {}, {}
    common = None
    base_id = None
    baseline_records = {}
    def lock_baselines():
            nonlocal common, baseline_records, base_id
            common = select_normalizer({name: {s: records[f"B-CAT-{name}"][s]["clean"] for s in SEEDS}
                                        for name in normalizers})
            # PRIOR and LATE have zero additional fits; B* is sealed before C0.
            baseline_records = {key: records[key] for key in records}
            for name, normalizer in normalizers.items():
                normalized = normalizer.transform(valid)
                late_id = "LATE-" + name
                baseline_records[late_id] = {}
                for seed in SEEDS:
                    late = LateModel({m: models[("B-" + short, name, seed)]
                                      for m, short in zip(MODS, ("T", "A", "V"))}, prior, median).to(device)
                    scores = evaluate(late, normalized, seed=seed, deadline=deadline)
                    scores["parameters"] = parameter_count(late)
                    baseline_records[late_id][seed] = scores
                    late.cpu()
            prior_model = PriorModel(prior, median).to(device)
            prior_scores = evaluate(prior_model, valid, seed=17, deadline=deadline)
            prior_scores["parameters"] = 0
            baseline_records["PRIOR"] = {s: prior_scores for s in SEEDS}
            ordered = reference.rank_configs([summarize_configuration(cid, rows, objective="clean")
                                               for cid, rows in baseline_records.items()])
            base_id = ordered[0]["id"]
            write_json(output / "baseline_lock.json", dict(common_normalizer=common, B_star=base_id,
                provenance=provenance))
    for t in registry[:config["execution_fit_budget"]]:
        if t["block"] != "B" and common is None:
            lock_baselines()
        trial = dict(t["config"])
        if trial["normalizer"] == "common_preselected":
            trial["normalizer"] = common
        trial_id = t["trial_id"]
        events.event(trial_id, "RUNNING", config_hash=digest(trial), code_commit=provenance["code_commit"], metrics=None)
        try:
            require(time.monotonic() < deadline, "Total wall-time cap reached")
            model, result = fit(train, valid, normalizers[trial["normalizer"]], trial,
                                output_dir=output / trial_id, provenance=provenance, data_kind="OFFICIAL_TRAIN_VALID",
                                execution_config=config, device=device, library=library, total_deadline=deadline)
            cid = trial["architecture"] + "-" + trial["normalizer"]
            # Persist the evidence before its durable COMPLETED event.
            write_json(output / trial_id / "evaluation.json", result)
            records.setdefault(cid, {})[trial["seed"]] = result
            models[(trial["architecture"], trial["normalizer"], trial["seed"])] = model.cpu()
            events.event(trial_id, "COMPLETED", checkpoint=result["checkpoint"],
                         metrics={k: result[k] for k in ("clean", "attempted96") if k in result})
        except Exception as exc:
            status = "RESOURCE_CAP_STOP" if "cap reached" in str(exc) or "guard reached" in str(exc) else "FAILED"
            try:
                events.event(trial_id, status, failure_reason=type(exc).__name__ + ": " + str(exc), metrics=None)
            except Exception as log_error:
                exc.add_note("Failure logging also failed: " + repr(log_error))
            raise
    if common is None:
        lock_baselines()
    mechanism = {cid: rows for cid, rows in records.items() if not cid.startswith("B-")}
    decision = final_choice({base_id: baseline_records[base_id], **mechanism}, base_id)
    write_json(output / "selection.json", dict(decision=decision, common_normalizer=common,
        B_star=base_id, provenance=provenance, executed_budget=config["execution_fit_budget"]))
    return decision
