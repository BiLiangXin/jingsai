"""Explicit user-preauthorized, reviewed, published, one-use S01 campaign.

No native approval journal or CLI grant. Trusts the local OS account/Git
publisher, not a security sandbox against hostile same-account code.
"""
from __future__ import annotations
import ctypes
import datetime
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath
from .contracts import ROOT, digest, require

TASK = "S01_FROZEN_BASELINE_EXECUTION"
MODE = "PREAUTHORIZED_BY_CURRENT_USER_INSTRUCTION"
BASE_COMMIT = "71524473e915412ef823d9ad8dcb5928c4eeb2ca"
INSTRUCTION_SHA256 = "7a7f1835b0f08049453f25227f0faf50ff12f9859ebfe7ccbc3d53f6cb013afd"
SOURCE_SHA256 = "66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd"
CUTOFF = "2026-09-25T18:00:00+08:00"
MANIFEST = "reports/s01_activation/AUTHORIZED_EXECUTION_MANIFEST.json"
AUTH_RECORD = "docs/S01_EXEC_AUTH_01.json"
REVIEW = "reports/s01_activation/independent_review.json"
FROZEN_PATHS = ("docs/research/R01", "research/r01", "src/mosei/data")
CRITICAL = {
    "configs/s01_execution.json", "TASK_SPEC.md", "DECISIONS.md", "state/LATEST_RESEARCH.json",
    "docs/research/R01/FREEZE_01.json", "docs/research/R01/protocol.json", "docs/EXPERIMENT_REGISTER.json",
    AUTH_RECORD, "tools/s01_train.py", "tests/test_s01_preparation.py", "tests/test_s01_activation.py",
} | {"src/mosei/s01/" + n + ".py" for n in
     ("__init__", "authorization", "contracts", "models", "normalization", "protocol", "registry", "engine", "execution")}
_ACTIVE_BINDING = None


class AuthorizationError(PermissionError):
    pass


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _git(root, *args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=root, timeout=30).decode().strip()


def path_digest(path):
    return hashlib.sha256(os.path.normcase(str(Path(path).resolve())).encode()).hexdigest()


def reject_redirected_path(path):
    for p in (Path(path).absolute(), *Path(path).absolute().parents):
        if p.exists():
            require(not p.is_symlink() and not (getattr(p.lstat(), "st_file_attributes", 0) &
                    getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)), "Redirected path rejected")


def select_budget(now):
    require(now.tzinfo is not None, "Timezone-aware selection required")
    remaining = (datetime.datetime.fromisoformat(CUTOFF) - now).total_seconds()
    if remaining >= 12 * 3600:
        return (30, 12, 2)
    if remaining >= 4 * 3600:
        return (24, 4, 1)
    raise AuthorizationError("DEADLINE_BLOCKED: no complete authorized window remains")


def verify_manifest(root, campaign):
    p = root / MANIFEST
    reject_redirected_path(p)
    raw = p.read_bytes()
    value = json.loads(raw)
    require(value["base_commit"] == BASE_COMMIT and value["campaign_id"] == campaign, "Wrong activation manifest")
    rows = value["files"]
    names = [r["path"] for r in rows]
    require(len(names) == len(set(names)) == len({n.casefold() for n in names}), "Duplicate manifest paths")
    require(CRITICAL <= set(names) and MANIFEST not in names and REVIEW not in names,
            "Critical manifest incomplete or self-referential")
    for r in rows:
        rel = r["path"]
        require(not PurePosixPath(rel).is_absolute() and ".." not in PurePosixPath(rel).parts and
                ":" not in rel and "\\" not in rel, "Unsafe manifest path")
        p = root / rel
        reject_redirected_path(p)
        data = p.read_bytes()
        require(len(data) == r["size"] and hashlib.sha256(data).hexdigest() == r["sha256"],
                "Authorized manifest hash/size changed: " + rel)
    p = root / REVIEW
    reject_redirected_path(p)
    review = json.loads(p.read_bytes())
    mh = hashlib.sha256(raw).hexdigest()
    require(review["status"] == "TECHNICAL_PASS" and review["blocking_critical"] == 0 and
            review["blocking_major"] == 0 and review["authorized_manifest_sha256"] == mh,
            "Independent review does not bind this activation manifest")
    return mh


def _claims_root():
    require(os.name == "nt", "Fixed Windows campaign ledger required")
    profile = ctypes.create_unicode_buffer(32768)
    require(ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, profile) == 0, "Native Windows profile unavailable")
    root = Path(profile.value) / ".codex" / "mosei_campaign_claims"
    reject_redirected_path(root)
    root.mkdir(exist_ok=True)
    return root


def claim_path(campaign):
    return _claims_root() / (digest(["BiLiangXin/jingsai", campaign]) + ".json")


def require_official_authority(config, *, split, optimizer=False, root=ROOT, output_dir=None, device=None, launch=False):
    if split not in ("train", "valid"):
        raise AuthorizationError("Test and Attachment3/4 are independently quarantined")
    if optimizer and split != "train":
        raise AuthorizationError("Optimizer accepts TRAIN only, never valid")
    if config.get("training_authorized") is not True:
        raise AuthorizationError("S01_TRAINING_AUTHORIZED=false; no official data execution")
    try:
        require(config.get("task_id") == TASK and config.get("protocol_freeze") == "R01-FREEZE-01", "Task/freeze mismatch")
        require(config.get("status") == "ACTIVE_AUTHORIZED" and config.get("owner_authorization_mode") == MODE and
                config.get("resource_cap_status") == "USER_PREAUTHORIZED", "Explicit campaign preauthorization required")
        actual = (config["execution_fit_budget"], config["resource_walltime_cap_hours"], config["per_fit_walltime_cap_hours"])
        require(actual in ((30, 12, 2), (24, 4, 1)), "Wrong budget or resource cap")
        selected = datetime.datetime.fromisoformat(config["budget_decided_at"])
        require(select_budget(selected) == actual and selected <= _now(), "Budget differs from once-locked pre-execution selection")
        require(config.get("core_budget") == 39 and config.get("retry_training_budget") == 0, "No retry/expansion")
        require(device == config.get("device") == "cuda", "Wrong device; measured CUDA required")
        require(config.get("storage_cap_gib") == 5.0 and config.get("gpu_memory_guard_fraction") == .8, "Resource guards changed")
        require(all(config.get(k) is False for k in ("test_authorized", "attachment3_4_authorized", "q3_authorized")), "Forbidden scope enabled")
        require(config.get("model_seeds") == [17,29,43] and config.get("train_mask_root") == 2207 and
                config.get("valid_mask_root") == 1103 and config.get("nominal_conditions") == 96 and
                config.get("views") == 144 and config.get("random_replicates") == 3, "Frozen protocol metadata changed")
        require(config.get("disabled_blocks") == ["D", "T", "L"], "Optional blocks must stay disabled")
        require(config.get("official_source_sha256") == SOURCE_SHA256, "Configured source fingerprint changed")
        require(config.get("latest_compute_finish") == CUTOFF, "Absolute deadline changed")
        deadline, now = datetime.datetime.fromisoformat(CUTOFF), _now()
        require(now < deadline, "Absolute compute deadline passed")
        if launch:
            require(now + datetime.timedelta(hours=actual[1]) <= deadline, "DEADLINE_BLOCKED: locked window no longer fits")
        require(output_dir is not None, "Bound private output directory required")
        output = Path(output_dir).absolute()
        reject_redirected_path(output)
        require(not output.resolve().is_relative_to(root.resolve()), "Output must be outside public repository")
        require(path_digest(output) == config["private_output_sha256"], "Wrong private output directory")
        campaign = config["campaign_id"]
        require(isinstance(campaign, str) and 8 <= len(campaign) <= 128, "Unique campaign ID required")
        if launch:
            require(not output.exists(), "Use a new private execution directory")
            require(not claim_path(campaign).exists(), "Campaign already claimed; no replay")
        require(_git(root, "branch", "--show-current") == "codex/mosei-auto", "Wrong branch")
        require(_git(root, "remote", "get-url", "origin") == "https://github.com/BiLiangXin/jingsai.git", "Wrong origin")
        require(not _git(root, "status", "--porcelain"), "Dirty tree; reviewed clean state required")
        head = _git(root, "rev-parse", "HEAD")
        remote = _git(root, "ls-remote", "origin", "refs/heads/codex/mosei-auto").split()
        require(len(remote) == 2 and remote[0] == head and remote[1] == "refs/heads/codex/mosei-auto", "Local/remote HEAD mismatch")
        require(json.loads((root / "configs/s01_execution.json").read_bytes()) == config, "Config differs from committed project config")
        require(not _git(root, "diff", "--name-only", BASE_COMMIT, "--", *FROZEN_PATHS), "Frozen files changed")
        contract = lambda text: [s for s in text.splitlines() if s.startswith("| D-DATA-")]
        require(contract(_git(root, "show", BASE_COMMIT + ":DECISIONS.md")) ==
                contract((root / "DECISIONS.md").read_text(encoding="utf-8")), "Data contract changed")
        state = json.loads((root / "state/LATEST_RESEARCH.json").read_bytes())
        require(state.get("s01_training_authorized") is True and state.get("campaign_id") == campaign, "Project campaign not active")
        task = (root / "TASK_SPEC.md").read_text(encoding="utf-8")
        require(f"task_id: {TASK}\n" in task and "s01_training_authorized: true\n" in task and
                "status: ACTIVE_AUTHORIZED\n" in task, "Wrong active task")
        freeze = json.loads((root / "docs/research/R01/FREEZE_01.json").read_bytes())
        require(freeze["status"] == "FROZEN_FOR_S01_PROTOCOL", "Protocol not frozen")
        record = json.loads((root / AUTH_RECORD).read_bytes())
        require(record["authorization_id"] == "S01-EXEC-AUTH-01" and record["source"] == "EXPLICIT_CURRENT_USER_INSTRUCTION" and
                record["instruction_sha256"] == INSTRUCTION_SHA256 and record["mode"] == MODE and
                record["campaign_id"] == campaign and record["selected_budget"] == list(actual) and
                record["budget_decided_at"] == config["budget_decided_at"] and
                record["private_output_sha256"] == config["private_output_sha256"], "Wrong explicit user authorization record")
        mh = verify_manifest(root, campaign)
        binding = dict(task_id=TASK, protocol_freeze="R01-FREEZE-01", commit=head, campaign_id=campaign,
            execution_config_sha256=digest(config), authorized_manifest_sha256=mh, authorization_mode=MODE,
            execution_fit_budget=actual[0], resource_walltime_cap_hours=actual[1], per_fit_walltime_cap_hours=actual[2],
            device=device, private_output_sha256=path_digest(output), latest_compute_finish=CUTOFF)
        if not launch:
            require(_ACTIVE_BINDING == binding, "Official source/fit requires this process's claimed campaign")
            claimed = json.loads(claim_path(campaign).read_bytes())
            require(claimed["binding"] == binding and claimed["pid"] == os.getpid(), "Wrong claimed process/binding")
        return dict(binding=binding, owner_authorization=dict(mode=MODE, authorization_id="S01-EXEC-AUTH-01", instruction_sha256=INSTRUCTION_SHA256))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise AuthorizationError("PREAUTHORIZED_S01_CAMPAIGN_PREFLIGHT_FAILED: " + str(exc)) from exc


def claim_campaign(authorization):
    """Atomic one-use launch. Failure/crash never releases the consumed grant."""
    global _ACTIVE_BINDING
    binding = authorization["binding"]
    require(binding.get("authorization_mode") == MODE, "Preauthorized campaign binding required")
    path = claim_path(binding["campaign_id"])
    reject_redirected_path(path)
    value = dict(status="LAUNCH_CONSUMED", binding=binding, owner_authorization=authorization["owner_authorization"], pid=os.getpid(), claimed_at=_now().isoformat())
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise AuthorizationError("Campaign already launched; no replay, new directory or unapproved retry") from exc
    _ACTIVE_BINDING = binding
    return path
