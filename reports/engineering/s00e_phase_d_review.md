# Independent S00E technical re-review

Run: `20260925-020000-S00E-ASTRA-d9e4edb`  
Reviewer: independent GPT-6 Astra / High  
Technical result: PASS. 0 CRITICAL, 0 blocking MAJOR, 0 MINOR findings identified in the necessary review scope.

Production E19 approval remains pending. This technical report does not grant user approval, E21 success, publication or S01 authorization. The new report and manifest require a genuine matching owner confirmation. Earlier confirmation cannot be transferred to this changed version.

## Necessary scope and actual execution

This review builds on the completed independent review of the shared S00E data contract, scanner, test evidence, Gate, preflight, staging, Review Release and index implementation. The new review examined native approval event parsing, fixed host identity/root discovery, the explicit local host trust boundary, affected tests and the subsequent junction repair. Following the user's latest request, checks were narrowed to the confirmed safety defect, version/evidence consistency and approval isolation; no further risk-surface expansion was performed.

The former NATIVE-R01 is resolved. The verifier now calls reject_redirected_path before resolving the sessions root and before opening each discovered journal. The helper lstat-checks the original path and every ancestor and rejects symlinks and Windows FILE_ATTRIBUTE_REPARSE_POINT. Independently repeated the original actual Windows directory-junction attack at the sessions root and at an ancestor: both now reject. Permanent tests additionally cover intermediate directory and file reparse flags. Normal synthetic journal approval remains a positive control.

All 58 frozen snapshot hashes independently match current files and remained unchanged through review. Current private pytest collection/execution proofs validate against the public TEST_RESULTS, typed subtest markers and current code hashes. The recorded 28 D2 tests are a subset of the main total. The full independent suite was started before the user narrowed the checks and was allowed to finish: 221 main tests and 25 subtests passed, exit 0, 29.06 seconds. Command: `python -B -m pytest -q -p no:cacheprovider --basetemp <OS_TEMP>/pytest-temp tests`. Bytecode and pytest cache writes were disabled; all test outputs remained in OS temporary storage. No additional full run was started.

The tracked public text scan checked 121 files without findings. All 80 manifest-listed existing files scanned clean. Existing final-review filenames are replaced only by the new verbatim reviewer artifacts; an old run's review at the same filename does not approve the current run.

## Native event and approval isolation

The parser requires an exact question containing task/run/report/manifest digests, a native request_user_input_async call, its accepted acknowledgement, a later role=user input_text reply, the matching tool/call/question-item identity and the exact answer. Ambiguous duplicate requests or replies, malformed events, unrelated agent/tool messages, rejection and stale questions fail closed. Additional independent probes rejected integer acknowledgement values, duplicate acknowledgements, boolean question indices, wrong tool identity, prefixed quoted reply text and an old-run question. These diagnostics are separate from pytest totals.

The production native reader was exercised read-only against an unapproved question for the new run; it refused approval. No native paths, unrelated messages or raw journal contents are included in public artifacts. No production native record was written or synthesized. The fixed profile API and original-component reparse checks prevent environment or junction substitution of the native source.

The approved design trusts the local Codex host journal and OS account. It is explicitly not cryptographic authentication and does not claim protection from an attacker already able to rewrite trusted host files or compromise the account. SSH verification remains an alternative. A copied repository receipt, this technical PASS JSON, or a synthetic test event is not a production approval source.

## Evidence and remaining steps

Authoritative reviewed_files binds immutable implementation and key test files. review_evidence_sha256 binds the actual current TEST_RESULTS, runtime/source/D2 reports and this review/probe pair. The complete 58-file audit snapshot is separate because publication metadata and status documents are expected to change. Current real CPU/CUDA TRAIN smoke evidence was examined as recorded evidence; no official data or local configuration was opened and no official smoke was rerun by this reviewer.

Copy the independent artifacts byte-for-byte, update acceptance with their hashes, obtain one genuine native or signed owner confirmation of the final report and manifest, then run the actual E21 preflight and authorized publisher. Preserve the reviewed code and immutable test/runtime/probe bytes. No production approval, Git mutation, Release operation or stage completion was performed in this review. Existing historical-data-access and installed-package-origin limitations were not expanded into new blocking work.
