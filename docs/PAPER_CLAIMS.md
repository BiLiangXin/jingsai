# Paper claim evidence ledger

| Claim | State | Evidence | Limitation |
| --- | --- | --- | --- |
| Frozen aligned support/observed/padding contract exists | VERIFIED | docs/S00D_DATA_CONTRACT.md; DECISIONS.md | Operational first baseline contract; no final model selection |
| S00E safety and evidence repairs pass current full tests | VERIFIED tests and independent technical review | Current run TEST_RESULTS and subsequent independent review | Synthetic engineering checks are not sentiment accuracy |
| Tiny TRAIN Torch bridge/backward can run without source mutation | VERIFIED current CPU/CUDA run | reports/engineering/s00e_pytorch_runtime.json and source mutation report | No optimizer, epochs, validation/test predictions or model performance |
| Model predictive performance | UNKNOWN | No model run; metrics null | No Accuracy, F1, MAE or Pearson claims |
| S00E publication complete | VERIFIED | E19/E21, PUBLISH_RECEIPT and R01 prerequisite recheck | Current publication supersedes historical pending notes below |


## Native local approval revision — 20260925-014500-S00E-ASTRA-d9e4edb

The owner explicitly approved the prior report/manifest, but that approval is not migrated to revised code. The local native Codex journal verifier now checks the fixed task identity, exact digest question, accepted tool call, and linked user reply on every invocation. Repository receipts are not authority. Trust assumes an uncompromised local Codex host and OS account; this is not cryptographic authentication. New actual validation: 217 main tests, 25 subtests separately; CPU/CUDA TRAIN smoke passed with unchanged source. Fresh independent review and owner confirmation are required before E19; E21 and Release remain blocked. No predictive metrics were produced.


## Junction repair checkpoint — 20260925-020000-S00E-ASTRA-d9e4edb

Independent review rejected the native approval path because Windows junctions are not symlinks. Adopted full original-path lstat reparse-point rejection before traversal/open; rejected trusting resolve/is_symlink alone. Permanent root/ancestor/intermediate/file regressions pass. Actual full collection/execution: 221 main tests and 25 separate subtests, exit 0. Targeted first attempt had one assertion-message mismatch (29 passed/1 failed); fixed the assertion, without weakening the rejection. CPU/CUDA smoke and source hash unchanged. New independent review and owner confirmation still required; no predictive metrics.


## Completed independent technical review

Current run `20260925-020000-S00E-ASTRA-d9e4edb`: independent Astra High review PASS, zero CRITICAL or blocking MAJOR. Reviewer independently ran 221 main tests and 25 subtests (exit 0), verified 58 hashes and replayed the junction rejection. Report SHA256 `26c74726eff8c52ad5a08e399c8c1d6f3e9dc577dd4f75ea7340829588e5d6d8`. User approval of this exact revised digest and E21 publication preflight remain pending. No further review expansion is planned. Model metrics remain null.


## Verified S00E publication — 20260925-020000-S00E-ASTRA-d9e4edb

All 21 Gates passed, including actual independent review plus native exact-digest user approval and read-only E21. Existing stage_handoff completed ordinary implementation/metadata/index pushes and Release target/size/download SHA256 checks. Implementation 6480bfc77ce63edca92e6a57237772cddca0c3d0; metadata 27b026051c805f946e66e90a04bff603d7a01caa; index 7c1596dbe107d9e7b174b6e959941ddaf7c0f198; asset SHA256 e6cd31f0bb9af1ea6e79e5452645fec1afda2a296166db52f1e7fe41041625bf. R01 may resume; S01 remains unauthorized. No model performance claim.

Publication retained two ordinary failed attempts: intentional two-space Markdown line breaks initially failed whitespace formatting; an exact-file local Git attribute preserved approved report bytes. The first implementation push 92137f094cd2bd75a0182dc9fd8cefbdb61c6072 then stopped before Release because four governance documents had worktree CRLF versus Git LF. Setting local core.autocrlf=false preserved reviewed bytes in the ordinary follow-up implementation commit; no research text/code/hash changed, no history rewrite, no duplicate Release. No further review or research work was added.


## R01 evidence ledger — 2026-09-25

| Claim | State | Evidence | Limitation |
|---|---|---|---|
| R01 generator satisfies selected observed retention and finite fallback on checked synthetic cases | VERIFIED within finite reference cases | reports/research/R01_LOCAL_CLOSEOUT/checks.json; research/r01/reference.py | No NumPy/PyTorch implementation or data experiment; not a universal proof |
| 96 nominal conditions receive equal weight despite144views | INFERRED algebra; VERIFIED synthetic reduction | DESIGN §3/5 and checks | Requires actual ordered sample/view provenance from a future pipeline |
| C0/R0 comparison holds checkpoint policy constant | PROVISIONAL design; INFERRED identifiability improvement | DESIGN §5/8; protocol.json | No measured enhancement effect |
| R1/R2/R1-cap can test end-to-end fusion strategies | HYPOTHESIS | DESIGN §4; finite trials | Co-adaptation remains; not causal modality contribution |
| CE large-common-offset regression is corrected | VERIFIED synthetic counterexample and check | test_closeout.py and checks.json | No gradient/runtime/model test |
| Final seed17 obeys the proposed measured clean guard or reverts to B*17 | INFERRED rule; VERIFIED synthetic cases | select_final and checks | Future valid estimates remain noisy; no population guarantee |
| Gate improves prediction under missing data | UNKNOWN | All model trials NOT_RUN, metrics=null | Must not appear as a result or innovation claim |
| Known-mask simulation deploys to Attachment3 | UNKNOWN | DESIGN §2 | Reliable S/A not confirmed; no special data opened |
| Complete Q2/Q3 solved or any official model score exists | UNKNOWN | No authorized model experiment | Main96 omits TAVlocal; Q3 pending |

Sources opened and scopes verified in docs/research/R01/SOURCES.md and sources.json. External paper scores are not competition evidence. Protocol freeze and owner approval remain pending; independent technical review is not approval. Future registry entries must retain every config/seed/attempt, including failures and nonimprovements, not only successful/best seeds.
