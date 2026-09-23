# S00B data contract evidence

run_id: `20260924-001338-S00B-fc277357`
decision authority: Main Research Chat
next stage: `PENDING_RESEARCH_REVIEW`; `NEXT_STAGE_NOT_AUTHORIZED`

## VERIFIED

- Both official Attachment 2 feature PKLs have `train/valid/test = 3395/728/727`, total 4850 per version. Their complete observed field schemas, dtypes and shapes are recorded in `reports/data_audit/schema_aligned.json` and `schema_unaligned.json`.
- PKL `annotations` fields are absent. The official Attachment 2 `label.xlsx` supplied annotations for all 4123 train/valid IDs. No test annotation/label cell was accessed from this workbook.
- Train/valid `classification_labels` encode Negative/Neutral/Positive as 0/1/2. Regression, annotation, and classification agree; regression exactly zero equals Neutral. Regression finite values lie in `[-3,3]`.
- Exact IDs are unique, correctly parse with `$_$`, and have no cross-split overlap. `video_id` has no cross-split overlap. Aligned/unaligned have identical split ID sets and order, and equal label arrays. Test equality is a boolean only.
- The `text_bert` array is integer `(N,3,50)`. Channel 1 is binary with a contiguous active prefix in train/valid. Channel 2 is all zero. The numerical channels are described in `text_bert_diagnostics.json` without dumping token IDs.
- Aligned candidate-active positions and audio/vision structural zeros are quantified in `aligned_positional_diagnostics.json`. Inactive candidate positions have nonzero `text` feature rows. Aligned vision has internal zero runs, including within candidate-active positions.
- Unaligned length fields are integer-like and in range. Audio has no nonzero rows after declared length; vision has 36,928 train and 8,455 valid nonzero rows after it. Vision also has 30 train zero rows inside declared length.
- No NaN or Inf was found in text, audio or vision. Whole-vision-zero samples occur and were not removed.
- Attachment 1 has 100 videos in 37 video_id folders, 100 Excel label rows, all required columns, and matching video/label keys. Attachment 3 has 60 PKLs; Attachment 4 has 40 PKLs and 40 MP4s with per-version filename correspondence. Attachment 3/4 content was not inspected.
- Both Attachment 2 source files have unchanged size, mtime and SHA256 before and after audit. Public reports contain aggregate evidence only. Detailed test label distributions remain quarantined.

## SPECIFIED

- The competition specifies 4850 samples per feature version, 100 Attachment 1 videos, 37 video_id folders, ID form `video_id$_$clip_id`, regression range `[-3,3]`, and strict zero for Neutral. Observed totals match these stated counts. These specified claims and observed claims are recorded separately in the JSON evidence.
- S00B uses train/valid for full audit, test for limited integrity checks, and Attachment 3/4 for file-level inventory only under frozen decisions D-S00B-01 to D-S00B-04.

## INFERRED

- `text_bert` channel 1 is an `INFERRED_ATTENTION_MASK_CHANNEL` candidate based on binary values and contiguous active prefixes. It is not a final support or padding rule.

## HYPOTHESIS

- Structural zeros may reflect multiple mechanisms, including storage support, alignment and local feature absence. The present evidence does not distinguish these causes. No hypothesis is adopted as a data contract.

## UNKNOWN

- Whether any observed `ZERO_ROW` means missing: **UNKNOWN**. Whether any `ZERO_ROW` means padding: **UNKNOWN**.
- Final aligned/unaligned selection, support/observed masks, interpretation of nonzero unaligned vision after `vision_lengths`, and treatment of nonzero aligned text features at candidate-inactive positions require research review.
- No genuine token-to-time or feature-to-second mapping was established. The audit does not infer temporal evidence from position index.
- No final model input combination, standardization, training design, explanation method or next stage is authorized by this audit.

## Research review questions

1. What evidence should govern final support versus observed masks, given the vision-length and aligned text candidate-mask discrepancies?
2. Should the official unaligned `vision_lengths` be treated as descriptive metadata, and what independent validation would be required before using them as support boundaries?
3. How should whole-vision-zero and internal zero-run samples be represented without treating zero as missing by default?
4. Which feature version and later-stage research protocol should be frozen after review?

`PROPOSED_RESEARCH_CHANGE: NONE`. This audit records evidence and does not change D-S00B-01 through D-S00B-04.
