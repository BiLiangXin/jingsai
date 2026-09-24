# Research and engineering log

## 2026-09-25 — serial local engineering closeout

- Verified official clone, origin, branch and fresh remote at 4bd0c6c; all prior CORE member hashes/current bytes matched. Preserved original reports locally before updating current summaries.
- Adopted GOV-ASTRA-SERIAL-01 per explicit user instruction: one Astra writer, real independent context, no web ZIP prerequisite. Four governance paths scanned/staged/committed/pushed; remote d9e4edb verified. Frozen research rows unchanged.
- Independent reviewer closeout_review used only synthetic temp fixtures and found three blockers. Author paused official writes during review.
- Red regression run: 8 failed and 23 passed. This confirmed missing scalar-plural scans and strict node-proof checks; no competition data was used.
- First full attempt 20260925-004100-S00E-ASTRA-d9e4edb: 198 collected/executed, 197 passed, 1 failed, 25 subtests passed, exit 1. The new CRLF publication test exposed Git diff whitespace classification. Kept the failure record and logs under that run/private. Fixed CRLF recognition while retaining trailing-whitespace checks.
- Adopted explicit typed SubtestReport detection, one main setup/call/teardown, source fingerprints before collection/before execution/after execution, exact index/Release byte comparison. Rejected the prior duplicate-call approximation and post-only hash snapshot.
- E19 signature verification checks live owner signing keys and canonical task/run/report/manifest bytes. Agent does not generate or enroll an owner key. Current owner signing-key lookup returned none, so real approval remains blocked. Synthetic signature tests use disposable local keys only.
- No model/loss/normalizer selection, optimizer, training, checkpoint or predictive metrics. Engineering evidence cannot support a model-performance claim.

- Fresh run `20260925-005000-S00E-ASTRA-d9e4edb`: 199 main tests passed, 25 subtests passed; collection/execution exit 0, all main phase sets verified. D2 subset 26 passed and belongs to the 199; not additional tests. CPU/CUDA actual tiny TRAIN smoke passed with unchanged source hash. No predictive metrics. Evidence source hashes are in TEST_RESULTS.json; no old runtime relabeling.

- Independent full review of the 199-test version: 199 main and 25 subtests independently passed, but review REPAIRS_REQUIRED on BOM/whitespace CSV headers and GH_HOST trust redirection. Original review/probe bytes retained. Adopted header normalization and explicit github.com trust host; rejected treating an all-green suite as sufficient review.
- New run 20260925-005500-S00E-ASTRA-d9e4edb: 202 main tests passed, 25 subtests separately, both exit codes zero. D2 subset 28 is included in 202. CPU and available CUDA real TRAIN batch two smoke rerun; source SHA256 unchanged. Awaiting another actual independent review.

## Final independent engineering checkpoint

The actual independent Astra High reviewer passed technical review with zero CRITICAL, blocking MAJOR or MINOR findings, independently reran 202 main tests plus 25 subtests, and verified all 58 frozen hashes. Exact report: reports/engineering/s00e_phase_d_review.json (SHA256 07061958304488982a2a8962c8dc4c634ac7766b0a2f47da2a10ce47f30dd131). Additional evidence-tampering, signature-tampering and corrupted Release-download checks passed. Production E19 remains MANUAL_REVIEW_APPROVAL_REQUIRED: the pinned github.com owner signing-key count is zero and no genuine owner signature exists. E21 and S00E Release are blocked; governance push alone is not completion. R01 cannot start; S01 is unauthorized. No Web Chat ZIP is required.

- Actual read-only E21 command exited 1 with BLOCKED because E19 was not passed. No Gate was temporarily rewritten, no publication called. Requested one local owner confirmation of the exact independent report and manifest digests under user instruction section 4. Without authenticated approval, the stage remains BLOCKED.


## Native local approval revision — 20260925-014500-S00E-ASTRA-d9e4edb

The owner explicitly approved the prior report/manifest, but that approval is not migrated to revised code. The local native Codex journal verifier now checks the fixed task identity, exact digest question, accepted tool call, and linked user reply on every invocation. Repository receipts are not authority. Trust assumes an uncompromised local Codex host and OS account; this is not cryptographic authentication. New actual validation: 217 main tests, 25 subtests separately; CPU/CUDA TRAIN smoke passed with unchanged source. Fresh independent review and owner confirmation are required before E19; E21 and Release remain blocked. No predictive metrics were produced.


## Junction repair checkpoint — 20260925-020000-S00E-ASTRA-d9e4edb

Independent review rejected the native approval path because Windows junctions are not symlinks. Adopted full original-path lstat reparse-point rejection before traversal/open; rejected trusting resolve/is_symlink alone. Permanent root/ancestor/intermediate/file regressions pass. Actual full collection/execution: 221 main tests and 25 separate subtests, exit 0. Targeted first attempt had one assertion-message mismatch (29 passed/1 failed); fixed the assertion, without weakening the rejection. CPU/CUDA smoke and source hash unchanged. New independent review and owner confirmation still required; no predictive metrics.


## Completed independent technical review

Current run `20260925-020000-S00E-ASTRA-d9e4edb`: independent Astra High review PASS, zero CRITICAL or blocking MAJOR. Reviewer independently ran 221 main tests and 25 subtests (exit 0), verified 58 hashes and replayed the junction rejection. Report SHA256 `26c74726eff8c52ad5a08e399c8c1d6f3e9dc577dd4f75ea7340829588e5d6d8`. User approval of this exact revised digest and E21 publication preflight remain pending. No further review expansion is planned. Model metrics remain null.
