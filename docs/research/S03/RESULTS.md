# S03 readiness evidence

Current stage in progress. No new training fits. Source S02 champion M2seed17, epoch2 preserved. Historical S01/S02 evidence and unrun R01 alternatives are unchanged. Configuration and fixed protocols are recorded before new deployment/explanation results.

## Completed prerequisites

VERIFIED: independent backup of356 S01/S02 campaign files,202284794 bytes, actual per-file SHA256 and size comparison. All model weights, scalers, logs, caches and epoch records are included; private manifest is not published. BACKUP.json records the manifest hash. Restoration on728 clean VALID rows exactly reproduces saved logits and regression tensors, maximum absolute error0, parameters/buffers unchanged. RESTORE.json binds checkpoint and scaler.

The aligned pickle is monolithic: unpickling materializes its container, including test objects. Only allowlisted VALID fields are selected by the original adapter; no test labels/predictions/selection are evaluated. This limitation is disclosed rather than claiming that no test object ever entered RAM.

## Q2 figures and findings

VERIFIED:148 completed epochs across12 fits; every fit's epochs continuous and final selected checkpoint sourced from FITS.json. Eleven figure groups exported to PNG/SVG under reports/s03_readiness/figures, with canonical aggregate source CSV/hash manifest. All20 comparison rows (original reference plus19 candidates), all fixed seeds and negative results retained.

| Model | Clean F1 mean | Clean MAE mean | Attempted96 F1 mean | Attempted96 MAE mean |
|---|---:|---:|---:|---:|
| Original S01 CAT |0.601850|0.642627|0.586218|0.654539|
| M1 |0.600888|0.598509|0.590554|0.614097|
| M2 |0.621305|0.602218|0.606892|0.618534|
| M3 |0.602342|0.615489|0.588551|0.627749|
| M4 |0.602005|0.607287|0.589037|0.619634|

The recorded M2 win is preserved, not reranked by this task. M1 trades a slightly worse mean F1 for lower MAE. Mild augmentation M3 does not improve the attempted96 averages overM1. M4's fixed KD does not surpassM2. CAT classification plus text regression improves regression but ranks belowM2 under the frozen rule; all nonzero neutrality biases and W2 fail the old strict promotion guard. These statements describe this finite VALID search only, not population mechanisms or statistical significance.

Fixedseed17 M2 clean Accuracy0.646978, macro-F10.621798, MAE0.599469, Pearson0.651602; attempted96 F10.607522, MAE0.612427. Mean±sampleSD is separate from seed17. TRAIN online loss/metrics mix pre-update predictions at changing parameters and are not epoch-end clean TRAIN performance. Stopped epochs are absent, not extrapolated. Replicates are averaged within condition before equal96-condition weighting and then seed averaging. 144 views are not144 independent cases; fractions concern supported coordinates, not seconds. Repeated checkpoint/config/profile selection on the same VALID set is optimistic; no confidence interval or significance claim is made.

## Q1 extraction and recorded failure

VERIFIED:100/100 original clips have actual text/audio/video descriptors (128/16/39 dimensions), full private trace and immutable source/feature hashes. Q1 interface is independent of official Q2 features. Initial PocketSphinx initialization failed for all100 due to its Windows non-ASCII path handling. Retained the failure records and features; byte-identical model copied to an ASCII path, initialization verified, then only alignment recomputed. No feature extraction/model fitting rerun.

66/100 computed alignments pass token completeness, ordering and timestamp/bounds checks;34 remain UNALIGNED (15 dictionary-OOV,13 no returned segmentation,6 token sequence mismatch). All100 samples and original labels retained. Human boundary-accuracy verification remains0/100; acoustic aligner output is not manual ground truth. An actual successful case is provided privately with waveform audio, frame and word/feature timestamps. Public Q1_CHECKS.json records all100 array/timestamp/hash checks and synthetic frequency/dimension checks.

Source official feature-to-time correspondence remains UNKNOWN. No Q1 result authorizes attachment4 mapping. No seconds are fabricated from official indices.

## Deployment and Q3 measured checks

VERIFIED in DEPLOYMENT.json: both profiles pass all four clean guard checks. V0 three-seed attempted96 F1=0.5753564564, MAE=0.6337787719; V1 F1=0.6068921445, MAE=0.6185338719. The preregistered winner is V1. Clean metrics are unchanged at mean and seed17 levels. This does not alter the champion, seed, epoch, weights or scaler. The adapter saw only visible features/support. All three V1 caches agree with old known-mask simulation outputs within the previously specified tolerance on this particular zeroed library; this is not proof of real missing-mask identifiability.

VERIFIED in Q3_VALIDATION.json:728 VALID group explanations, eight coalitions each; full coalition reproduces original outputs; maximum Shapley efficiency residual8.881784197001252e-16. All36 preregistered local cases evaluated, six per true-class/correctness stratum. Mean absolute classification deletion effect is0.827263 for key windows versus0.561876 for equal-length random windows; six of36 cases do not improve. Regression deletion effects0.437485 versus0.295050; seven do not improve. Retention effects also include six classification and nine regression non-improvements. Windows are selected for large effects on the same cases, so these descriptive checks are not independent validation, causal explanations, significance tests or guarantees of human semantic faithfulness. All signed effects and failures retained privately.

Q3 numerical feature-space checks pass; source mapping remains UNVERIFIED, timestamps null, Attachment4 gate BLOCKED. Independent exact-hash review and committed Q2 final gate remain required before Attachment3 access. Paper/submission remain draft with explicit gaps, not fully complete.
