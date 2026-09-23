# S00C support boundary evidence

task_id: `S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF`
run_id: `20260924-014331-S00C-afeafae`
research authority: Main Research Chat
stage outcome: `PENDING_RESEARCH_REVIEW`; `NEXT_STAGE_NOT_AUTHORIZED`

## Scope and method

This is a targeted read-only numerical diagnosis of official Attachment 2 train and valid. The two trusted local PKLs were loaded sequentially. No S00C computation indexed test, opened Attachment 3/4, used external labels, trained a model, or changed the source arrays. Exact-zero rows retain the S00B mechanical definition: every feature component equals zero. Official declared lengths, numerical nonzero positions, candidate support, genuine observation and modality missingness are separate concepts.

Public outputs contain aggregate counts, histograms and quantiles. Ordered per-sample length diagnostics remain in the run's Git-ignored `private` directory. The public source integrity record contains only file names, sizes, mtimes and SHA256. The computations are implemented in `tools/s00c_run.py`, `tools/s00c_vision.py` and `tools/s00c_text_zero.py`.

## VERIFIED

- The local and remote official branch matched the activated S00C specification before loading data. Both source fingerprints matched the published S00B post-audit fingerprints before deserialization and were unchanged after this run. Evidence: `reports/data_audit/s00c_source_mutation_check.json` and the run's public hash records.
- Aligned and unaligned each supplied train 3,395 and valid 728 samples. Sixteen independent S00B count, length and aligned candidate-position checks all matched. The S00B reports and computations were read unchanged. Evidence: `reports/data_audit/s00c_s00b_reconciliation.json`.
- Unaligned vision has 36,928 train and 8,455 valid nonzero stored rows at or after official `vision_lengths`, across 618/3,395 and 141/728 samples. Its after-boundary nonzero rows form 1,794 and 465 contiguous runs, with 1,176 and 324 zero gaps between runs. The first after-boundary nonzero offset has median 2 and 3 rows, respectively; offset zero never occurs. No affected sample fits the exact one-row, immediate-boundary off-by-one pattern. Extension beyond the declared boundary varies: the modal extension covers only 13/618 train and 4/141 valid affected samples. Evidence: `reports/data_audit/s00c_vision_length_boundary.json`.
- Train vision has 30 whole-sequence-zero samples, each with declared length 1; valid has none. This reproduces the 30 declared-inside zero rows in S00B. S00B's inside-slice `whole` classification explains why its leading/internal-inside counts are zero. No sample was removed. Evidence: vision boundary report and `reports/data_audit/s00c_zero_mechanism_matrix.json`.
- Median L2 norm of nonzero vision rows inside versus after declared length is 14.933 versus 14.716 for train and 14.811 versus 14.740 for valid. These are numerical magnitudes, not observation labels. After-boundary nonzero rows are distributed across hundreds of samples; the largest 5% of all samples account for 62.8% and 58.6% of such rows. Length-bin tables show frequency varies by declared length. Evidence: vision boundary report.
- Unaligned audio has zero nonzero rows after declared length and zero zero rows inside declared length in both train and valid. Its stored zero-run structure differs from vision. Evidence: vision boundary report, zero mechanism matrix and S00B reconciliation.
- Aligned `text_bert` is integer `(N,3,50)`. Channel 1 is binary and has a continuous active prefix for every train/valid sample; aggregate candidate-active positions total 83,672/18,628. Every candidate-inactive continuous `text` row is numerically nonzero: 86,078/17,772 rows. Median row L2 norm is 14.726/14.697 inside the candidate-active region and 9.936/9.904 outside it. Among adjacent candidate-inactive row pairs, exact equality occurs zero times; cosine similarity at least 0.999 occurs 32/82,936 and 7/17,091 times. Evidence: `reports/data_audit/s00c_text_mask_diagnostics.json`.
- Aligned vision has 110/15 whole-zero samples and 210/68 internal zero runs in train/valid; candidate-active vision zero positions number 11,039/2,436. Aligned audio has no whole-zero samples and no internal zero runs, while candidate-active audio zero positions number 6,855/1,502. Unaligned vision has 1,794/465 stored internal zero runs and 30/0 whole-zero samples; unaligned audio has no stored internal zero runs. These are numerical patterns, not missing/padding classifications. Evidence: zero mechanism matrix.

## SPECIFIED

- S00C permits new numerical diagnosis on official Attachment 2 train/valid only. Test remains quarantined; Attachment 3/4 content is out of scope. No model training, final aligned/unaligned choice, final support/missing definition or S01 work is authorized.
- Official `audio_lengths` and `vision_lengths` are declared lengths. They do not by themselves prove that every row after the boundary is padding or that every row before it is a genuine observation.

## INFERRED

- `text_bert` channel 1 is an attention-mask **candidate** because it is binary and forms a continuous active prefix in both observed splits. The candidate does not define padding for continuous `text` features.
- The measured vision discrepancy is not explained by a universal one-row or single fixed offset: the immediate boundary row is zero in affected samples and extension offsets are heterogeneous. This inference is limited to those simple offset explanations.
- Similar inside/after vision row-norm magnitudes show that after-boundary nonzero values are not uniformly tiny numerical noise. Magnitude alone cannot establish their provenance or validity.

## HYPOTHESIS

- After-boundary vision values could reflect retained feature extraction outputs, alignment or storage conventions, length metadata with a different intended meaning, or another mechanism. These alternatives remain untested by an independent source of frame/feature timing or producer documentation.
- Candidate-inactive continuous text values could arise from contextual encoding or feature storage conventions. No token recovery or re-encoding was performed, so this is not a final text support interpretation.

## UNKNOWN

- Whether any individual after-boundary vision row is a real source observation, an extraction artifact, or unusable for modeling remains unknown. A producer data dictionary, feature-to-source alignment, or independently verified extraction trace would be needed.
- Whether any structural zero denotes padding, local missingness, invalid observation or a legitimate zero feature remains unknown. Official length metadata, zero rows and candidate text mask are not interchangeable.
- The final feature version, support/observed masks and any later model or corruption design require Main Research Chat review. No decision in `DECISIONS.md` is frozen by this report.

## Research decision candidates for owner review

| Candidate meaning | Supporting evidence | Alternative explanation | Additional independent evidence needed |
| --- | --- | --- | --- |
| Treat official unaligned vision length as descriptive metadata pending validation | Nonzero rows occur after it in 618/141 samples, with heterogeneous offsets | Post-length values may be synthetic or unusable outputs | Producer semantics or verified feature-to-frame trace |
| Keep channel 1 as a text mask candidate only | Binary continuous prefix in every observed train/valid sample | Continuous `text` may retain meaningful contextual values beyond it | Feature-generation documentation or authorized extraction trace |
| Keep structural zeros separate from missingness | Whole-zero, end-zero and internal-zero patterns differ by modality/version | Some zero runs may ultimately encode missingness or support | Independently documented encoder/padding rules and authorized later experiments |

These are review candidates, not adopted research decisions. `PROPOSED_RESEARCH_CHANGE: NONE`.
