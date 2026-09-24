"""Fail-closed project authorization, separate from CLI options and editable receipts.

The future owner event is verified on the fixed native Codex host. This trusts
the uncompromised local host/account, not arbitrary repository JSON. No event is
created or requested by this module. Test/special access is always rejected.
"""
from __future__ import annotations

import importlib.util
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

from .contracts import ROOT, digest, require

TASK = "S01_FROZEN_BASELINE_EXECUTION"
HOST_THREAD = "01a0d38f-482f-7962-89e3-f26626ae5a01"


class AuthorizationError(PermissionError):
    pass


def _git(root, *args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=root).decode().strip()


def approval_question(binding):
    return ("批准 S01 首轮有限预算正式执行。绑定内容：" +
            json.dumps(binding, sort_keys=True, ensure_ascii=False, separators=(",", ":")) +
            "。本次仅 train 学习、valid 选择；test/附件3/4仍禁止。是否批准上述确切版本？请明确回复“批准”。"
            "本批准信任本机 Codex 宿主会话记录，不等同于密码学签名。")


def verify_native_owner(binding):
    # Reuse the independently reviewed native-event parser and path hardening.
    spec = importlib.util.spec_from_file_location("s00e_host_trust", ROOT / "tools/s00e_approval.py")
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    root = host.native_sessions_root()
    host.reject_redirected_path(root)
    events = []
    for path in sorted(root.rglob(f"*{HOST_THREAD}*.jsonl")):
        host.reject_redirected_path(path)
        require(path.resolve().is_relative_to(root.resolve()), "Unsafe host journal")
        with path.open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        require(rows and rows[0].get("type") == "session_meta" and
                rows[0].get("payload", {}).get("id") == HOST_THREAD and
                rows[0]["payload"].get("originator") == "Codex Desktop", "Wrong native host identity")
        events.extend(rows)
    evidence = host.validate_host_events(events, approval_question(binding))
    evidence["thread_id"] = HOST_THREAD
    return evidence


def require_official_authority(config, *, split, optimizer=False, root=ROOT, output_dir=None, device=None,
                               launch=False):
    if split not in ("train", "valid"):
        raise AuthorizationError("Test and Attachment3/4 are independently quarantined")
    if optimizer and split != "train":
        raise AuthorizationError("Optimizer accepts TRAIN only, never valid")
    if config.get("training_authorized") is not True:
        raise AuthorizationError("S01_TRAINING_AUTHORIZED=false; no official data execution")
    try:
        require(config.get("task_id") == TASK and config.get("protocol_freeze") == "R01-FREEZE-01", "Task/freeze mismatch")
        require(config.get("resource_cap_status") == "OWNER_APPROVED", "Numeric cap is only proposed")
        for key in ("resource_walltime_cap_hours", "per_fit_walltime_cap_hours", "storage_cap_gib"):
            v = config.get(key)
            require(type(v) in (int, float) and 0 < v < float("inf"), "Missing numeric resource limit")
        require(config.get("execution_fit_budget") in (24, 30, 39) and config.get("core_budget") == 39,
                "Unapproved fit-budget expansion")
        require(config.get("retry_training_budget") == 0, "No automatic retry budget")
        require(device == config.get("device") == "cuda", "Execution device differs from measured CUDA proposal")
        require(isinstance(config.get("campaign_id"), str) and 1 <= len(config["campaign_id"]) <= 128,
                "Unique owner-bound campaign required")
        require(output_dir is not None, "Private campaign directory must be owner-bound")
        deadline = datetime.datetime.fromisoformat(config["latest_compute_finish"])
        now = datetime.datetime.now(datetime.timezone.utc)
        require(deadline.tzinfo is not None and now < deadline, "Absolute compute deadline passed")
        if launch:
            require(now + datetime.timedelta(hours=config["resource_walltime_cap_hours"]) <= deadline,
                    "Too late to reserve cap before the paper buffer; obtain a pre-execution reduced plan")
        require(_git(root, "branch", "--show-current") == "codex/mosei-auto", "Wrong branch")
        require(_git(root, "remote", "get-url", "origin") == "https://github.com/BiLiangXin/jingsai.git", "Wrong repository")
        require(not _git(root, "status", "--porcelain"), "Execution requires clean reviewed tree")
        current = json.loads((root / "configs/s01_execution.json").read_text(encoding="utf-8"))
        require(current == config, "Only committed project execution config is accepted")
        state = json.loads((root / "state/LATEST_RESEARCH.json").read_text(encoding="utf-8"))
        require(state.get("s01_training_authorized") is True, "Project authority remains false")
        task = (root / "TASK_SPEC.md").read_text(encoding="utf-8")
        require(f"task_id: {TASK}\n" in task and "s01_training_authorized: true\n" in task,
                "Active project task does not authorize execution")
        freeze = json.loads((root / "docs/research/R01/FREEZE_01.json").read_text(encoding="utf-8"))
        require(freeze["status"] == "FROZEN_FOR_S01_PROTOCOL", "Protocol is not frozen")
        binding = dict(task_id=TASK, protocol_freeze="R01-FREEZE-01", commit=_git(root, "rev-parse", "HEAD"),
                       execution_config_sha256=digest(config), freeze_sha256=digest(freeze),
                       resource_walltime_cap_hours=config["resource_walltime_cap_hours"],
                       per_fit_walltime_cap_hours=config["per_fit_walltime_cap_hours"],
                       frozen_core_budget=39, execution_fit_budget=config["execution_fit_budget"],
                       campaign_id=config["campaign_id"], device=device,
                       private_output_sha256=hashlib.sha256(os.path.normcase(str(Path(output_dir).resolve())).encode()).hexdigest(),
                       latest_compute_finish=config["latest_compute_finish"], training_authorized=True)
        return dict(binding=binding, owner_event=verify_native_owner(binding))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise AuthorizationError("OWNER_EXECUTION_AUTHORIZATION_REQUIRED: " + str(exc)) from exc


def _claims_root():
    spec = importlib.util.spec_from_file_location("s00e_claim_host", ROOT / "tools/s00e_approval.py")
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    parent = host.native_sessions_root().parent
    host.reject_redirected_path(parent)
    root = parent / "mosei_campaign_claims"
    root.mkdir(exist_ok=True)
    host.reject_redirected_path(root)
    return root


def claim_campaign(authorization):
    """A grant permits one launch, including after failure or in another directory.

    This ledger is separate from the native journal; it never creates approval.
    A crash consumes the launch. Recovery requires separate owner authorization
    and preserved attempt evidence, never a silent from-scratch retry.
    """
    binding = authorization["binding"]
    campaign = binding["campaign_id"]
    path = _claims_root() / (digest(["BiLiangXin/jingsai", campaign]) + ".json")
    value = dict(campaign_id=campaign, status="LAUNCH_CONSUMED", binding=binding,
                 owner_event=authorization["owner_event"],
                 claimed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise AuthorizationError("Campaign already launched; no replay, new directory or unapproved retry") from exc
    return path
