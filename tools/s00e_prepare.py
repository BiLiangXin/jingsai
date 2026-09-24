"""Prepare truthful PHASE C review evidence; never publish or claim final Gate success."""
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

from mosei_flow import sha256, write_json
from stage_handoff import (
    BRANCH, ORIGIN, RUN_ID, S00E_GATE_IDS, scan_public,
    scan_tracked_public_tree, spec_scalar, validate_acceptance,
    validate_s00e_source, HandoffError,
)
from s00e_evidence import EvidenceError, validate_tests

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "S00E_S01_PRESTART_ENGINEERING_HARDENING"
ACTIVATION = "b98fd8fce558bb80aaa22c1cd2c057eab641d54d"
SAFETY_PRECOMMIT = "078028f022cc175361cb8bf908f760087f35f709"
GOVERNANCE_HEAD = "d9e4edb11b710a92ef33c256bfca6684162911d7"
OLD_CSV = ("docs/samples/labels-100.csv", "docs/samples/labels-feature-first10.csv")
REPORT_NAMES = (
    "s00e_public_tree_scan.json", "s00e_pytorch_runtime.json",
    "s00e_contract_hardening.json", "s00e_security_findings.json",
    "s00e_source_mutation_check.json", "s00e_repair_matrix.json",
    "s00e_d2_repair_matrix.json", "s00e_d2_review_inputs.json",
    "s00e_d2_probe_results.json",
    "s00e_prepublication_preflight.json",
)
CODE = (
    "tools/s00e_approval.py", "tests/test_stage_s00e_closeout.py",
    "src/mosei/data/data_contract.py", "src/mosei/data/pooling.py",
    "tools/stage_handoff.py", "tools/s00d_finalize.py",
    "tools/s00e_smoke.py", "tools/s00e_test_record.py", "tools/s00e_prepare.py",
    "tools/s00e_preflight.py", "tools/web_chat_handoff.py",
    "tools/s00e_pytest_probe.py", "tools/s00e_evidence.py", "tools/s00e_d2_probes.py",
    "tests/test_stage_handoff.py", "tests/test_stage_s00e_hardening.py",
    "tests/test_stage_s00e_phase_d_repair.py", "tests/test_stage_s00e_d2_repair.py",
)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def public_candidates() -> list[str]:
    names = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return sorted(name for name in names if name and Path(name).suffix.lower() in {
        ".md", ".json", ".csv", ".py", ".toml", ".yaml", ".yml"
    })


def review_diff(run_id: str) -> None:
    private = ROOT / "reports" / "runs" / run_id / "private"
    private.mkdir(parents=True, exist_ok=True)
    tracked = subprocess.run(["git", "diff", "--", *CODE], cwd=ROOT,
                             check=True, capture_output=True, text=True, encoding="utf-8").stdout
    additions = []
    for name in CODE:
        tracked_name = subprocess.run(["git", "ls-files", "--error-unmatch", "--", name],
                                      cwd=ROOT, capture_output=True)
        if tracked_name.returncode == 0:
            continue
        lines = (ROOT / name).read_text(encoding="utf-8").splitlines(keepends=True)
        additions.extend(difflib.unified_diff([], lines, fromfile="/dev/null", tofile=name))
    (private / "PHASE_C_DIFF.patch").write_text(tracked + "".join(additions), encoding="utf-8")


def make_gate(run_id: str, evidence: dict[str, list[str]], checks: dict[str, bool]) -> dict:
    if set(evidence) != S00E_GATE_IDS or set(checks) != S00E_GATE_IDS:
        raise ValueError("S00E Gate definition must contain exactly E01-E21")
    items = [{"id": code, "status": "PASS" if checks[code] else "BLOCKED",
              "detail": "Verified PHASE C evidence" if checks[code] else
                        "Pending independent PHASE D review or PHASE E handoff",
              "evidence": evidence[code]} for code in sorted(S00E_GATE_IDS)]
    summary = {key: sum(item["status"] == key for item in items)
               for key in ("PASS", "FAIL", "SKIPPED", "BLOCKED")}
    return {"task_id": TASK_ID, "run_id": run_id, "status": "BLOCKED",
            "passed": False, "summary": summary, "items": items,
            "phase_c_status": "READY_FOR_INDEPENDENT_REVIEW"}


def prepare(run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    spec = (ROOT / "TASK_SPEC.md").read_text(encoding="utf-8")
    required = {"task_id": TASK_ID, "status": "ACTIVE", "research_authorized": "true",
                "next_stage_authorized": "false", "s01_training_authorized": "false"}
    if any(spec_scalar(spec, key) != value for key, value in required.items()):
        raise RuntimeError("S00E authorization mismatch")
    if (git("remote", "get-url", "origin") != ORIGIN or
            git("branch", "--show-current") != BRANCH or
            git("config", "--local", "--get", "mosei.officialWorkspace").lower() != "true" or
            git("rev-parse", "HEAD") != GOVERNANCE_HEAD or
            git("merge-base", SAFETY_PRECOMMIT, "HEAD") != SAFETY_PRECOMMIT or
            git("diff", "--name-only", SAFETY_PRECOMMIT, "HEAD").splitlines() != ["AGENTS.md", "DECISIONS.md", "TASK_SPEC.md", "docs/HANDOFF_WORKFLOW.md"]):
        raise RuntimeError("Expected exact authorized governance HEAD after safety precommit")
    remote = git("ls-remote", "origin", f"refs/heads/{BRANCH}").split()
    if not remote or remote[0] != GOVERNANCE_HEAD:
        raise RuntimeError("Authorized governance HEAD not verified on remote")
    if git("ls-files", "--", *OLD_CSV) or any((ROOT / name).exists() for name in OLD_CSV):
        raise RuntimeError("Unsafe sample CSV remains in current tree")
    frozen_q1 = [line for line in git("show", f"{SAFETY_PRECOMMIT}:DECISIONS.md").splitlines()
                 if line.startswith("| Q1-")]
    current_q1 = [line for line in (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines()
                  if line.startswith("| Q1-")]
    if not frozen_q1 or current_q1 != frozen_q1:
        raise RuntimeError("Frozen Q1 governance changed outside authorized scope")
    tests = json.loads((ROOT / f"reports/runs/{run_id}/TEST_RESULTS.json").read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / "reports/engineering/s00e_pytorch_runtime.json").read_text(encoding="utf-8"))
    source = json.loads((ROOT / "reports/engineering/s00e_source_mutation_check.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "reports/data_contract/source_mutation_check.json").read_text(encoding="utf-8"))
    try:
        validate_tests(tests, ROOT, TASK_ID, run_id)
        candidate_run = {"task_id": TASK_ID, "stage": "S00E", "run_id": run_id,
                         "source_sha256_before": source["before"]["sha256"],
                         "source_sha256_after": source["after"]["sha256"]}
        validate_s00e_source(candidate_run, ROOT)
    except (EvidenceError, HandoffError, KeyError, TypeError) as exc:
        raise RuntimeError("Actual PHASE C test, runtime, or source evidence incomplete") from exc
    tree_before = scan_tracked_public_tree(ROOT)
    pending_before = {name: issues for name in public_candidates()
                      if (issues := scan_public(ROOT / name))}
    if tree_before["findings"] or pending_before:
        raise RuntimeError("Public safety scan failed before preparing evidence")

    run_base = f"reports/runs/{run_id}"
    docs = ROOT / "docs/S00E_ENGINEERING_HARDENING.md"
    docs.write_text(
        f"# S00E PHASE C engineering review\n\n"
        f"task_id: `{TASK_ID}`\nrun_id: `{run_id}`\n"
        f"status: `READY_FOR_INDEPENDENT_REVIEW`\n"
        f"activation_commit: `{ACTIVATION}`\n"
        f"safety_governance_precommit: `{SAFETY_PRECOMMIT}`\n\n"
        "The separate ordinary safety commit removed both sample-level CSVs from the current branch and corrected current governance/navigation. CURRENT_TREE_REMOVAL != HISTORICAL_ERASURE. A repository owner may assess historical access as a separate PROPOSED_SECURITY_ACTION; no history rewrite was attempted.\n\n"
        "Engineering changes enforce the existing aligned baseline mask equalities, post-float32 finite and strict-zero target checks, NumPy/Torch storage separation, and NaN-safe masked pooling. Publication now validates complete mandatory Gate items and scans the tracked public text index/worktree. The S00D test-count constant was replaced with actual pytest collection/execution. Frozen D-DATA-01 through D-DATA-07 and archived S00D evidence were not rewritten.\n\n"
        f"The birdAL full suite actually collected and executed {tests['collected']} tests: {tests['passed']} passed, {tests['failed']} failed, {tests['skipped']} skipped (exit {tests['exit_code']}); {tests['subtests_passed']} subtests passed separately. The tiny official aligned TRAIN smoke used a batch of two on CPU and available CUDA, with three-modal pooling, a throwaway linear backward and finite gradients. No optimizer, epoch, checkpoint, prediction, metric, valid/test indexing or Attachment 3/4 content access occurred. The trusted pickle container was deserialized structurally; only its train key was indexed.\n\n"
        f"The official source SHA256 before/after is `{source['before']['sha256']}`; it matches the S00D baseline. Aggregate runtime, source evidence and the B01–B13 repair matrix are in `reports/engineering/`. Full code review input is the working-tree diff from the safety precommit plus newly added files listed in the run evidence. The ignored private run directory also contains `PHASE_C_DIFF.patch` for local review.\n\n"
        "Astra's second PHASE D review found R01–R04 and M01. This D2 repair adds scalar and duplicate-key scans, run-bound evidence, a manual independent-review approval hard gate, shared runtime/test checks, and actual pytest node-phase proof. E19 remains BLOCKED pending a fresh independent review and trustworthy external approval. E21 remains BLOCKED until E19 and read-only prepublication checks pass. Release verification is postpublication and is not an E21 prerequisite. This evidence does not claim S00E completion or S01 authorization.\n",
        encoding="utf-8")

    security = {"stage": "S00E", "run_id": run_id, "current_tree_csv_removed": True,
                "current_tree_removal_is_historical_erasure": False,
                "safety_governance_precommit": SAFETY_PRECOMMIT,
                "safety_precommit_remote_verified": True,
                "old_csv_paths_absent": list(OLD_CSV),
                "proposed_security_action": "Repository owner to separately assess historical accessibility; no history rewrite authorized or performed.",
                "sample_rows_or_labels_published": False}
    write_json(ROOT / "reports/engineering/s00e_security_findings.json", security)
    contract = {"stage": "S00E", "run_id": run_id, "data_kind": "synthetic_regressions_plus_real_train_smoke",
                "frozen_decisions_unchanged": True,
                "mask_equalities_checked": ["shared_nonempty_prefix_support", "padding_complement",
                                            "text_observed_equals_support",
                                            "audio_vision_structural_zero_matches_raw",
                                            "audio_vision_observed_equals_supported_nonzero"],
                "post_float32_finite_checked": True, "strict_zero_target_preserved": True,
                "torch_storage_isolated": True, "masked_nan_isolated": True,
                "normalized_zero_keeps_source_mask": True,
                "actual_test_results": f"{run_base}/TEST_RESULTS.json",
                "real_runtime_evidence": "reports/engineering/s00e_pytorch_runtime.json"}
    write_json(ROOT / "reports/engineering/s00e_contract_hardening.json", contract)
    repairs = [
        ("B01", "CRITICAL", ["DECISIONS.md", "docs/data-guide.md", "reports/engineering/s00e_security_findings.json"],
         "Two old CSVs removed by separate verified ordinary precommit; current backlinks removed."),
        ("B02", "MAJOR", ["src/mosei/data/data_contract.py", "tests/test_stage_s00e_hardening.py"],
         "Every supplied mask dtype, shape, support prefix and frozen equality is validated."),
        ("B03", "MAJOR", ["src/mosei/data/data_contract.py", "tests/test_stage_s00e_hardening.py"],
         "Post-float32 finite and strict-zero checks reject overflow and sign collapse."),
        ("B04", "CRITICAL", ["tools/stage_handoff.py", "tests/test_stage_s00e_hardening.py"],
         "All 21 S00E IDs, PASS statuses, evidence, identity and summary counts are checked."),
        ("B05", "MAJOR", ["tools/stage_handoff.py", "reports/engineering/s00e_public_tree_scan.json"],
         "Entire tracked text index/worktree and pending public files are scanned before publication."),
        ("B06", "MAJOR", ["tools/s00e_smoke.py", "reports/engineering/s00e_pytorch_runtime.json"],
         "birdAL CPU/CUDA runtime and tiny official TRAIN forward/backward actually exercised."),
        ("B07", "MAJOR", ["src/mosei/data/data_contract.py", "tests/test_stage_s00e_hardening.py"],
         "Batch construction and every Torch bridge tensor own independent storage."),
        ("B08", "MAJOR", ["src/mosei/data/pooling.py", "tests/test_stage_s00e_hardening.py"],
         "Masked NaN/Inf tails are isolated; supported nonfinite values are rejected."),
        ("B09", "MAJOR", ["tools/s00d_finalize.py", f"{run_base}/TEST_RESULTS.json"],
         "Actual pytest collection/execution replaces the hardcoded S00D count."),
        ("B10", "MAJOR", ["docs/data-guide.md", "docs/DATA_CONTRACT_EVIDENCE.md"],
         "Current guide uses verified S00B/C/D facts and removes test-bearing pooled label table."),
        ("B11", "MAJOR", ["DECISIONS.md", "docs/data-guide.md"],
         "Q1 supplied source/retention rules recorded as SPECIFIED; missing mapping undecided."),
        ("B12", "MAJOR", ["tools/stage_handoff.py", "tests/test_stage_handoff.py"],
         "S00E engineering reports are narrowly allowlisted and included in latest index selection."),
        ("B13", "MINOR", ["README_CODEX.md", "state/NEXT_ACTIONS.md", "docs/HANDOFF_WORKFLOW.md"],
         "Live navigation now distinguishes completed S00D from active S00E."),
    ]
    matrix = {"stage": "S00E", "run_id": run_id, "phase": "C",
              "status": "READY_FOR_INDEPENDENT_REVIEW",
              "official_torch_version_listing": "https://pytorch.org/get-started/previous-versions/",
              "findings": [{"id": code, "severity": severity,
                            "phase_c_state": "IMPLEMENTED_AND_TESTED",
                            "repair": detail, "evidence": paths}
                           for code, severity, paths, detail in repairs],
              "unresolved": [
                  "E19 independent Astra review pending.",
        "E21 PREPUBLICATION_SAFETY_PREFLIGHT pending E19 and PHASE E; Release verification is post-publication.",
                  "Historical access to deleted sample CSVs requires separate owner assessment.",
                  "Installed Torch package origin was not independently authenticated; the local runtime and the official release-version listing were verified separately."
              ]}
    write_json(ROOT / "reports/engineering/s00e_repair_matrix.json", matrix)
    write_json(ROOT / "reports/engineering/s00e_d2_review_inputs.json",
               {"task_id": TASK_ID, "stage": "S00E", "run_id": run_id,
                "safety_governance_precommit": SAFETY_PRECOMMIT,
                "governance_head": GOVERNANCE_HEAD,
                "reviewed_files": {name: sha256(ROOT / name) for name in CODE}})
    write_json(ROOT / "reports/engineering/s00e_prepublication_preflight.json",
               {"stage": "S00E", "run_id": run_id,
                "name": "PREPUBLICATION_SAFETY_PREFLIGHT", "status": "BLOCKED",
                "reason": "E19 independent Astra re-review pending", "read_only": True,
                "git_write_performed": False, "release_created": False})
    run = {"task_id": TASK_ID, "run_id": run_id, "stage": "S00E",
           "status": "PHASE_C_READY_FOR_INDEPENDENT_REVIEW",
           "data_kind": "real_official_local", "branch": BRANCH,
           "activation_commit": ACTIVATION, "safety_governance_precommit": SAFETY_PRECOMMIT,
           "implementation_commit": None, "metadata_commit": None, "release_url": None,
           "environment": runtime["environment"], "source_file": "aligned_50.pkl",
           "source_sha256_before": source["before"]["sha256"],
           "source_sha256_after": source["after"]["sha256"],
           "split_usage": {"train": "tiny engineering smoke only",
                           "valid": "not indexed", "test": "quarantined; not indexed"},
           "trusted_pickle_container_deserialized": True,
           "attachment3_content_inspected": False, "attachment4_content_inspected": False,
           "model_training_performed": False, "predictive_metrics": None,
           "next_stage_authorized": False}
    write_json(ROOT / f"{run_base}/RUN.json", run)
    files = ["docs/S00E_ENGINEERING_HARDENING.md", "docs/data-guide.md",
             "docs/HANDOFF_WORKFLOW.md",
             *[f"reports/engineering/{name}" for name in REPORT_NAMES], *CODE]
    manifest = {"stage": "S00E", "task_id": TASK_ID, "run_id": run_id,
                "public_files": files}
    write_json(ROOT / f"{run_base}/public/HANDOFF_INPUTS.json", manifest)

    tree = scan_tracked_public_tree(ROOT)
    candidates = public_candidates()
    extra = {name: issues for name in candidates
             if (issues := scan_public(ROOT / name))}
    if tree["findings"] or extra:
        raise RuntimeError(f"Public text safety findings: tracked={tree['findings']}, pending={extra}")
    tree_report = {"stage": "S00E", "run_id": run_id, "status": "PASS_AT_PHASE_C",
                   "tracked_text_files_scanned": tree["scanned_text_files"],
                   "pending_public_text_files_scanned": len(candidates),
                   "tracked_findings": {}, "pending_findings": {},
                   "index_and_worktree_scanned": True,
                   "post_staging_rescan_required_in_PHASE_E": True}
    write_json(ROOT / "reports/engineering/s00e_public_tree_scan.json", tree_report)

    evidence = {
        "E01": ["AGENTS.md", f"{run_base}/RUN.json"],
        "E02": ["TASK_SPEC.md", f"{run_base}/RUN.json"],
        "E03": ["docs/S00D_DATA_CONTRACT.md", "reports/engineering/s00e_source_mutation_check.json"],
        "E04": ["reports/engineering/s00e_security_findings.json"],
        "E05": ["reports/engineering/s00e_public_tree_scan.json", "tools/stage_handoff.py"],
        "E06": ["src/mosei/data/data_contract.py", "tests/test_stage_s00e_hardening.py"],
        "E07": ["src/mosei/data/data_contract.py", "tests/test_stage_s00e_hardening.py"],
        "E08": ["tools/stage_handoff.py", "tests/test_stage_s00e_hardening.py"],
        "E09": [f"{run_base}/TEST_RESULTS.json", "tools/s00e_test_record.py"],
        "E10": ["reports/engineering/s00e_pytorch_runtime.json"],
        "E11": ["reports/engineering/s00e_pytorch_runtime.json", "tools/s00e_smoke.py"],
        "E12": ["reports/engineering/s00e_pytorch_runtime.json", "src/mosei/data/pooling.py"],
        "E13": ["reports/engineering/s00e_pytorch_runtime.json"],
        "E14": ["reports/engineering/s00e_pytorch_runtime.json", "tests/test_stage_s00e_hardening.py"],
        "E15": ["reports/engineering/s00e_source_mutation_check.json"],
        "E16": ["src/mosei/data/dataset.py", "tools/s00e_smoke.py"],
        "E17": ["tools/s00e_smoke.py", f"{run_base}/RUN.json"],
        "E18": [f"{run_base}/TEST_RESULTS.json"],
        "E19": ["reports/engineering/s00e_phase_d_review.json"],
        "E20": ["DECISIONS.md", "docs/data-guide.md", "docs/HANDOFF_WORKFLOW.md"],
        "E21": ["reports/engineering/s00e_prepublication_preflight.json",
                f"{run_base}/public/HANDOFF_INPUTS.json", "tools/s00e_preflight.py"],
    }
    verified = {"workspace": True, "authority": True, "source": True,
                "csv_removed": True, "scan": not tree["findings"] and not extra,
                "tests": tests["status"] == "PASS", "runtime": runtime["status"] == "PASS",
                "isolation": runtime["smoke"]["test_key_indexed"] is False and
                             runtime["smoke"]["attachment3_content_opened"] is False and
                             runtime["smoke"]["attachment4_content_opened"] is False,
                "q1_governance": [line for line in (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines()
                                  if line.startswith("| Q1-")] ==
                                 [line for line in git("show", f"{SAFETY_PRECOMMIT}:DECISIONS.md").splitlines()
                                  if line.startswith("| Q1-")] and
                                 all((ROOT / name).is_file() for name in
                                     ("docs/data-guide.md", "docs/HANDOFF_WORKFLOW.md"))}
    checks = {
        "E01": verified["workspace"], "E02": verified["authority"], "E03": verified["source"],
        "E04": verified["csv_removed"], "E05": verified["scan"],
        "E06": verified["tests"], "E07": verified["tests"], "E08": verified["tests"],
        "E09": verified["tests"], "E10": verified["runtime"],
        "E11": verified["runtime"], "E12": verified["runtime"], "E13": verified["runtime"],
        "E14": verified["runtime"], "E15": verified["source"],
        "E16": verified["isolation"], "E17": verified["isolation"],
        "E18": verified["tests"], "E19": False, "E20": verified["q1_governance"], "E21": False,
    }
    if not all(checks[code] for code in S00E_GATE_IDS - {"E19", "E21"}):
        raise RuntimeError("S00E prerequisite Gate evidence incomplete; no ready Gate written")
    gate = make_gate(run_id, evidence, checks)
    write_json(ROOT / f"{run_base}/GATE.json", gate)
    acceptance_paths = sorted(set(["docs/S00E_ENGINEERING_HARDENING.md", *[
        f"reports/engineering/{name}" for name in REPORT_NAMES],
        f"{run_base}/RUN.json", f"{run_base}/GATE.json",
        f"{run_base}/TEST_RESULTS.json", f"{run_base}/public/HANDOFF_INPUTS.json"] +
        [path for item in gate["items"] if item["status"] == "PASS"
         for path in item["evidence"]]))
    acceptance = {"task_id": TASK_ID, "stage": "S00E", "run_id": run_id,
                  "status": "READY_FOR_INDEPENDENT_REVIEW",
                  "data_kind": "real_official_local",
                  "evidence": [{"requirement": Path(name).name, "path": name,
                                "sha256": sha256(ROOT / name)} for name in acceptance_paths]}
    write_json(ROOT / "reports/stages/S00E/acceptance.json", acceptance)
    validate_acceptance(ROOT / "reports/stages/S00E/acceptance.json", "S00E",
                        task_id=TASK_ID, run_id=run_id, root=ROOT)
    final_tree = scan_tracked_public_tree(ROOT)
    final_pending = {name: issues for name in public_candidates()
                     if (issues := scan_public(ROOT / name))}
    if final_tree["findings"] or final_pending:
        raise RuntimeError("Final PHASE C public safety scan failed")
    review_diff(run_id)
    return {"run_id": run_id, "status": "READY_FOR_INDEPENDENT_REVIEW",
            "gate": gate["summary"], "tests": tests["passed"],
            "tracked_text_scanned": tree["scanned_text_files"],
            "safety_precommit": SAFETY_PRECOMMIT}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.run_id)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
