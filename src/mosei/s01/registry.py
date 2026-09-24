"""Finite preregistration and append-only private execution events."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from .contracts import ROOT, SEEDS, digest, require


def recipe(architecture, normalizer, seed):
    return dict(architecture=architecture, normalizer=normalizer, seed=seed, recipe="T0", hidden=64,
                batch_size=32, lr=.001, weight_decay=.0001, dropout=0., clip_norm=1., loss="CE+MAE/3",
                max_epochs=100, patience=10, min_delta_F=.0001, min_delta_MAE=.0001,
                checkpoint_objective="clean" if architecture.startswith("B-") else "attempted96",
                train_mask_root=2207, valid_mask_root=1103, protocol_freeze="R01-FREEZE-01")


def preregister():
    frozen = json.loads((ROOT / "docs/research/R01/trials.json").read_text(encoding="utf-8"))
    records = []
    for t in frozen["trials"]:
        if t["protocol_status"] != "FROZEN_FOR_S01_PROTOCOL":
            continue
        config = recipe(t["architecture"], t["normalizer"], t["seed"])
        records.append(dict(trial_id=t["trial_id"], architecture=t["architecture"], block=t["block"],
                            normalizer=t["normalizer"], recipe="T0", seed=t["seed"], config=config,
                            config_hash=digest(config), config_hash_kind="CANONICAL_PREREGISTERED_TEMPLATE",
                            resolved_config_hash=None, code_commit=None,
                            code_commit_binding="Exact clean authorized HEAD assigned at execution; not the earlier design commit",
                            data_contract="D-DATA-01..07 FROZEN_FOR_BASELINE",
                            train_mask_root=2207, valid_mask_root=1103, status="NOT_RUN",
                            started_at=None, finished_at=None, checkpoint=None, metrics=None,
                            failure_reason=None, retry_count=0, training_authorized=False))
    validate_preregistration(records)
    return records


def validate_preregistration(records):
    require(len(records) == 39 and len({r["trial_id"] for r in records}) == 39, "Exactly 39 unique fits")
    expected = {(a, n, s) for a in ("B-T", "B-A", "B-V", "B-CAT")
                for n in ("identity", "zscore") for s in SEEDS}
    expected |= {(a, "common_preselected", s) for a in ("C0", "R0", "R1", "R2", "R1-CAP") for s in SEEDS}
    require({(r["architecture"], r["normalizer"], r["seed"]) for r in records} == expected,
            "Frozen core population differs; optional blocks rejected")
    for r in records:
        require(r["config"] == recipe(r["architecture"], r["normalizer"], r["seed"]), "Unexpected trial recipe")
        require(r["config_hash"] == digest(r["config"]), "Preregistered config hash mismatch")
        require(r["status"] == "NOT_RUN" and r["metrics"] is None and r["training_authorized"] is False,
                "Prerequisite registry cannot claim execution")


class EventRegistry:
    """Keep failures and cap stops. No retry budget or overwrite of previous attempts."""
    def __init__(self, path, records):
        validate_preregistration(records)
        self.path = Path(path)
        require(not self.path.exists(), "Prior execution log cannot be overwritten")
        self.allowed = {r["trial_id"] for r in records}
        self.states = {key: "NOT_RUN" for key in self.allowed}
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, trial_id, status, **details):
        require(trial_id in self.allowed, "Unregistered fit")
        previous = self.states[trial_id]
        require((previous, status) in (("NOT_RUN", "RUNNING"), ("RUNNING", "COMPLETED"),
                                      ("RUNNING", "FAILED"), ("RUNNING", "RESOURCE_CAP_STOP")),
                "Invalid transition or unauthorized retry")
        row = dict(trial_id=trial_id, previous_status=previous, status=status,
                   timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(), retry_count=0, **details)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.states[trial_id] = status
