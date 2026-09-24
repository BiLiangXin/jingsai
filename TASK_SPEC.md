task_id: S00E_S01_PRESTART_ENGINEERING_HARDENING
status: ACTIVE
research_authorized: true
next_stage_authorized: false
previous_stage: S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS
stage_type: engineering_hardening
research_owner: Main Research Chat
execution_agent: Codex
task_version: 1.0
baseline_verified_head: 6dec2bdad55c8733d3abe6c61cb1b2212b183d57
activation_scope: SPECIFICATION_ONLY
s01_training_authorized: false

# S00E: S01 pre-start engineering hardening — ACTIVE_FROZEN

User authorized engineering repair after Main Research Chat's full S00D code review. This document ACTIVATES S00E ONLY. It does not declare that its implementation, tests, real official smoke test, Gate, Git publication or Review Release have occurred. S00D remains the last COMPLETED verified stage until S00E is actually executed and audited. S01 training and all subsequent research stages remain NOT AUTHORIZED. Follow AGENTS.md before this task. If AGENTS or an existing FROZEN research decision conflicts with this document, stop with PROPOSED_RESEARCH_CHANGE instead of weakening the invariant.

## 1. Model checkpoints; switching is MANUAL, never presumed

The Codex host cannot switch model automatically merely because a prompt requests it. Complete one phase and STOP at each MODEL_SWITCH_REQUIRED checkpoint; ask the user to switch model/reasoning setting and explicitly continue in the verified official repo. Do not claim a phase used a model that you did not actually use.

PHASE A: GPT-6 Sol / Medium — verify exact repository, state, scope and environment; read all relevant code and evidence.
PHASE B: GPT-6 Astra / High — independently review the proposed engineering repair, security boundaries and frozen data-contract semantics BEFORE implementation.
PHASE C: GPT-6 Sol / High — implement frozen repair plan, diagnose ordinary engineering faults, rerun tests and perform real PyTorch smoke.
PHASE D: GPT-6 Astra / High — independent final code/security review; return to PHASE C for any blocking defects.
PHASE E: GPT-6 Sol / Medium — run final tests/Gate, safe Git and Release handoff, verify checksums, generate fresh local Web Chat bundle; STOP pending Main Research Chat review.

MODEL_SWITCH_REQUIRED checkpoints are hard pauses. No S00E full-run continuation under the wrong selected model. If a requested model is unavailable, report MODEL_UNAVAILABLE; await user decision. Do not silently substitute. No xhigh/max is necessary for this engineering-only stage. GPT-6 Astra / xhigh remains reserved for separately authorized future algorithmic research.

## 2. Official workspace and provenance

Official repository BiLiangXin/jingsai; branch codex/mosei-auto. Last verified pre-activation HEAD: 6dec2bdad55c8733d3abe6c61cb1b2212b183d57. Before acting, read AGENTS.md, DECISIONS.md, TASK_SPEC.md, CHATGPT_REVIEW.md, state/LATEST_RUN.json, state/NEXT_ACTIONS.md, docs/S00D_DATA_CONTRACT.md, docs/S00C_SUPPORT_EVIDENCE.md, docs/DATA_CONTRACT_EVIDENCE.md, docs/HANDOFF_WORKFLOW.md, docs/data-guide.md, relevant project problem statement, src/mosei/data/*, src/mosei/provenance.py, tools/s00d_contract_run.py, tools/s00d_finalize.py, tools/stage_handoff.py, tools/web_chat_handoff.py, tools/mosei_flow.py, all directly related tests, S00D real run/Gate/release receipt.

Check git status --short, origin, branch, HEAD and local-only official-workspace marker. Verify TASK_SPEC.task_id == S00E_S01_PRESTART_ENGINEERING_HARDENING, status ACTIVE, research_authorized true, next_stage_authorized false. On a clean local checkout behind this activated remote branch, fetch and fast-forward only. If dirty, diverged, or remote changed, STOP and report; no hard reset, destructive clean, parallel E-S00E directory, force push, history rewrite or unrelated edits. Treat the prior model-schedule-only JSON as ENGINEERING_SCHEDULE_UPDATE, not evidence that S00E ran.

## 3. Immutable research/data boundaries

Preserve D-DATA-01 through D-DATA-07 exactly: aligned_50.pkl is the controlled first-baseline interface, not the final winner. shared support = text_bert channel 1 == 1; observed text = support; audio/vision observed = support AND NOT exact whole-feature structural zero; operational padding = NOT support; STRUCTURAL_ZERO is never automatically missing, padding or artificial corruption. Train only fits learned parameters/statistics; valid is for later model selection, not fit; test remains quarantined; Attachments 3/4 are not opened. Never infer sample labels/missing from feature values. Do not train or evaluate a model, select architecture/normalizer, design missing simulation/distillation/reconstruction, or generate predictive metrics. One tiny real official TRAIN minibatch is permitted solely for PyTorch data bridge/pooling/backward smoke with a throwaway linear tensor operation; no epochs, model performance or checkpoint. Official sources are read-only, record before/after source SHA256 and stop on mutation.

## 4. PHASE B: repair-plan review (GPT-6 Astra / High)

Before implementation, inspect code and tests for (a) current-tree sample-level CSV exposure and document backlinks; (b) AlignedBatch semantic mask invariants; (c) overflow in conversion to float32; (d) publisher accepting mandatory SKIPPED or inconsistent Gate summaries; (e) manifest-only scan missing pre-existing tracked public text files; (f) PyTorch bridge / masked pooling missing positive runtime verification, aliasing and NaN masking; (g) hardcoded S00D executed-test count; (h) out-of-date data-guide status and Q1 governance synchronization. Produce an internal repair plan and severity/verification matrix. If anything requires changing data split usage, label meaning, support/padding/missing interpretation, aligned/unaligned baseline status or test/Attachment 3/4 policy, create PROPOSED_RESEARCH_CHANGE with current_decision, proposed_change, reason, expected_benefit, risk, required_evidence, STOP and await Main Research Chat approval.

## 5. PHASE C: repairs (GPT-6 Sol / High)

5.1 Current public tree: the existing tracked docs/samples/labels-100.csv and docs/samples/labels-feature-first10.csv contain sample-level IDs, text and labels inconsistent with current public safety policy. Remove them from the CURRENT development branch using ordinary Git deletion after confirming no unrelated changes. Remove links and any sample-level excerpts from docs/data-guide.md. DO NOT rewrite history, delete tags, modify main or falsely claim historical erasure; explicitly record CURRENT_TREE_REMOVAL != HISTORICAL_ERASURE. If historical access requires further action, report PROPOSED_SECURITY_ACTION without executing it. Do not create alternate public dumps.

5.2 A clean, separately verified, ordinary governance/safety precommit is required BEFORE using stage_handoff for S00E: current stage_handoff's public_files validation accepts only EXISTING files and its worktree-change preflight rejects unlisted deletions; it cannot itself publish deletions of legacy CSV files. Stage only exact deletion paths and reviewed docs/DECISIONS updates after scan, make an ordinary safety-governance commit and push with remote HEAD verification. Never use git add . or -A. Record this precommit SHA separately from the later S00E implementation/release target. Never circumvent mandatory actual tests or Gate to create a stage completion claim.

5.3 Whole tracked-public-text-tree scan: implement a pre-publish scanner of tracked current-tree .md/.json/.csv/.py/.toml/.yaml/.yml (using git ls-files plus worktree/index status correctly), including files outside current handoff manifest. Reject forbidden sample-level CSV columns, raw text arrays, sample-level labels/IDs, secrets, private config/paths, illegal test distributions; ensure staged additions are scanned and tracked deletions are not mistakenly treated as unresolved. Do not scan or misclassify binary PNG/DOCX as UTF-8 text. Reconcile suspicious existing files rather than deleting useful evidence blindly. Fail closed before Git publication; test manifest-safe plus unrelated tracked unsafe CSV detection.

5.4 Batch semantic validation: strengthen AlignedBatch.from_arrays to verify mask boolean shape and all frozen equalities: same shared support for 3 modalities, padding == NOT support, text_observed == support, audio/vision structural-zero masks exactly match underlying feature tensors, and audio/vision observed == support AND NOT structural_zero. Reject forged but shape-valid AlignedMaskSet. Validate source finite and POST-float32-cast finite; include adversarial finite-float64-to-infinite-float32 test. Avoid mutating source arrays.

5.5 Harden stage_handoff.validate_run: for current all-mandatory stage gate, reject FAIL, BLOCKED, SKIPPED, non-PASS status, missing gate.items, inconsistent summary and item status/count, PASS=0 and duplicate IDs; do not silently skip unrun work. Future optional Gate semantics require explicit separate authorization. Fix any publisher tests that relied on fake or incomplete gate fixtures. Existing S00D published data and Gate must remain unchanged.

5.6 PyTorch runtime: obtain/import stable official torch in verified local environment if necessary; log Python, torch/CUDA versions and device. Exercise official aligned TRAIN tiny batch through AlignedBatch.to_torch(), verify model_inputs and targets separation, shapes and dtypes, CPU path and GPU only if available. Exercise actual torch masked_mean, trivial throwaway nn.Linear and backward, finite gradients and invariance of pooled outputs to arbitrarily large values outside support. Make torch pooling mask with masked_fill/where instead of 0 * possible NaN; test non-support NaN isolation and preserve active-region nonfinite detection. Check torch.from_numpy aliasing and ensure original NumPy batch and source remain unchanged after any synthetic in-place adversarial attempt; select and document a safe bridge behavior. NO epoch training, external weights, official valid/test metrics or checkpoints. If safe official torch runtime cannot be established, BLOCK, not synthetic-success.

5.7 Remove false test-count evidence: replace s00d_finalize.py's s00d_contract_test_count = 36 constant with actual pytest collection/execution evidence; keep archived S00D evidence immutable. Update tests and documentation without claiming a historical rerun.

5.8 Sync prior-approved Q1 official clarification to DECISIONS.md as project governance, separately from S00E experiments: attachment1 audio source actual MP4 soundtrack; text source official label-100.xlsx:text; vision source MP4 frames; retain all 100 by default even when audio/text inconsistent, silent, non-English or unclear/no human face. Enumerate uncertainty states without assuming every anomaly is natural missing; never fabricate forced audio-text alignment. Exact Q1 missing mapping remains UNDECIDED. Source: user-supplied competition forum expert reply of 2026-09-24; retain provenance and distinguish supplied clarification from reverified source. Publish rules only, no example sample IDs.

5.9 Update docs/data-guide.md only to reflect actually verified S00B/C/D audit facts and actual ID separator '$_$'; remove pre-audit false statements. Do not rewrite archived reports or old release artifacts.

## 6. Tests and 21 mandatory S00E Gates

New synthetic regression tests must cover: tracked unsafe unlisted CSV / safe text / binary exclusion; gates containing skipped items and summary/item inconsistency; each mask semantic mismatch (support/observed/padding/structural zero), post-cast overflow; torch real bridge, padding large-value and NaN masking, backward gradients and NumPy immutability; dynamic pytest count; CSV current-tree untracked; source read-only; test and Attachments 3/4 isolation; Q1 docs no sample-level excerpts. Run full 'python -m pytest -q tests' and record actual collected/executed counts and exit status, not guessed 116 or 36. Report torch runtime smoke evidence separately from synthetic tests.

S00E Gate E01–E21, each with explicit evidence, all must PASS:
E01 verified official workspace; E02 active S00E authority; E03 S00D dependency and source baseline; E04 unsafe sample CSVs absent from CURRENT tracked branch; E05 whole tracked public text scan clean; E06 exact batch semantic masks checked; E07 post-float32 finite validation; E08 skipped/inconsistent Gate fail-closed; E09 dynamic actual test collection evidence; E10 official stable PyTorch import/runtime; E11 real-to-torch smoke; E12 torch masked pooling smoke; E13 tiny backward/finite gradients; E14 NumPy batch unchanged; E15 official TRAIN source fingerprint unchanged; E16 test quarantine; E17 Attachment 3/4 isolation; E18 full pytest passes; E19 independent Astra final review reports no CRITICAL or blocking MAJOR; E20 docs and Q1 governance sync; E21 scanned safe automatic handoff. NO FAIL/BLOCKED/SKIPPED is allowed for SUCCESS.

## 7. Independent PHASE D review (GPT-6 Astra / High)

Review the full DIFF against the exact activation baseline and updated ordinary safety precommit. Review code, tests, evidence, accidental data exposure, publisher bypasses, correctness of computed gate, torch alias safety, contract meaning and no new split leakage. Mark CRITICAL, MAJOR, MINOR with files/lines and confirmed reproduction where possible. If any CRITICAL/blocking MAJOR, STOP publication, return to Sol High repair and rerun tests, then repeat Astra High review. This model handoff requires explicit user switch, not a claim in a report. Record review evidence without disclosing internal model reasoning.

## 8. PHASE E evidence and handoff (GPT-6 Sol / Medium)

Create unique run_id and safe docs/S00E_ENGINEERING_HARDENING.md, public aggregated reports/engineering/s00e_public_tree_scan.json, s00e_pytorch_runtime.json, s00e_contract_hardening.json, s00e_security_findings.json and s00e_source_mutation_check.json; reports/runs/<run_id>/RUN.json, GATE.json, TEST_RESULTS.json, public/HANDOFF_INPUTS.json; reports/stages/S00E/acceptance.json. Keep any raw test log, local paths or private diagnostics gitignored; no raw sample IDs, labels, raw text, private paths, protected data or model checkpoints in public outputs. Real official TRAIN smoke means RUN.data_kind='real_official_local' only when genuinely executed; otherwise stage is BLOCKED.

After repairing the gate and tracked-tree scanners, verify ordinary safety precommit has been pushed and local HEAD matches remote. Use ONLY the existing authorized tools/stage_handoff.py --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json with exact existing public files. It must check verified workspace, S00E authority, actual tests, all mandatory Gate PASS, source hash, public safety, exact staging, ordinary push, implementation commit, Release target and downloaded asset SHA256, metadata and latest index. Distinguish activation SHA, safety-governance precommit SHA, implementation SHA, metadata SHA and index HEAD. Generate a NEW safe local Web Chat handoff ZIP according to AGENTS.md; ZIP is convenience, not a new authorization. Do not push raw private files, use force push or history rewrite.

On genuine completion report PENDING_RESEARCH_REVIEW, NEXT_STAGE_NOT_AUTHORIZED, S01_NOT_STARTED, STOPPED_AFTER_S00E. If work cannot complete, report BLOCKED with truthful partial Git/Release state; no invented SUCCESS. Return latest CHATGPT_REVIEW.md, run_id, new commit SHAs, actual tests/Gate, any security findings and actual release evidence to Main Research Chat. STOP; do not self-authorize S01.
