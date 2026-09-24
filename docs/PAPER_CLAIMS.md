# Paper claim evidence ledger

| Claim | State | Evidence | Limitation |
| --- | --- | --- | --- |
| Frozen aligned support/observed/padding contract exists | VERIFIED | docs/S00D_DATA_CONTRACT.md; DECISIONS.md | Operational first baseline contract; no final model selection |
| S00E safety and evidence repairs pass current full tests | VERIFIED tests and independent technical review | Current run TEST_RESULTS and subsequent independent review | Synthetic engineering checks are not sentiment accuracy |
| Tiny TRAIN Torch bridge/backward can run without source mutation | VERIFIED current CPU/CUDA run | reports/engineering/s00e_pytorch_runtime.json and source mutation report | No optimizer, epochs, validation/test predictions or model performance |
| Model predictive performance | UNKNOWN | No model run; metrics null | No Accuracy, F1, MAE or Pearson claims |
| S00E publication complete | BLOCKED | E19/E21 and Release receipt required | Ordinary governance push is not stage acceptance |


## Native local approval revision — 20260925-014500-S00E-ASTRA-d9e4edb

The owner explicitly approved the prior report/manifest, but that approval is not migrated to revised code. The local native Codex journal verifier now checks the fixed task identity, exact digest question, accepted tool call, and linked user reply on every invocation. Repository receipts are not authority. Trust assumes an uncompromised local Codex host and OS account; this is not cryptographic authentication. New actual validation: 217 main tests, 25 subtests separately; CPU/CUDA TRAIN smoke passed with unchanged source. Fresh independent review and owner confirmation are required before E19; E21 and Release remain blocked. No predictive metrics were produced.


## Junction repair checkpoint — 20260925-020000-S00E-ASTRA-d9e4edb

Independent review rejected the native approval path because Windows junctions are not symlinks. Adopted full original-path lstat reparse-point rejection before traversal/open; rejected trusting resolve/is_symlink alone. Permanent root/ancestor/intermediate/file regressions pass. Actual full collection/execution: 221 main tests and 25 separate subtests, exit 0. Targeted first attempt had one assertion-message mismatch (29 passed/1 failed); fixed the assertion, without weakening the rejection. CPU/CUDA smoke and source hash unchanged. New independent review and owner confirmation still required; no predictive metrics.


## Completed independent technical review

Current run `20260925-020000-S00E-ASTRA-d9e4edb`: independent Astra High review PASS, zero CRITICAL or blocking MAJOR. Reviewer independently ran 221 main tests and 25 subtests (exit 0), verified 58 hashes and replayed the junction rejection. Report SHA256 `26c74726eff8c52ad5a08e399c8c1d6f3e9dc577dd4f75ea7340829588e5d6d8`. User approval of this exact revised digest and E21 publication preflight remain pending. No further review expansion is planned. Model metrics remain null.
