# Research decisions

Fields: `decision_id | status | decision | evidence | reason | date | affected_stages`.

| decision_id | status | decision | evidence | reason | date | affected_stages |
| --- | --- | --- | --- | --- | --- | --- |
| ENG-001 | FROZEN | This fresh clone is the sole official development repository; the old E directory is a local source only. | VERIFIED remote main SHA and clean clone | Avoid carrying old Git history and tracked raw data | 2026-09-23 | S00A onward |
| RES-001 | UNDECIDED | Aligned versus unaligned feature interface | UNKNOWN | Requires later research review and data audit | 2026-09-23 | S00B onward |
| RES-002 | UNDECIDED | Padding and observation semantics | UNKNOWN | Requires actual data audit | 2026-09-23 | S00B onward |
| RES-003 | UNDECIDED | Missingness and corruption design | UNKNOWN | Requires research authorization | 2026-09-23 | Later stages |
| RES-004 | UNDECIDED | Model, loss, and distillation | UNKNOWN | Requires research authorization | 2026-09-23 | Later stages |
| RES-005 | UNDECIDED | Explanation and time mapping | UNKNOWN | Requires research authorization and mapping evidence | 2026-09-23 | Later stages |
| RES-006 | UNDECIDED | Final normalizer choice between none and train-only z-score | SPECIFIED S00D authorization | Await S01 valid comparison; S00D builds infrastructure only | 2026-09-24 | S01 onward |
| D-DATA-01 | FROZEN_FOR_BASELINE | S01 primary controlled baseline interface is aligned_50.pkl; unaligned remains a later controlled comparator. This is not a final performance verdict. | SPECIFIED Main Research Chat S00D authorization; VERIFIED S00B/S00C interfaces | Fix one baseline input contract without declaring aligned superior | 2026-09-24 | S00D, S01 baseline |
| D-DATA-02 | FROZEN_FOR_BASELINE | Keep support, observed, and artificial corruption masks distinct. For aligned, shared operational support is text_bert channel 1 equal to 1. | SPECIFIED Main Research Chat S00D authorization; VERIFIED S00C binary continuous prefix | Prevent conflation of stored values and sequence support | 2026-09-24 | S00D, S01 baseline |
| D-DATA-03 | FROZEN_FOR_BASELINE | Aligned audio/vision observed mask is shared support AND NOT exact structural zero row; text observed mask equals support. | SPECIFIED Main Research Chat S00D authorization | Define an operational observed-vector rule without equating zero with missing | 2026-09-24 | S00D, S01 baseline |
| D-DATA-04 | FROZEN_FOR_BASELINE | Natural exact zero rows are STRUCTURAL_ZERO only. Future artificial corruption uses a separate explicit mask and is never inferred from feature values. | SPECIFIED Main Research Chat S00D authorization | Preserve natural-zero versus artificial-corruption semantics | 2026-09-24 | S00D onward |
| D-DATA-05 | FROZEN_FOR_BASELINE | S01 aligned operational padding is NOT support; temporal pooling, aggregation, attention summaries and temporal loss reductions exclude padding. ZERO_ROW is not PADDING. | SPECIFIED Main Research Chat S00D authorization | Prevent non-support storage values from leaking into representations | 2026-09-24 | S00D, S01 baseline |
| D-DATA-06 | FROZEN_FOR_BASELINE | First baseline permits continuous text, audio and vision only; text_bert channel 1 is mask metadata, not a fourth modality. IDs, raw text, labels, split membership and Attachment 3/4 statistics are not predictors. Official classification/regression labels are targets. | SPECIFIED Main Research Chat S00D authorization | Establish a leak-resistant model input allowlist | 2026-09-24 | S00D, S01 baseline |
| D-DATA-07 | FROZEN_FOR_BASELINE | Learned normalization fits train only, using support AND observed vectors; text uses support, audio/vision exclude exact-zero structural rows for scaler statistics. Provide identity and train-only z-score; final scaler choice remains UNDECIDED. | SPECIFIED Main Research Chat S00D authorization | Enforce split isolation while leaving model selection to later valid comparison | 2026-09-24 | S00D, S01 baseline |
| Q1-SOURCE-01 | FROZEN | For the 100 Attachment 1 samples, audio source is the actual MP4 soundtrack, text source is the official label-100.xlsx:text field, and vision source is MP4 frames. Retain all 100 by default, including audio/text inconsistencies, silence, non-English audio or text, unclear scenes, and clips without a human face. Record uncertainty states for these cases; do not fabricate forced audio-text alignment. | SPECIFIED user-supplied competition forum expert reply dated 2026-09-24; source not independently reverified here | Preserve the authorized Q1 input and coverage rules without silently dropping atypical samples | 2026-09-24 | Q1 governance |
| Q1-MISSING-01 | UNDECIDED | Exact Q1 mapping from uncertainty or source anomalies to missingness is not defined. No anomaly is automatically natural missingness. | UNKNOWN; the supplied clarification does not define a missingness mapping | Preserve uncertainty for later research review | 2026-09-24 | Q1 later research |

Valid status values: `UNDECIDED`, `PROVISIONAL`, `FROZEN_FOR_BASELINE`, `FROZEN`, `REOPENED`. `FROZEN_FOR_BASELINE` is an operational S01 interface contract, not `FINAL_MODEL_DECISION`. RES-001 through RES-005 retain their undecided final research scope.

## Engineering workflow authority

| ID | Status | Decision | Source |
| --- | --- | --- | --- |
| GOV-ASTRA-SERIAL-01 | AUTHORIZED | Astra High serial engineering with one official-tree writer; actual independent read-only Astra review and verified owner approval source; no Sol/Astra switch or mandatory Web Chat ZIP; original safety/Gates/Review Release contract retained; engineering completion precedes research resumption; ongoing project/paper evidence; S01 training remains unauthorized. D-DATA-01 through D-DATA-07 and Q1 are unchanged. | Explicit user S00E_ASTRA_LOCAL_CLOSEOUT instruction, 2026-09-25 |
