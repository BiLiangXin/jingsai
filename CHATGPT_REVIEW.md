# Current Review — S00C support boundary evidence

task_id: `S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF`
run_id: `20260924-014331-S00C-afeafae`
status: `SUCCESS`
repository: `BiLiangXin/jingsai`
branch: `codex/mosei-auto`
baseline_commit: `afeafaebd2d5a158ee1e5ce28c3e1233159e82ed`
previous_stage_implementation_commit: `b8f839bb32b8c75827d9cd20dc618885a35cde4f`
implementation_commit: `98f70db69f750c3f1b27b17f3c7fab25a0493d77`
metadata_commit: `ee7631abacdceac5aabf128e034c23404832200a`
release_url: `https://github.com/BiLiangXin/jingsai/releases/tag/codex-run-20260924-014331-S00C-afeafae`
release_tag: `codex-run-20260924-014331-S00C-afeafae`
review_asset: `review-20260924-014331-S00C-afeafae.zip`

## Real run and source integrity

VERIFIED: The S00C run read the two trusted official Attachment 2 feature PKLs sequentially and calculated only train/valid numerical diagnostics. Both before/after source fingerprints match; the current fingerprints also match the S00B published source records. No original file was modified. Test was not indexed for new diagnostics. Attachment 3/4 content was not opened. See `reports/runs/20260924-014331-S00C-afeafae/RUN.json`, public source hash records and `reports/data_audit/s00c_source_mutation_check.json`.

An earlier local attempt with a different run ID stopped at a report-layer lookup error after source integrity verification. Its evidence remains in its ignored private directory; it was never published. The corrected run `20260924-014331-S00C-afeafae` completed and independently reconciled 16 S00B facts.

The first automatic handoff invocation stopped in pre-Git validation because its porcelain status parser dropped a significant leading space. No Git write or Release occurred in that attempt. The parser and synthetic regression test were corrected before retrying; the failed attempt record remains in this run's ignored private directory.

## S00B baseline reproduction

VERIFIED: Both feature versions again have train/valid 3,395/728 samples. Unaligned audio has zero nonzero rows after declared length; vision has 36,928/8,455. Train vision has 30 zero rows inside declared length, all from 30 whole-zero sequences with declared length 1. Aligned candidate-active positions and inactive-nonzero continuous text counts also match. All 16 reconciliation checks are equal. See `reports/data_audit/s00c_s00b_reconciliation.json`.

## Targeted boundary results

VERIFIED: After-boundary vision nonzero rows occur in 618/3,395 train samples and 141/728 valid samples. No affected sample has a single nonzero row immediately at the declared boundary. The first nonzero offsets and extension lengths are heterogeneous, and median nonzero-row norms inside versus after are of similar magnitude. Audio supplies a contrasting zero-after-length pattern. The complete aggregate distributions and length bins are in `reports/data_audit/s00c_vision_length_boundary.json`.

INFERRED: The observed vision pattern does not fit a universal off-by-one or single fixed offset. UNKNOWN: whether post-length vision values are genuine observations, extraction artifacts or unusable values. A producer definition or independently verified feature-to-source alignment is needed. Official lengths were not replaced or reinterpreted as a final support rule.

## Aligned text and structural zeros

VERIFIED: Channel 1 of aligned `text_bert` is binary and continuous-prefix in every train/valid sample. Candidate-inactive continuous `text` has 86,078/17,772 nonzero rows. Tail repetition and row-norm distributions are in `reports/data_audit/s00c_text_mask_diagnostics.json`. INFERRED: channel 1 remains an attention-mask candidate only; it does not define final padding for continuous text.

VERIFIED: Exact-zero runs differ by modality and interface. Aligned vision has 110/15 whole-zero samples; unaligned vision has 30/0. Prefix, suffix, internal, multiple internal, candidate-active overlap and official-length boundary cross-statistics are in `reports/data_audit/s00c_zero_mechanism_matrix.json`. UNKNOWN: these zero structures do not establish padding, missingness or invalid observation.

## Tests, Gate and publication

Actual engineering test command: `python -m pytest -q tests` — 80 passed, 0 failed, exit code 0. Synthetic tests are separate from the real-data run. S00C Gate: 12/12 PASS, with no FAIL, SKIPPED or BLOCKED; see `reports/runs/20260924-014331-S00C-afeafae/GATE.json`. The public-file safety scan and Git raw-data protection check are recorded by the Gate. Release fields above are populated only after remote target, asset size and downloaded SHA256 verification.

## Research review boundary

Candidate data-contract meanings, alternatives, limits and independent evidence requirements are in `docs/S00C_SUPPORT_EVIDENCE.md`. Main Research Chat must decide whether and how to interpret vision lengths, text candidate mask and structural zeros. The existing `DECISIONS.md` remains unchanged. No aligned/unaligned final choice, missing/padding rule, model or S01 stage is approved.

`PROPOSED_RESEARCH_CHANGE: NONE`.

`PENDING_RESEARCH_REVIEW`
`NEXT_STAGE_NOT_AUTHORIZED`
`STOPPED_AFTER_S00C`

## Verified automatic handoff

Release target: `98f70db69f750c3f1b27b17f3c7fab25a0493d77`. Asset SHA256: `6de70cee0d776361e07acb68d1eed94044f7590498941a6f92c516bd2982dfe0`. Downloaded SHA256 matches. Stage remains `PENDING_RESEARCH_REVIEW`; `NEXT_STAGE_NOT_AUTHORIZED`.
