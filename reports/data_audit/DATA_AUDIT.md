# S00B real data audit

run_id: `20260924-001338-S00B-fc277357`
baseline: `fc277357e9583190d6be786221b8b3407fa957f8`
data_kind: `real_official_local`
scope: Attachment 2 aligned and unaligned; Attachment 1 integrity; Attachment 3/4 file metadata only.

## Source and quarantine

The user-confirmed local official `aligned_50.pkl` and `unaligned_50.pkl` were opened read-only with `trusted_competition_pickle=true` in a gitignored local config. Both files have identical size, mtime and SHA256 before and after the audit; see [source mutation check](source_mutation_check.json). No official file was modified. Public paths are redacted as `<LOCAL_DATA_ROOT>`.

`test` was limited to schema, sample count, IDs, finite values, label field existence/shape/legal range, and aligned/unaligned identity and label equality. `TEST_LABEL_DISTRIBUTION_QUARANTINED=true`. No test label distribution or sample-level label appears in a public output. Attachment 3 and 4 contents were not opened.

## Verified schema and counts

Both versions are dictionaries with `train`, `valid`, `test` splits of 3395, 728 and 727 rows, totaling **4850** in each version. This equals the competition's specified 4850, without adding the two versions together. Every sample-aligned field has a matching first dimension. Both have `id`, `raw_text`, `text`, `text_bert`, `audio`, `vision`, `classification_labels`, `regression_labels`. Neither PKL has `annotations`. Unaligned additionally has `audio_lengths` and `vision_lengths`.

The observed `text` shape is `(N,50,768)` and `text_bert` is integer `(N,3,50)` in both versions. Aligned `audio` and `vision` are `(N,50,74)` and `(N,50,35)`; unaligned are `(N,500,74)` and `(N,500,35)`. Full dtype and field details are in the two schema JSON files. No field's first dimension was inconsistent.

## IDs and labels

All IDs parse as `video_id$_$clip_id`, with zero empty, malformed or duplicate IDs. Exact ID overlap and video_id overlap between every pair of splits are both zero. Aligned and unaligned have equal ID sets and order in each split. Public reports provide aggregate counts only.

The official Attachment 2 `label.xlsx` has 4850 data rows. Only train/valid label and annotation cells were accessed; all 4123 train/valid IDs matched. The verified encoding is `Negative=0`, `Neutral=1`, `Positive=2`. Train/valid regression values are finite and within `[-3,3]`; strict regression zero and Neutral agree in every audited row. Regression sign, annotation and classification mapping have zero discrepancies. The two PKL versions have equal labels for all splits; for test only the equality boolean is reported.

## Structural zeros and candidate position evidence

`ZERO_ROW` means every feature dimension is exactly zero. It is a mechanical observation, not a missing or padding definition. Full per-position counts, sample zero-count histograms, run classifications and length bins are in the CSV/JSON outputs.

| Version / split | Audio zero rows | Vision zero rows | Vision internal zero runs | Whole-vision-zero samples |
| --- | ---: | ---: | ---: | ---: |
| aligned train | 92,933 | 97,117 | 210 | 110 |
| aligned valid | 19,274 | 20,208 | 68 | 15 |
| unaligned train | 1,197,456 | 1,344,017 | 1,794 | 30 |
| unaligned valid | 251,806 | 283,697 | 465 | 0 |

No `text` feature row is exactly all zero in train or valid. In `text_bert`, channel 1 is binary with a contiguous active prefix and is an **inferred** attention-mask candidate. This is not a final token, support or padding rule. Aligned candidate-active positions total 83,672 train and 18,628 valid. Inactive candidate positions still have nonzero `text` features. Inside candidate-active positions, audio has 6,855/1,502 zero rows and vision has 11,039/2,436 zero rows for train/valid. The full contingency is in [aligned positional diagnostics](aligned_positional_diagnostics.json).

Unaligned `audio_lengths` and `vision_lengths` are integer-like and within `[0,500]`. Audio has zero nonzero rows after its declared length. Vision has **36,928 train and 8,455 valid nonzero rows after declared length**, and 30 train zero rows inside declared length. This discrepancy is evidence for research review; it does not authorize a new length, padding or missing rule. See [length consistency](length_consistency_unaligned.json).

There are no NaN or Inf values in any audited modality. The test finite check is reported only as existence and total count. Whole-vision-zero samples are retained and reported as data-quality evidence.

## Cross-version and attachments

Train/valid annotations, classification and regression labels, raw_text hashes/equality, and text features agree between aligned and unaligned. Test identity and label equality are true; no detailed test comparison is published. Text feature comparison was safe within memory and yielded exact equality and max absolute difference 0 for train/valid.

Attachment 1 has 100 MP4 files in 37 video_id folders, plus `label-100.xlsx` with 100 data rows and all five required columns. Video keys and label rows match with zero unmatched or duplicate keys. These observed values match the competition-specified expectations.

Attachment 3 contains 60 PKL files, 30 in each aligned/unaligned version directory. `CONTENT_NOT_INSPECTED=true`.

Attachment 4 contains 40 PKL and 40 MP4 files, 20 matched feature/video stems in each version. `FEATURE_CONTENT_NOT_INSPECTED=true` and `VIDEO_CONTENT_NOT_INSPECTED=true`.

## Interpretation boundary

The observed zeros, inferred attention-mask channel and declared length behavior do **not** establish final padding or missing semantics. No model training, feature extraction, video analysis, aligned/unaligned selection or later-stage research was performed. Main Research Chat must review these facts before freezing subsequent definitions.
