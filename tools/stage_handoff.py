"""Fail-closed publication of an already authorized and accepted stage.

One invocation performs the public-file scan, exact Git staging, ordinary
commits/pushes, Review Release verification, and stable latest-run indexing.
It does not run a research stage or infer authorization from the presence of
outputs. The stage runner supplies an exact-file HANDOFF_INPUTS.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import uuid
import zipfile
import hashlib
import tomllib
from pathlib import Path, PurePosixPath

from mosei_flow import forbidden_path, make_review_zip, scan_text, sha256, write_json
from s00e_evidence import EvidenceError, validate_tests as validate_s00e_tests

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "codex/mosei-auto"
ORIGIN = "https://github.com/BiLiangXin/jingsai.git"
STAGE = re.compile(r"S\d{2}[A-Z]?\Z")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{4,100}\Z")
RAW_ID = re.compile(r"(?<![\w])[-_A-Za-z0-9]{5,}\$_\$\d+\b")
FORBIDDEN_JSON_KEYS = {"sample_ids", "raw_ids", "raw_text_dump", "token_ids_dump", "sample_level_labels", "test_label_distribution"}
TEST_DISTRIBUTION_KEYS = {"distribution", "histogram", "class_counts", "negative_count", "neutral_count", "positive_count", "mean", "std", "quantiles", "sample_labels"}
PRIOR_S00E_RUNS = {"20260924-063758-S00E-078028f", "20260924-233200-S00E-D2-4bd0c6c", "20260925-005000-S00E-ASTRA-d9e4edb", "20260925-005500-S00E-ASTRA-d9e4edb", "20260925-014500-S00E-ASTRA-d9e4edb"}
PUBLIC_SUFFIXES = {".md", ".json", ".csv", ".py", ".toml", ".yaml", ".yml"}
S00E_GATE_IDS = {f"E{number:02d}" for number in range(1, 22)}
PROTECTED_DIRS = {"private", "artifacts", "credentials", "tokens", ".private", ".secrets"}
SAMPLE_KEYS = {"id", "sample_id", "video_id", "clip_id", "sample_ids", "raw_ids",
               "label", "labels", "classification_label", "classification_labels",
               "regression_label", "regression_labels", "raw_text", "token_ids",
               "token_ids_dump"}
CREDENTIAL_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey",
                   "access_token", "private_key", "client_secret"}


class HandoffError(RuntimeError):
    pass


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode:
        raise HandoffError(f"Command failed ({result.returncode}): {args[0]} {args[1] if len(args) > 1 else ''}: {result.stderr.strip()}")
    return result


def git(*args: str, check: bool = True) -> str:
    return command("git", *args, check=check).stdout.strip()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HandoffError(f"Expected JSON object: {path.name}")
    return value


def spec_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*([^\r\n]+)", text)
    return match.group(1).strip().strip("`").strip("'").strip(chr(34)) if match else None


def verify_workspace() -> str:
    if not (ROOT / ".git").is_dir():
        raise HandoffError("Use the verified official clone, not a linked worktree")
    if Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT.resolve():
        raise HandoffError("Repository root mismatch")
    if git("config", "--local", "--get", "mosei.officialWorkspace", check=False).lower() != "true":
        raise HandoffError("Official workspace marker missing; verify clone, then set local mosei.officialWorkspace=true")
    if git("remote", "get-url", "origin") != ORIGIN or git("branch", "--show-current") != BRANCH:
        raise HandoffError("Wrong origin or branch")
    local = git("rev-parse", "HEAD")
    remote = git("ls-remote", "--heads", "origin", BRANCH).split()
    if not remote or remote[0] != local:
        raise HandoffError("Remote HEAD differs; synchronize safely before publication")
    if git("diff", "--cached", "--name-only"):
        raise HandoffError("Pre-existing staged changes must be reviewed separately")
    if command("gh", "auth", "status", check=False).returncode:
        raise HandoffError("GitHub CLI authentication unavailable")
    return local


def public_path(relative: str, run_id: str, stage: str, root: Path = ROOT) -> Path:
    if not isinstance(relative, str) or "\\" in relative or not relative or relative.startswith("/"):
        raise HandoffError("Public path must be a relative POSIX path")
    parts = PurePosixPath(relative).parts
    if ".." in parts or "." in parts or (len(parts) < 2 and relative not in {"CHATGPT_REVIEW.md", "README_CODEX.md", "AGENTS.md", "DECISIONS.md", "TASK_SPEC.md", "README.md"}):
        raise HandoffError(f"Unsafe public path: {relative}")
    if forbidden_path(relative) or {x.lower() for x in parts} & {"private", "artifacts"} or PurePosixPath(relative).suffix.lower() not in PUBLIC_SUFFIXES:
        raise HandoffError(f"Forbidden public path: {relative}")
    allowed = (
        relative == "CHATGPT_REVIEW.md"
        or relative == "README_CODEX.md"
        or relative in {"AGENTS.md", "DECISIONS.md", "TASK_SPEC.md", "README.md"}
        or relative == "state/NEXT_ACTIONS.md"
        or relative.startswith("docs/")
        or relative.startswith("src/mosei/")
        or relative.startswith("tests/")
        or relative.startswith("tools/")
        or relative.startswith("configs/")
        or relative.startswith(f"reports/runs/{run_id}/")
        or (stage == "S00E" and any(relative == f"reports/runs/{prior}/{leaf}"
            for prior in PRIOR_S00E_RUNS for leaf in ("RUN.json", "GATE.json", "TEST_RESULTS.json", "public/HANDOFF_INPUTS.json")))
        or relative.startswith(f"reports/stages/{stage}/")
        or relative.startswith("reports/data_audit/")
        or relative.startswith("reports/data_contract/")
        or (stage == "S00E" and relative.startswith("reports/engineering/s00e_"))
        or relative.startswith("reports/experiments/")
    )
    if not allowed:
        raise HandoffError(f"Path outside publication allowlist: {relative}")
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise HandoffError(f"Missing, linked, or escaping public file: {relative}")
    return path


def scan_json(value: object, in_test: bool = False) -> list[str]:
    findings = []
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        identity = keys & {"id", "sample_id", "video_id", "clip_id"}
        payload = keys & {"label", "classification_label", "regression_label", "labels", "classification_labels", "regression_labels", "raw_text", "token_ids"}
        scalar_identity = any(str(key).lower() in identity and type(item) in {str, int, float}
                              for key, item in value.items())
        scalar_payload = any(str(key).lower() in payload and type(item) in {str, int, float}
                             for key, item in value.items())
        if (scalar_identity and scalar_payload) or isinstance(value.get("raw_text"), str):
            findings.append("sample_level_record")
        for key, item in value.items():
            lower = str(key).lower()
            if lower in FORBIDDEN_JSON_KEYS:
                findings.append(f"forbidden_json_key:{key}")
            if in_test and lower in TEST_DISTRIBUTION_KEYS:
                findings.append(f"test_distribution_key:{key}")
            if lower == "raw_text" and isinstance(item, str):
                findings.append("sample_level_record")
            if lower == "raw_text" and isinstance(item, list):
                findings.append("raw_text_array")
            if lower in {"labels", "classification_labels", "regression_labels"} and isinstance(item, list):
                findings.append("sample_level_label_array")
            if lower in CREDENTIAL_KEYS:
                findings.append(f"credential_key:{key}")
            if lower in {"records", "samples", "rows"} and isinstance(item, list):
                for record in item:
                    if isinstance(record, dict):
                        record_keys = {str(k).lower() for k in record}
                        if record_keys & SAMPLE_KEYS:
                            findings.append("sample_level_record")
            findings.extend(scan_json(item, in_test or lower == "test" or lower.startswith("test_") or lower.endswith("_test")))
    elif isinstance(value, list):
        # A top-level JSON array is a common records export.  Gate items with
        # an E01-style identifier alone are not sample records.
        for item in value:
            if isinstance(item, dict):
                keys = {str(key).lower() for key in item}
                if keys & (SAMPLE_KEYS - {"id", "sample_id", "video_id", "clip_id"}):
                    findings.append("sample_level_record")
        for item in value:
            findings.extend(scan_json(item, in_test))
    return findings


def scan_public_bytes(relative: str, data: bytes) -> list[str]:
    """Apply the same public-content policy to a worktree file or Git index blob."""
    path_parts = {part.lower() for part in PurePosixPath(relative).parts}
    if forbidden_path(relative) or path_parts & PROTECTED_DIRS:
        return ["forbidden_path"]
    if len(data) > 1024 * 1024:
        return ["oversize"]
    try:
        content = data.decode("utf-8")
    except UnicodeError:
        return ["binary_or_unknown"]
    issues = scan_text(content)
    if RAW_ID.search(content):
        issues.append("raw_sample_id")
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix == ".json":
        try:
            def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate structured key")
                    result[key] = value
                return result
            issues.extend(scan_json(json.loads(content, object_pairs_hook=unique_pairs)))
        except (json.JSONDecodeError, ValueError, RecursionError):
            issues.append("invalid_json")
    elif suffix == ".csv":
        header = next(csv.reader(content.lstrip("\ufeff").splitlines(), skipinitialspace=True), [])
        if {x.strip().lower() for x in header} & SAMPLE_KEYS:
            issues.append("sample_level_csv_columns")
    elif suffix == ".md":
        # Current Markdown must not re-publish a table pooling the locked test labels.
        if re.search(r"(?im)^\|[^\n]*?(?:label\.xlsx|test)[^\n]*?\|(?:[^\n]*?\d+\s*\|){3,}", content) and re.search(
                r"(?im)^\|[^\n]*(?:正向|中性|负向|negative|neutral|positive)[^\n]*\|", content):
            issues.append("test_bearing_label_distribution_table")
        if re.search(r"(?im)^\|[^\n]*?test[^\n]*?\|(?:\s*\d+(?:\.\d+)?\s*\|){3,}", content):
            issues.append("test_distribution_table")
    elif suffix in {".yaml", ".yml", ".toml"}:
        try:
            if suffix == ".toml":
                parsed = tomllib.loads(content)
            else:
                import yaml
                class UniqueSafeLoader(yaml.SafeLoader):
                    pass

                def unique_mapping(loader, node):
                    loader.flatten_mapping(node)
                    result = {}
                    for key_node, value_node in node.value:
                        key = loader.construct_object(key_node, deep=True)
                        if key in result:
                            raise ValueError("duplicate structured key")
                        result[key] = loader.construct_object(value_node, deep=True)
                    return result

                UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
                parsed = yaml.load(content, Loader=UniqueSafeLoader)
            structured = scan_json(parsed)
            issues.extend(structured)
            if any("sample" in x or "raw_text" in x for x in structured):
                issues.append("sample_level_array")
        except (ImportError, ValueError, RecursionError):
            issues.append("unparseable_structured_text")
        except Exception:
            # Unknown YAML tags and parser failures fail closed without logging content.
            issues.append("unparseable_structured_text")
    return sorted(set(issues))


def scan_public(path: Path) -> list[str]:
    if path.is_symlink():
        return ["linked_path"]
    return scan_public_bytes(path.as_posix(), path.read_bytes())


def scan_tracked_public_tree(root: Path = ROOT) -> dict:
    """Inspect the resulting Git index and worktree, including unlisted tracked text."""
    listing = subprocess.run(["git", "ls-files", "--cached", "-z"], cwd=root, capture_output=True)
    if listing.returncode:
        raise HandoffError("Cannot enumerate tracked Git index paths")
    names = [part.decode("utf-8") for part in listing.stdout.split(b"\0") if part]
    if len(names) != len(set(names)):
        raise HandoffError("Duplicate or unmerged Git index paths")
    findings: dict[str, list[str]] = {}
    scanned = 0
    for name in names:
        relative = PurePosixPath(name)
        if forbidden_path(name) or {x.lower() for x in relative.parts} & PROTECTED_DIRS or relative.is_absolute() or ".." in relative.parts:
            findings[name] = ["forbidden_tracked_path"]
            continue
        if relative.suffix.lower() not in PUBLIC_SUFFIXES:
            continue
        scanned += 1
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            findings[name] = ["missing_linked_or_escaping_worktree_file"]
            continue
        worktree_issues = scan_public_bytes(name, path.read_bytes())
        staged_blob = subprocess.run(["git", "show", f":{name}"], cwd=root, capture_output=True)
        if staged_blob.returncode:
            findings[name] = ["unreadable_index_blob"]
            continue
        index_issues = scan_public_bytes(name, staged_blob.stdout)
        if worktree_issues or index_issues:
            findings[name] = sorted(set(worktree_issues + index_issues))
    return {"scanned_text_files": scanned, "findings": findings}


def _acceptance_map(path: Path, stage: str, task_id: str, run_id: str, root: Path) -> dict[str, str]:
    validate_acceptance(path, stage, task_id=task_id, run_id=run_id, root=root)
    value = load_json(path)
    return {item["path"]: item["sha256"] for item in value["evidence"]}


def _validate_evidence_path(relative: str, *, root: Path, run_id: str,
                            stage: str, acceptance: dict[str, str]) -> None:
    if not isinstance(relative, str) or not relative:
        raise HandoffError("Gate evidence path must be a nonempty string")
    path = public_path(relative, run_id, stage, root)
    if relative not in acceptance or sha256(path) != acceptance[relative]:
        raise HandoffError(f"Gate evidence is not acceptance-bound: {relative}")


def _validate_e19_review(evidence: list[str], *, root: Path, run_id: str,
                         task_id: str, acceptance: dict[str, str]) -> None:
    candidates = [x for x in evidence if "phase_d_review" in x.lower() or "phase-d-review" in x.lower()]
    if len(candidates) != 1:
        raise HandoffError("E19 requires exactly one independent PHASE_D_REVIEW evidence file")
    path = public_path(candidates[0], run_id, "S00E", root)
    if path.suffix.lower() != ".json":
        raise HandoffError("E19 review evidence must be structured JSON")
    value = load_json(path)
    if (value.get("task_id") != task_id or value.get("stage") != "S00E" or
            value.get("run_id") != run_id or
            value.get("phase") != "D" or value.get("status") != "PASS" or
            type(value.get("blocking_issues")) is not int or value["blocking_issues"] != 0 or
            type(value.get("critical_issues")) is not int or value["critical_issues"] != 0 or
            value.get("reviewer_model") != "GPT-6 Astra" or
            value.get("reasoning") != "High"):
        raise HandoffError("E19 independent review is incomplete or did not pass")
    reviewed = value.get("reviewed_files")
    required_reviewed = {"tools/stage_handoff.py", "tools/s00e_preflight.py",
                         "tools/web_chat_handoff.py", "tools/s00e_test_record.py",
                         "tools/s00e_pytest_probe.py", "tools/s00e_evidence.py",
                         "tools/s00e_d2_probes.py",
                         "tools/s00e_prepare.py", "tools/s00e_smoke.py", "tools/s00e_approval.py",
                         "tests/test_stage_s00e_closeout.py",
                         "src/mosei/data/data_contract.py", "src/mosei/data/pooling.py",
                         "tests/test_stage_s00e_hardening.py", "tests/test_stage_handoff.py",
                         "tests/test_stage_s00e_phase_d_repair.py", "tests/test_stage_s00e_d2_repair.py"}
    if not isinstance(reviewed, dict) or not required_reviewed <= set(reviewed):
        raise HandoffError("E19 lacks reviewed file SHA256 bindings")
    for relative, expected in reviewed.items():
        _validate_evidence_path(relative, root=root, run_id=run_id,
                                stage="S00E", acceptance=acceptance)
        if sha256(root / relative) != expected:
            raise HandoffError(f"E19 reviewed file changed after independent review: {relative}")
    if candidates[0] not in acceptance:
        raise HandoffError("E19 review is not included in acceptance evidence")
    review_evidence = value.get("review_evidence")
    if (not isinstance(review_evidence, list) or
            f"reports/runs/{run_id}/TEST_RESULTS.json" not in review_evidence or
            not any("probe" in item.lower() for item in review_evidence if isinstance(item, str))):
        raise HandoffError("E19 independent review lacks actual probe and test evidence")
    bound_evidence = value.get("review_evidence_sha256")
    if not isinstance(bound_evidence, dict) or set(bound_evidence) != set(review_evidence):
        raise HandoffError("E19 evidence digest bindings missing")
    for relative in review_evidence:
        if sha256(root / relative) != bound_evidence[relative]:
            raise HandoffError("E19 actual reviewed evidence changed")
        _validate_evidence_path(relative, root=root, run_id=run_id,
                                stage="S00E", acceptance=acceptance)
    verify_independent_review_approval(path, sha256(path), task_id, run_id)


def verify_independent_review_approval(review_path: Path, review_sha256: str,
                                       task_id: str, run_id: str) -> None:
    """Authenticate exact reviewed bytes using an owner-controlled signing key."""
    from s00e_approval import ApprovalError, verify
    if sha256(review_path) != review_sha256:
        raise HandoffError("Independent review changed during verification")
    try:
        verify(review_path.parents[2], review_path, task_id, run_id)
    except (ApprovalError, OSError, subprocess.SubprocessError) as exc:
        raise HandoffError("MANUAL_REVIEW_APPROVAL_REQUIRED: trusted owner approval unavailable or invalid") from exc


def _validate_e21_preflight(evidence: list[str], *, root: Path, run_id: str) -> None:
    relative = "reports/engineering/s00e_prepublication_preflight.json"
    if relative not in evidence:
        raise HandoffError("E21 requires its independent read-only preflight receipt")
    value = load_json(public_path(relative, run_id, "S00E", root))
    manifest = root / "reports" / "runs" / run_id / "public" / "HANDOFF_INPUTS.json"
    if (value.get("name") != "PREPUBLICATION_SAFETY_PREFLIGHT" or
            value.get("stage") != "S00E" or value.get("run_id") != run_id or
            value.get("status") != "PASS" or value.get("read_only") is not True or
            value.get("e01_e20_passed") is not True or
            value.get("review_e19_checked") is not True or
            value.get("tracked_tree_and_index_checked") is not True or
            value.get("git_write_performed") is not False or
            value.get("release_created") is not False or
            value.get("manifest_sha256") != sha256(manifest)):
        raise HandoffError("E21 prepublication receipt is incomplete or stale")


def validate_gate(gate: dict, stage: str, task_id: str, run_id: str,
                  *, root: Path = ROOT, acceptance: dict[str, str] | None = None,
                  preflight: bool = False) -> None:
    expected_overall = "BLOCKED" if preflight else "PASS"
    expected_passed = False if preflight else True
    if (gate.get("task_id") != task_id or gate.get("run_id") != run_id or
            gate.get("status") != expected_overall or gate.get("passed") is not expected_passed):
        raise HandoffError("Stage Gate identity or overall status did not pass")
    items = gate.get("items")
    summary = gate.get("summary")
    if not isinstance(items, list) or not items or not isinstance(summary, dict):
        raise HandoffError("Stage Gate items or summary missing")
    statuses = ("PASS", "FAIL", "SKIPPED", "BLOCKED")
    if set(summary) != set(statuses) or any(type(summary[key]) is not int or summary[key] < 0 for key in statuses):
        raise HandoffError("Stage Gate summary malformed")
    ids = []
    if acceptance is None:
        acceptance = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or (item.get("status") != "PASS" and
                not (preflight and item.get("id") == "E21" and item.get("status") == "BLOCKED")):
            raise HandoffError("Stage Gate item did not pass")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x for x in evidence):
            raise HandoffError("Stage Gate item lacks evidence")
        if stage == "S00E" and acceptance and item["status"] == "PASS":
            for relative in evidence:
                _validate_evidence_path(relative, root=root, run_id=run_id,
                                        stage=stage, acceptance=acceptance)
            if item["id"] == "E19" and item["status"] == "PASS":
                _validate_e19_review(evidence, root=root, run_id=run_id,
                                     task_id=task_id, acceptance=acceptance)
            if item["id"] == "E21" and item["status"] == "PASS":
                _validate_e21_preflight(evidence, root=root, run_id=run_id)
        ids.append(item["id"])
    if len(ids) != len(set(ids)) or (stage == "S00E" and set(ids) != S00E_GATE_IDS):
        raise HandoffError("Stage Gate IDs incomplete or duplicated")
    expected_summary = {"PASS": len(items) - int(preflight), "FAIL": 0,
                        "SKIPPED": 0, "BLOCKED": int(preflight)}
    if summary != expected_summary:
        raise HandoffError("Stage Gate summary disagrees with items")


def validate_s00e_source(run: dict, root: Path = ROOT) -> None:
    """Recheck the official source fingerprint before any S00E Git publication."""
    baseline = load_json(root / "reports/data_contract/source_mutation_check.json")
    report = load_json(root / "reports/engineering/s00e_source_mutation_check.json")
    runtime = load_json(root / "reports/engineering/s00e_pytorch_runtime.json")
    expected = baseline.get("after")
    smoke = runtime.get("smoke")
    devices = smoke.get("devices") if isinstance(smoke, dict) else None
    environment = runtime.get("environment")
    required_device_checks = {"pooled_shapes_valid": True, "masked_tail_invariant": True,
                              "masked_nan_isolated": True, "linear_backward_finite": True}
    required_devices = {"cpu"}
    if isinstance(environment, dict) and environment.get("cuda_available") is True:
        required_devices.add("cuda")
    valid_devices = isinstance(devices, dict) and all(
        isinstance(devices.get(device), dict) and devices[device].get("bridge") == "PASS" and
        devices[device].get("pooled_modalities") == 3 and
        all(devices[device].get(key) is expected for key, expected in required_device_checks.items())
        for device in required_devices)
    if (run.get("task_id") != "S00E_S01_PRESTART_ENGINEERING_HARDENING" or
            run.get("stage") != "S00E" or
            runtime.get("task_id") != run.get("task_id") or runtime.get("stage") != "S00E" or
            runtime.get("run_id") != run.get("run_id") or
            runtime.get("data_kind") != "real_official_local" or
            report.get("task_id") != run.get("task_id") or report.get("stage") != "S00E" or
            report.get("run_id") != run.get("run_id") or
            not isinstance(smoke, dict) or type(smoke.get("batch_size")) is not int or smoke.get("batch_size") != 2 or
            smoke.get("split") != "train" or smoke.get("test_key_indexed") is not False or
            smoke.get("attachment3_content_opened") is not False or
            smoke.get("attachment4_content_opened") is not False or
            smoke.get("numpy_batch_unchanged") is not True or
            smoke.get("torch_cpu_storage_separate") is not True or
            not isinstance(environment, dict) or environment.get("name") != "birdAL" or
            type(environment.get("cuda_available")) is not bool or
            not valid_devices or
            not isinstance(expected, dict) or baseline.get("unchanged") is not True or baseline.get("before") != expected or
            report.get("unchanged") is not True or report.get("before") != expected or
            report.get("after") != expected or runtime.get("status") != "PASS" or
            runtime.get("source_unchanged") is not True or
            run.get("source_sha256_before") != expected.get("sha256") or
            run.get("source_sha256_after") != expected.get("sha256")):
        raise HandoffError("S00E source evidence disagrees with the S00D baseline")
    config = load_json(root / "configs/paths.local.json")
    if set(config) != {"data_root", "trusted_competition_pickle"} or config["trusted_competition_pickle"] is not True:
        raise HandoffError("Trusted local official source configuration required")
    source = Path(config["data_root"]) / "附件2-数据集特征文件" / "aligned_50.pkl"
    if source.is_symlink() or not source.is_file():
        raise HandoffError("Trusted official aligned source unavailable")
    stat = source.stat()
    if (stat.st_size != expected.get("size") or stat.st_mtime_ns != expected.get("mtime_ns") or
            sha256(source) != expected.get("sha256")):
        raise HandoffError("Official aligned source changed before publication")


def validate_acceptance(path: Path, stage: str, *, task_id: str | None = None,
                        run_id: str | None = None, root: Path | None = None) -> None:
    root = ROOT if root is None else root
    acceptance = load_json(path)
    actual_stage = acceptance.get("stage")
    if actual_stage != stage and not (isinstance(actual_stage, str) and actual_stage.startswith(stage + "_")):
        raise HandoffError("Stage acceptance ID mismatch")
    if stage == "S00E" and (acceptance.get("task_id") != task_id or
                             acceptance.get("run_id") != run_id or
                             actual_stage != stage):
        raise HandoffError("S00E acceptance task/stage/run identity mismatch")
    evidence = acceptance.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise HandoffError("Missing acceptance evidence")
    seen = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise HandoffError("Invalid acceptance evidence")
        relative = item.get("path")
        if not isinstance(relative, str) or relative in seen:
            raise HandoffError("Invalid acceptance path")
        seen.add(relative)
        parts = PurePosixPath(relative).parts
        if relative.startswith("/") or "\\" in relative or ".." in parts or forbidden_path(relative) or {x.lower() for x in parts} & {"private", "artifacts"}:
            raise HandoffError(f"Unsafe acceptance path: {relative}")
        target = root / relative
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()) or sha256(target) != item.get("sha256"):
            raise HandoffError(f"Acceptance hash mismatch: {relative}")


def validate_run(manifest: dict, root: Path = ROOT, *, preflight: bool = False) -> tuple[list[str], Path]:
    stage = manifest.get("stage")
    run_id = manifest.get("run_id")
    task_id = manifest.get("task_id")
    if not isinstance(stage, str) or not STAGE.fullmatch(stage) or not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise HandoffError("Invalid stage or run ID")
    if not isinstance(task_id, str) or not task_id.startswith(stage + "_"):
        raise HandoffError("Task ID does not match stage")
    spec = (root / "TASK_SPEC.md").read_text(encoding="utf-8")
    if spec_scalar(spec, "task_id") != task_id or spec_scalar(spec, "status") != "ACTIVE" or spec_scalar(spec, "research_authorized") != "true":
        raise HandoffError("Current TASK_SPEC does not authorize this stage")
    run_dir = root / "reports" / "runs" / run_id
    run = load_json(run_dir / "RUN.json")
    gate = load_json(run_dir / "GATE.json")
    tests = load_json(run_dir / "TEST_RESULTS.json")
    if (run.get("task_id") != task_id or run.get("data_kind") not in {"official", "real_official_local"} or
            (stage == "S00E" and (run.get("stage") != stage or run.get("run_id") != run_id))):
        raise HandoffError("Real official run evidence required")
    # Reject a malformed Gate before touching its acceptance evidence.
    validate_gate(gate, stage, task_id, run_id, preflight=preflight)
    acceptance_path = root / "reports" / "stages" / stage / "acceptance.json"
    acceptance = _acceptance_map(acceptance_path, stage, task_id, run_id, root)
    validate_gate(gate, stage, task_id, run_id, root=root, acceptance=acceptance,
                  preflight=preflight)
    if stage == "S00E":
        try:
            validate_s00e_tests(tests, root, task_id, run_id)
        except EvidenceError as exc:
            raise HandoffError(str(exc)) from exc
    elif tests.get("exit_code") != 0 or type(tests.get("failed")) is not int or tests["failed"] != 0 or type(tests.get("passed")) is not int or tests["passed"] < 1:
        raise HandoffError("Actual engineering tests did not pass")
    if stage == "S00E":
        tested_files = tests["tested_files_sha256"]
    if stage == "S00E":
        validate_s00e_source(run, root)
    files = manifest.get("public_files")
    if not isinstance(files, list) or not all(isinstance(x, str) for x in files):
        raise HandoffError("Manifest requires exact public_files list")
    if stage == "S00E" and not {name for name in files if name.endswith(".py")} <= set(tested_files):
        raise HandoffError("Manifest code or tests are absent from executed SHA256 record")
    required = ["CHATGPT_REVIEW.md", f"reports/runs/{run_id}/RUN.json", f"reports/runs/{run_id}/GATE.json", f"reports/runs/{run_id}/TEST_RESULTS.json", f"reports/stages/{stage}/acceptance.json", f"reports/runs/{run_id}/public/HANDOFF_INPUTS.json"]
    files = list(dict.fromkeys(required + files))
    findings = {name: issues for name in files if (issues := scan_public(public_path(name, run_id, stage, root)))}
    if findings:
        raise HandoffError(f"Public safety scan failed: {findings}")
    tree = scan_tracked_public_tree(root)
    if tree["findings"]:
        raise HandoffError(f"Tracked public text safety scan failed: {tree['findings']}")
    return files, run_dir


def exact_stage(paths: list[str], message: str) -> str:
    print(git("status", "--short"))
    command("git", "-c", "core.autocrlf=false", "add", "--", *paths)
    staged = git("diff", "--cached", "--name-only", "-z").split("\0")
    staged = [x for x in staged if x]
    if not staged or not set(staged) <= set(paths):
        raise HandoffError("Staged paths differ from the explicit allowlist")
    print(git("diff", "--cached", "--name-status"))
    if command("git", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
               "diff", "--cached", "--check", check=False).returncode:
        raise HandoffError("Staged diff has whitespace errors")
    tree = scan_tracked_public_tree()
    if tree["findings"]:
        raise HandoffError(f"Tracked public text safety scan failed: {tree['findings']}")
    for name in staged:
        path = public_path(name, _run_from_path(paths), _stage_from_path(paths)) if name != "state/LATEST_RUN.json" else ROOT / name
        issues = scan_public(path)
        staged_text = git("show", f":{name}")
        issues.extend(scan_text(staged_text))
        if RAW_ID.search(staged_text):
            issues.append("raw_sample_id_in_index")
        if issues:
            raise HandoffError(f"Staged public safety check failed for {name}: {issues}")
    verify_staged_bytes(staged)
    command("git", "commit", "-m", message)
    return git("rev-parse", "HEAD")


def verify_staged_bytes(paths: list[str]) -> None:
    """The commit must retain the bytes whose SHA256 was tested and reviewed."""
    for name in paths:
        result = subprocess.run(["git", "show", f":{name}"], cwd=ROOT, capture_output=True)
        if result.returncode or result.stdout != (ROOT / name).read_bytes():
            raise HandoffError("Staged bytes differ from reviewed worktree bytes")


def build_review_asset(asset: Path, paths: list[str]) -> None:
    """Freeze committed bytes and apply the same scanner to every Release member."""
    members = {}
    for name in paths:
        result = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=ROOT, capture_output=True)
        if result.returncode or result.stdout != (ROOT / name).read_bytes():
            raise HandoffError("Release input differs from implementation commit")
        if name in members or scan_public_bytes(name, result.stdout):
            raise HandoffError("Unsafe or duplicate Review Release member")
        members[name] = result.stdout
    asset.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(asset, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in members.items():
            output.writestr(name, data)
    with zipfile.ZipFile(asset) as check:
        if check.testzip() is not None or check.namelist() != list(members):
            raise HandoffError("Review Release ZIP membership or CRC mismatch")
        for name, data in members.items():
            if check.read(name) != data or scan_public_bytes(name, check.read(name)):
                raise HandoffError("Review Release ZIP member integrity failure")


def _run_from_path(paths: list[str]) -> str:
    return next(x.split("/")[2] for x in paths if x.startswith("reports/runs/"))


def _stage_from_path(paths: list[str]) -> str:
    return next(x.split("/")[2] for x in paths if x.startswith("reports/stages/"))


def push_and_verify(commit_sha: str) -> None:
    command("git", "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    remote = git("ls-remote", "--heads", "origin", BRANCH).split()
    if not remote or remote[0] != commit_sha:
        raise HandoffError("Remote branch HEAD verification failed")


def release_and_verify(run_id: str, implementation_sha: str, asset: Path, run_dir: Path) -> dict:
    tag = f"codex-run-{run_id}"
    existing = command("gh", "release", "view", tag, "--repo", "BiLiangXin/jingsai", "--json", "tagName,targetCommitish,assets,url,isDraft", check=False)
    if existing.returncode == 0:
        raise HandoffError("Release tag already exists; inspect it before retrying")
    command("gh", "release", "create", tag, str(asset), "--repo", "BiLiangXin/jingsai", "--target", implementation_sha, "--title", tag, "--notes", f"Authorized stage review for {run_id}")
    view = load_release(tag)
    remote_asset = next((x for x in view.get("assets", []) if x.get("name") == asset.name), None)
    if view.get("targetCommitish") != implementation_sha or not remote_asset or remote_asset.get("size") != asset.stat().st_size:
        raise HandoffError("Release target or asset size verification failed")
    tag_ref = git("ls-remote", "--tags", "origin", tag).split()
    if not tag_ref or tag_ref[0] != implementation_sha:
        raise HandoffError("Remote tag target verification failed")
    verify_dir = run_dir / "private" / f"release-verify-{uuid.uuid4().hex[:8]}"
    verify_dir.mkdir(parents=True, exist_ok=False)
    command("gh", "release", "download", tag, "--repo", "BiLiangXin/jingsai", "--pattern", asset.name, "--dir", str(verify_dir))
    local_hash = sha256(asset)
    downloaded_hash = sha256(verify_dir / asset.name)
    if local_hash != downloaded_hash or (remote_asset.get("digest") and remote_asset["digest"] != f"sha256:{local_hash}"):
        raise HandoffError("Downloaded asset SHA256 mismatch")
    return {"tag": tag, "url": view["url"], "target": implementation_sha, "asset_name": asset.name, "asset_size_bytes": asset.stat().st_size, "local_sha256": local_hash, "downloaded_sha256": downloaded_hash}


def load_release(tag: str) -> dict:
    return json.loads(command("gh", "release", "view", tag, "--repo", "BiLiangXin/jingsai", "--json", "tagName,targetCommitish,assets,url,isDraft").stdout)


def worktree_changed_paths() -> set[str]:
    records = command("git", "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.split("\0")
    paths = set()
    index = 0
    while index < len(records) and records[index]:
        record = records[index]
        if len(record) < 4 or record[2] != " ":
            raise HandoffError("Malformed Git porcelain status")
        paths.add(record[3:].replace("\\", "/"))
        if "R" in record[:2] or "C" in record[:2]:
            index += 1
            if index >= len(records) or not records[index]:
                raise HandoffError("Incomplete Git rename status")
            paths.add(records[index].replace("\\", "/"))
        index += 1
    return paths


def set_review_field(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:\s*.*$")
    replacement = f"{key}: `{value}`"
    return pattern.sub(replacement, text, count=1) if pattern.search(text) else text.replace("\n", "\n" + replacement + "\n", 1)


def refresh_acceptance(stage: str, run_id: str, new_paths: list[str]) -> None:
    path = ROOT / "reports" / "stages" / stage / "acceptance.json"
    value = load_json(path)
    entries = {x["path"]: x for x in value["evidence"]}
    for relative in new_paths:
        entries[relative] = {"requirement": PurePosixPath(relative).name, "path": relative, "sha256": sha256(ROOT / relative)}
    for entry in entries.values():
        entry["sha256"] = sha256(ROOT / entry["path"])
    value["evidence"] = list(entries.values())
    write_json(path, value)


def latest_index(stage: str, task_id: str, run_id: str, implementation: str, metadata: str, release: dict, evidence: list[str]) -> dict:
    return {
        "schema_version": 1,
        "latest_completed_stage": stage,
        "task_id": task_id,
        "run_id": run_id,
        "repository": "BiLiangXin/jingsai",
        "branch": BRANCH,
        "branch_head": {"ref": f"refs/heads/{BRANCH}", "verified_stage_completion_sha": metadata},
        "implementation_commit": implementation,
        "metadata_commit": metadata,
        "release": release,
        "review_path": "CHATGPT_REVIEW.md",
        "core_public_evidence_paths": evidence,
        "next_stage_authorized": False,
        "handoff_status": "PENDING_RESEARCH_REVIEW",
    }


def publish(manifest_path: Path) -> dict:
    initial_head = verify_workspace()
    expected_manifest = manifest_path.resolve()
    manifest = load_json(expected_manifest)
    stage, run_id, task_id = manifest["stage"], manifest["run_id"], manifest["task_id"]
    if expected_manifest != (ROOT / "reports" / "runs" / run_id / "public" / "HANDOFF_INPUTS.json").resolve():
        raise HandoffError("Manifest must reside in the corresponding run/public directory")
    latest_path = ROOT / "state" / "LATEST_RUN.json"
    if latest_path.is_file() and load_json(latest_path).get("run_id") == run_id:
        raise HandoffError("This run is already indexed as completed; no duplicate publication")
    release_probe = command("gh", "release", "view", f"codex-run-{run_id}", "--repo", "BiLiangXin/jingsai", "--json", "tagName", check=False)
    if release_probe.returncode == 0:
        raise HandoffError("Release tag already exists; inspect it before any Git write")
    if "not found" not in release_probe.stderr.lower():
        raise HandoffError("Cannot confirm Release tag availability")
    files, run_dir = validate_run(manifest)
    for changed in worktree_changed_paths():
        if changed not in files:
            raise HandoffError("Unrelated workspace changes present; review them before publication")
    manifest_rows = [{"path": x, "size": (ROOT / x).stat().st_size, "sha256": sha256(ROOT / x)} for x in files]
    manifest_relative = f"reports/runs/{run_id}/MANIFEST.json"
    write_json(ROOT / manifest_relative, {"stage": stage, "run_id": run_id, "files": manifest_rows})
    if scan_public(ROOT / manifest_relative):
        raise HandoffError("Generated public manifest failed safety scan")
    files.append(manifest_relative)
    implementation = exact_stage(files, f"{stage} publish implementation {run_id}")
    push_and_verify(implementation)
    asset = run_dir / "artifacts" / f"review-{run_id}.zip"
    build_review_asset(asset, files)
    release = release_and_verify(run_id, implementation, asset, run_dir)
    receipt_relative = f"reports/runs/{run_id}/PUBLISH_RECEIPT.json"
    test_record = load_json(run_dir / "TEST_RESULTS.json")
    receipt = {"run_id": run_id, "stage": stage, "branch": BRANCH, "baseline_sha": initial_head, "implementation_commit": implementation, "implementation_staged_files": files, "actual_tests": {key: test_record.get(key) for key in ("command", "exit_code", "passed", "failed")}, "gate": load_json(run_dir / "GATE.json")["summary"], "release": release, "implementation_push_result": "PASS", "remote_asset_verified": True}
    write_json(ROOT / receipt_relative, receipt)
    review_path = ROOT / "CHATGPT_REVIEW.md"
    review = review_path.read_text(encoding="utf-8")
    for key, value in (("status", "PUBLICATION_VERIFIED_PENDING_INDEX"), ("implementation_commit", implementation), ("release_url", release["url"]), ("release_tag", release["tag"]), ("review_asset", release["asset_name"])):
        review = set_review_field(review, key, value)
    review += f"\n## Verified automatic handoff\n\nRelease target: `{implementation}`. Asset SHA256: `{release['local_sha256']}`. Downloaded SHA256 matches. Stage remains `PENDING_RESEARCH_REVIEW`; `NEXT_STAGE_NOT_AUTHORIZED`.\n"
    review_path.write_text(review, encoding="utf-8")
    run_record = load_json(run_dir / "RUN.json")
    run_record.update({"implementation_commit": implementation, "release_url": release["url"], "status": "PUBLICATION_VERIFIED_PENDING_INDEX"})
    write_json(run_dir / "RUN.json", run_record)
    refresh_acceptance(stage, run_id, [receipt_relative, f"reports/runs/{run_id}/RUN.json"])
    metadata_paths = [receipt_relative, "CHATGPT_REVIEW.md", f"reports/runs/{run_id}/RUN.json", f"reports/stages/{stage}/acceptance.json"]
    for x in metadata_paths:
        if scan_public(ROOT / x):
            raise HandoffError(f"Metadata safety scan failed: {x}")
    metadata = exact_stage(metadata_paths, f"{stage} record verified release {run_id}")
    push_and_verify(metadata)
    review = set_review_field(review_path.read_text(encoding="utf-8"), "status", "SUCCESS")
    review = set_review_field(review, "metadata_commit", metadata)
    review_path.write_text(review, encoding="utf-8")
    refresh_acceptance(stage, run_id, ["CHATGPT_REVIEW.md"])
    validate_acceptance(ROOT / "reports" / "stages" / stage / "acceptance.json", stage,
                        task_id=task_id, run_id=run_id, root=ROOT)
    evidence = [x for x in files if x.startswith("docs/") or x.startswith("reports/data_audit/") or x.startswith("reports/data_contract/") or x.startswith("reports/engineering/") or x.startswith(f"reports/stages/{stage}/")]
    evidence += [f"reports/runs/{run_id}/RUN.json", f"reports/runs/{run_id}/GATE.json", f"reports/runs/{run_id}/TEST_RESULTS.json", f"reports/runs/{run_id}/MANIFEST.json", receipt_relative]
    index = latest_index(stage, task_id, run_id, implementation, metadata, release, list(dict.fromkeys(evidence)))
    write_json(ROOT / "state" / "LATEST_RUN.json", index)
    final_paths = ["CHATGPT_REVIEW.md", "state/LATEST_RUN.json"]
    for x in final_paths:
        if scan_public(ROOT / x):
            raise HandoffError(f"Final safety scan failed: {x}")
    index_commit = exact_stage(final_paths + [f"reports/runs/{run_id}/GATE.json", f"reports/stages/{stage}/acceptance.json"], f"{stage} update latest-run index {run_id}")
    push_and_verify(index_commit)
    final_release = load_release(release["tag"])
    if final_release.get("targetCommitish") != implementation or not any(x.get("name") == release["asset_name"] and x.get("size") == release["asset_size_bytes"] for x in final_release.get("assets", [])):
        raise HandoffError("Final Release verification failed")
    return {"stage": stage, "run_id": run_id, "implementation_commit": implementation, "metadata_commit": metadata, "index_commit": index_commit, "release": release, "branch_head_ref": index["branch_head"]["ref"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True, help="Exact-file manifest at reports/runs/<run_id>/public/HANDOFF_INPUTS.json")
    args = parser.parse_args()
    try:
        result = publish(args.manifest)
    except (HandoffError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"HANDOFF_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
