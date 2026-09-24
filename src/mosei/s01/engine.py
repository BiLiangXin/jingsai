"""Train/evaluate primitives. This task exercises only closed synthetic fixtures."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import torch
from torch.nn import functional as F

from .authorization import require_official_authority
from .contracts import MODS, SEEDS, digest, require, stream_seed
from .models import R01Model, parameter_count
from .normalization import Normalizer
from .protocol import (CheckpointSelector, ValidationLibrary, metric_report, reference,
                       train_availability)


def joint_loss(output, batch):
    batch.validate()
    logits, prediction = output["logits"], output["regression"]
    require(logits.shape == (len(batch.support), 3) and prediction.shape == batch.values.shape,
            "Dual-head output shape")
    require(bool(torch.isfinite(logits).all() & torch.isfinite(prediction).all()), "Nonfinite output")
    require(bool((prediction.abs() <= 3).all()), "Regression range")
    value = F.cross_entropy(logits, batch.classes) + (prediction - batch.values).abs().mean() / 3
    require(bool(torch.isfinite(value)), "Nonfinite joint loss")
    return value


def optimizer_step(model, optimizer, batch, available=None):
    """Internal step; official callers must first pass the project authorization gate."""
    model.train()
    optimizer.zero_grad(set_to_none=True)
    loss = joint_loss(model(batch.inputs(available)), batch)
    loss.backward()
    for p in model.parameters():
        require(p.grad is None or bool(torch.isfinite(p.grad).all()), "Nonfinite gradient")
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
    optimizer.step()
    require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), "Nonfinite parameter")
    return float(loss.detach())


@torch.no_grad()
def predict(model, batch, *, batch_size=32, available=None, indices=None, deadline=None):
    model.eval()
    device = next(model.parameters(), model.prior).device
    indices = list(range(len(batch.support))) if indices is None else list(indices)
    classes, values = [], []
    for start in range(0, len(indices), batch_size):
        if deadline is not None:
            require(time.monotonic() < deadline, "Resource wall-time cap reached during validation")
        ix = indices[start:start + batch_size]
        part = batch.take(ix).to(device)
        active = None if available is None else {m: available[m][ix].to(device) for m in MODS}
        output = model(part.inputs(active))
        classes.append(output["logits"].argmax(1).cpu())
        values.append(output["regression"].cpu())
    if not indices:
        return torch.empty(0, dtype=torch.long), torch.empty(0)
    return torch.cat(classes), torch.cat(values)


def evaluate(model, batch, *, seed, library=None, batch_size=32, deadline=None):
    clean_c, clean_y = predict(model, batch, batch_size=batch_size, deadline=deadline)
    result = dict(clean=metric_report(batch, clean_c, clean_y))
    if library is None:
        return result
    library.validate_population(batch)
    reports = {}
    classes, y = batch.classes.cpu().tolist(), batch.values.cpu().tolist()
    for cid, views in library.views.items():
        reports[cid] = []
        for view in views:
            eligible = view["eligible"]
            indices = [i for i, yes in enumerate(eligible) if yes]
            c, v = predict(model, batch, available=view["available"], indices=indices,
                           batch_size=batch_size, deadline=deadline)
            damaged_c, damaged_y = [None] * len(classes), [None] * len(classes)
            for i, pc, py in zip(indices, c.tolist(), v.tolist()):
                damaged_c[i], damaged_y[i] = pc, py
            # INELIGIBLE never enters an extra forward or optimizer: use cached clean exactly once.
            reports[cid].append(reference.attempted_report(
                classes, y, clean_c.tolist(), clean_y.tolist(), damaged_c, damaged_y, eligible,
                ordered_rows=batch.ordinals, view_fingerprint=view["fingerprint"], replicate=view["replicate"]))
    result.update(attempted96=reference.checkpoint_score(reports, seed), condition_reports=reports)
    return result


def save_checkpoint(path, model, optimizer, normalizer, *, epoch, trace, config, provenance):
    payload = dict(format_version=1, architecture=model.architecture, seed=model.seed, epoch=epoch,
                   model=model.state_dict(), optimizer=optimizer.state_dict(), normalizer=normalizer.state_dict(),
                   selector_trace=list(trace), config_hash=digest(config), provenance=provenance,
                   torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [])
    torch.save(payload, path)


def load_checkpoint(path, model, optimizer, *, config, provenance):
    payload = torch.load(path, map_location="cpu", weights_only=True)
    require(payload["format_version"] == 1 and payload["config_hash"] == digest(config), "Checkpoint config mismatch")
    require(payload["architecture"] == model.architecture and payload["seed"] == model.seed, "Checkpoint identity mismatch")
    require(payload["provenance"] == provenance, "Checkpoint source/data provenance mismatch")
    require(0 <= payload["epoch"] <= 100 and len(payload["selector_trace"]) == payload["epoch"], "Checkpoint epoch/trace")
    model.load_state_dict(payload["model"], strict=True)
    optimizer.load_state_dict(payload["optimizer"])
    torch.set_rng_state(payload["torch_rng"])
    if payload["cuda_rng"] and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(payload["cuda_rng"])
    payload["restored_normalizer"] = Normalizer.from_state_dict(payload["normalizer"])
    return payload


def validate_recipe(config):
    expected = dict(recipe="T0", hidden=64, batch_size=32, lr=.001, weight_decay=.0001,
                    dropout=0., clip_norm=1., loss="CE+MAE/3", max_epochs=100,
                    patience=10, min_delta_F=.0001, min_delta_MAE=.0001)
    expected.update(train_mask_root=2207, valid_mask_root=1103, protocol_freeze="R01-FREEZE-01")
    require(all(config.get(k) == v for k, v in expected.items()), "Frozen T0 recipe changed")
    require(config.get("seed") in SEEDS, "Seed outside frozen protocol")
    require(config.get("normalizer") in ("identity", "zscore"), "Resolve common normalizer before fit")
    require(config.get("architecture") in ("B-T", "B-A", "B-V", "B-CAT", "C0", "R0", "R1", "R2", "R1-CAP"),
            "Excluded block/architecture")
    objective = "clean" if config["architecture"].startswith("B-") else "attempted96"
    require(config.get("checkpoint_objective") == objective, "Wrong checkpoint objective")


def fit(train, valid, normalizer, config, *, output_dir, provenance, data_kind,
        execution_config=None, device="cpu", synthetic_epochs=1, library=None, resume=None,
        total_deadline=None):
    if data_kind != "SYNTHETIC_ONLY":
        require(data_kind == "OFFICIAL_TRAIN_VALID", "Unknown data origin")
        require_official_authority(execution_config or {}, split="train", optimizer=True,
                                   output_dir=Path(output_dir).parent, device=device)
        require_official_authority(execution_config or {}, split="valid",
                                   output_dir=Path(output_dir).parent, device=device)
    validate_recipe(config)
    require(normalizer.method == config["normalizer"], "Normalizer/config mismatch")
    train.validate(); valid.validate()
    require(normalizer.fit_split == "train", "Train-fitted normalizer required")
    epochs = 100
    if data_kind == "SYNTHETIC_ONLY":
        require(type(synthetic_epochs) is int and 1 <= synthetic_epochs <= 2, "Synthetic dry-run limited to two epochs")
        epochs = synthetic_epochs
    destination = Path(output_dir)
    if resume is None:
        require(not destination.exists(), "Never overwrite a prior fit/attempt")
        destination.mkdir(parents=True)
    else:
        require(destination.is_dir(), "Resume requires existing attempt directory")
    train, valid = normalizer.transform(train), normalizer.transform(valid)
    if config["checkpoint_objective"] == "attempted96":
        library = library or ValidationLibrary(valid)
    checkpoint_library = library if config["checkpoint_objective"] == "attempted96" else None
    from .models import prior_statistics
    prior, median = prior_statistics(train, split="train")
    model = R01Model(config["architecture"], config["seed"], prior=prior, median=median).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    selector = CheckpointSelector()
    start_epoch = 0
    if resume:
        saved = load_checkpoint(resume, model, optimizer, config=config, provenance=provenance)
        require(saved["normalizer"] == normalizer.state_dict(), "Resume normalizer mismatch")
        selector.trace = saved["selector_trace"]
        start_epoch = saved["epoch"]
        if selector.trace:
            require(reference.choose_checkpoint(selector.trace)["stop_epoch"] is None, "Already early-stopped")
    deadline = total_deadline
    if data_kind == "OFFICIAL_TRAIN_VALID":
        per_fit = time.monotonic() + execution_config["per_fit_walltime_cap_hours"] * 3600
        deadline = min(per_fit, deadline) if deadline is not None else per_fit
    timing = dict(train_epoch_seconds=[], checkpoint_validation_seconds=[], final_validation_seconds=None)
    for epoch in range(start_epoch, epochs):
        epoch_started = time.perf_counter()
        order = torch.randperm(len(train.support), generator=torch.Generator().manual_seed(
            stream_seed(config["seed"], f"data-order:{epoch}"))).tolist()
        for start in range(0, len(order), 32):
            if deadline is not None:
                require(time.monotonic() < deadline, "Resource wall-time cap reached")
            if data_kind == "OFFICIAL_TRAIN_VALID" and str(device).startswith("cuda"):
                free, total = torch.cuda.mem_get_info()
                require(total - free < total * execution_config["gpu_memory_guard_fraction"],
                        "GPU global memory guard reached")
            part = train.take(order[start:start + 32]).to(device)
            active = train_availability(part, config["seed"], epoch)[0] if config["architecture"] in ("R0", "R1", "R2", "R1-CAP") else None
            optimizer_step(model, optimizer, part, active)
        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
        timing["train_epoch_seconds"].append(time.perf_counter() - epoch_started)
        validation_started = time.perf_counter()
        scores = evaluate(model, valid, seed=config["seed"], library=checkpoint_library,
                          batch_size=32, deadline=deadline)
        timing["checkpoint_validation_seconds"].append(time.perf_counter() - validation_started)
        objective = scores[config["checkpoint_objective"]]
        decision = selector.update(objective["macro_F1"], objective["MAE"])
        if decision["save"]:
            save_checkpoint(destination / "best.pt", model, optimizer, normalizer, epoch=epoch+1,
                            trace=selector.trace, config=config, provenance=provenance)
        save_checkpoint(destination / "last.pt", model, optimizer, normalizer, epoch=epoch+1,
                        trace=selector.trace, config=config, provenance=provenance)
        if data_kind == "OFFICIAL_TRAIN_VALID":
            used = sum(p.stat().st_size for p in destination.parent.rglob("*") if p.is_file())
            require(used < execution_config["storage_cap_gib"] * 2**30, "Storage cap reached")
        if decision["stop"]:
            break
    require((destination / "best.pt").is_file(), "No selected checkpoint")
    saved = load_checkpoint(destination / "best.pt", model, optimizer, config=config, provenance=provenance)
    validation_started = time.perf_counter()
    result = evaluate(model, valid, seed=config["seed"], library=library, batch_size=32, deadline=deadline)
    timing["final_validation_seconds"] = time.perf_counter() - validation_started
    result.update(parameters=parameter_count(model), selected_epoch=saved["epoch"],
                  evaluated_epochs=len(selector.trace), checkpoint=str(destination / "best.pt"), timing=timing)
    return model, result
