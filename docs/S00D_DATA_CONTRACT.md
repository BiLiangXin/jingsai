# S00D aligned data contract and baseline readiness

task_id: `S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS`
run_id: `20260924-100153-S00D-c26aced`
state: `PENDING_RESEARCH_REVIEW`; `NEXT_STAGE_NOT_AUTHORIZED`

## Scope and provenance

The authorized S00D run validated the trusted official `aligned_50.pkl` train and valid splits read-only. The source SHA256 before and after was `66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd`, matching the S00C published source fingerprint. The run did not index the test split, open Attachment 3/4 content, train a model, or compare predictive metrics. See `reports/data_contract/source_mutation_check.json` and the run's two public source-hash records.

## Baseline interface

`aligned_50.pkl` is **FROZEN_FOR_BASELINE** as the primary controlled interface. It is not a final performance comparison against unaligned. The adapter exposes train and valid only. Counts were 3,395 and 728. Stored shapes are `(N,50,768)` text, `(N,50,74)` audio, `(N,50,35)` vision. Stored dtypes are float32, float64, float64 respectively; model batches convert features to float32. `text_bert` channel 1 is mask metadata and does not enter the model input dictionary as a feature. See `reports/data_contract/contract_summary.json` and `loader_contract.json`.

## Mask semantics

`M_support = text_bert[:,1,:] == 1` is a validated, nonempty, continuous active prefix. All three aligned modalities share that support. `M_padding = NOT M_support`. Text observed positions equal support. Audio and vision observed positions equal support AND NOT exact all-dimension structural zero. Structural zero is a description of stored values and is not automatically missing, corruption, or padding. Artificial corruption is a separate explicit all-false default interface and can only mark observed positions. Continuous text after support can be nonzero; masked pooling excludes it without changing the source tensor.

In train, support covers 83,672 positions; audio and vision have 6,855 and 11,039 structural zero rows within support, respectively. In valid, support covers 18,628 positions; corresponding zero-row counts are 1,502 and 2,436. These are aggregate contract checks, not a missingness interpretation. See `reports/data_contract/mask_summary.json`.

## Targets, normalization and leakage boundary

Official three-class targets remain Negative=0, Neutral=1, Positive=2. Regression is finite within [-3,3], with neutral only at exact zero. Targets are returned separately from model inputs. Raw ID, raw text, labels, split membership and special-set statistics are absent from the model input dictionary. See `reports/data_contract/label_contract.json` and `loader_contract.json`.

Identity and train-only z-score infrastructure is available. Z-score statistics are calculated from train observed vectors only: text support positions and audio/vision supported nonzero rows. The persisted state records mean, std, count, dimensions, fit split, version and mask rule. Zero-variance features use scale 1; non-observed rows keep their original values. The valid split was used only for transform validation. The final normalizer choice remains **UNDECIDED**. See `reports/data_contract/normalization_contract.json`.

## Readiness and limitations

The adapter produces deterministic NumPy batches with explicit masks and targets. `AlignedBatch.to_torch()` is a direct optional conversion bridge; PyTorch is not installed in this S00D execution environment, so that bridge was not runtime exercised. This stage did not select a model architecture or run training. S01 remains unauthorized pending Main Research Chat review.
