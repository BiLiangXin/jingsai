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

Valid status values: `UNDECIDED`, `PROVISIONAL`, `FROZEN_FOR_BASELINE`, `FROZEN_FOR_S01_PROTOCOL`, `FROZEN`, `REOPENED`. `FROZEN_FOR_BASELINE` is an operational S01 interface contract, not `FINAL_MODEL_DECISION`. RES-001 through RES-005 retain their undecided final research scope.

## Engineering workflow authority

| ID | Status | Decision | Source |
| --- | --- | --- | --- |
| GOV-ASTRA-SERIAL-01 | AUTHORIZED | Astra High serial engineering with one official-tree writer; actual independent read-only Astra review and verified owner approval source; no Sol/Astra switch or mandatory Web Chat ZIP; original safety/Gates/Review Release contract retained; engineering completion precedes research resumption; ongoing project/paper evidence; S01 training remains unauthorized. D-DATA-01 through D-DATA-07 and Q1 are unchanged. | Explicit user S00E_ASTRA_LOCAL_CLOSEOUT instruction, 2026-09-25 |


## R01 local research recommendations — 2026-09-25

Source: explicit user R01_ASTRA_LOCAL_RESEARCH_CLOSEOUT. The local research author may settle ordinary design choices and publish safe research artifacts after verified S00E completion. None of these recommendations changes D-DATA-01 through D-DATA-07, authorizes S01/Q3 or approves a model. Full P01..P11 rationale/alternatives/evidence and pending R01-FREEZE-01 scope: docs/research/R01/DECISIONS.md; structured record: docs/research/R01/decisions.json. All eleven have status PROVISIONAL. R01-FREEZE-01 is PENDING_OWNER_CONFIRMATION, not FROZEN.


## MAIN_RESEARCH_DECISION — R01-FREEZE-01 — 2026-09-25

| decision_id | status | decision | evidence | reason | date | affected_stages |
| --- | --- | --- | --- | --- | --- | --- |
| R01-FREEZE-01 | FROZEN_FOR_S01_PROTOCOL | Freeze only the owner's16listed first-round protocol items, core39fits;24/30fallback chosen before execution. Wall-time cap required but numeric value remainsnull. D/T/L and66fit/deployment/Q3 extensions excluded. | SPECIFIED explicit current owner user instruction; approved source commit120a0938c76dd457a3d95c5c2a243f3e451a3f67 and exact file hashes in docs/research/R01/FREEZE_01.json | Record genuine owner approval without author self-approval or execution authorization | 2026-09-25 | Future S01 specification only |

This supersedes the previous pending R01-FREEZE-01 status only within the listed scope. D-DATA-01..07 remain byte-content unchanged. All official model experiments remainNOT_RUN, metrics=null, training_authorized=false. No test use, Attachment3/4research reads, Q3, unaligned comparison or66-fit expansion is authorized. Attachment3 reliable mask availability remainsUNKNOWN; natural structural-zero is not automatically artificial missing. Numeric wall-time must be entered into future execution config from actual hardware/non-selection resource measurements before S01 activation; null forbids bulk training. Next stage: S01_SPECIFICATION_AND_EXECUTION_AUTHORIZATION, not activated. Prior proposal/technical-review records remain historical evidence, not a substitute for this explicit owner decision.
## S01 preparation and deadline proposal — 2026-09-25

| ID | Status | Decision | Evidence / limit |
|---|---|---|---|
| S01-PREP-01 | SPECIFIED | Implement all39frozenfits and execute synthetic engineering checks only; normalizerNOT_YET_SELECTED; no officialdata/training. | Explicit user preparation request; reports/s01_preparation |
| S01-RESOURCE-01 | PROVISIONAL | Propose30fit pre-execution resource downgrade:B24+C0/R0six;12hour total,2hour perfit,CUDA,batch32,5GiB artifacts,80%globalGPU guard. Remaining9fitsNOT_RUN. | Verified synthetic hardware timing; no officialtime guarantee; owner has not approved hours/execution |
| S01-DEADLINE-01 | SPECIFIED deadline; PROVISIONAL allocation | Paper deadline2026-09-27 00:00 Beijing; propose compute stop2026-09-25 18:00 and30h revision buffer.30fit lateststart06:00; if unavailable select24before starting,4h cap andlateststart14:00, with no robust mechanism conclusion. | Explicit user deadline; no outcome-dependent budget switch |

R01-FREEZE-01 remainsFROZEN_FOR_S01_PROTOCOL/core39. These are finite implementation/resource proposals within its allowed24/30fallback, not a new research freeze or training approval. Execution requires one genuine owner event bound to exactcommit/config/freeze/campaign/output/device/budget/cap/deadline. Prior72hourproposal is superseded, not erased. All historical evidence, NOT_RUN and null metrics remain.


## S01-EXEC-AUTH-01 — explicit current user preauthorization

Status: USER_PREAUTHORIZED. Source: current user S01_PREAUTHORIZED_OFFICIAL_EXECUTION; instructionSHA2567a7f1835b0f08049453f25227f0faf50ff12f9859ebfe7ccbc3d53f6cb013afd. Currentuser explicitly replaces the historical nativeownerjournal/reconfirmation prerequisite for this onecampaign; all other source/split/protocol/Git/resource/one-shot checks remain.

CampaignS01-20260924T202319Z-30-1cf4769f; decisiontime2026-09-24T20:23:19.007829+00:00; selected30fits, 12hourtotal/2hourperfit,CUDA; retry0; absoluteend2026-09-25T18:00:00+08:00. Both30(12h/2h) and24(4h/1h) were preapproved, selected once bytimebeforeofficialsourceaccess. No selection-based fallback,extra fit orrestart. Core39registry retained; unselectedfitsNOT_RUN. Fullscope/criticalbinding:docs/S01_EXEC_AUTH_01.json andreports/s01_activation/AUTHORIZED_EXECUTION_MANIFEST.json. R01/datafreeze unchanged; test/special/Q3 anddeferredmodels remainexcluded. No modelmetric exists until actualofficialexecution.


## S01 current campaign closeout — S01-20260924T202319Z-30-1cf4769f

Campaign `S01-20260924T202319Z-30-1cf4769f` ended with **COMPLETED**. Budget 30; started 30, completed 30, failed 0, resource-stop 0, incomplete-without-terminal-event 0. Runtime 5464.000000 seconds. Common normalizer `zscore`; B* `B-CAT-zscore`. Source evidence: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/SUMMARY.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/FITS.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/BASELINE_AND_SELECTION.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/CONFIGURATION_SUMMARY.json`.

The one-shot authorization is CONSUMED for this terminal outcome; training_authorized=false and retry_training_budget=0. This closeout does not activate a new campaign, test, Attachment3/4, Q3 or any deferred model. Historical activation/preparation wording below or above is evidence of earlier states, not current execution permission. The immutable 39 preregistration rows stay NOT_RUN/null; distinct actual campaign rows and all failures are appended to docs/EXPERIMENT_REGISTER.json:s01_campaign_results. LATEST_RUN and frozen R01/data contracts remain unchanged.

Recorded final model: `B-CAT-zscore`, seed17, reason `WINNER_FIXED_SEED_GUARD_PASS`. Actual clean VALID metrics: `{"Accuracy": 0.6318681318681318, "macro_F1": 0.6006312138558835, "MAE": 0.6783806467575921, "Pearson": 0.5457738264072373, "Pearson_reason": null}`. No new selection was computed by this updater.

Repeated use of VALID for checkpoint, normalizer and configuration selection causes optimistic bias; seed SD is not a confidence interval and no significance is claimed. KNOWN_AVAILABILITY, 96 conditions/144 views, replicate → equal-weight condition → seed aggregation and CLEAN_ONCE are unchanged. Continuous windows use supported-coordinate fractions, not seconds. Attachment3 reliable masks remain UNKNOWN; natural structural-zero is not artificial missing. R1/R2/R1-CAP nine fits remain NOT_RUN; a 24-fit campaign supplies no C0/R0 mechanism evidence.

Actual execution command and environment: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/validation/RUN_RECEIPT.json`. The executed activation snapshot is commit `98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7`; its manifest is historical and is intentionally not rewritten to describe the closed authorization.


## S02-RES-01 / S02-EXEC-AUTH-01 — 2026-09-25

SPECIFIED and USER_PREAUTHORIZED by the explicit current S02 request: a new finite follow-up after known S01 results, not a change to S01's historical restrictions or R01 freeze. Freeze exactly W0/W1/W2 × five Neutral biases and M1/M2/M3/M4 × seeds17/29/43, bounded4h total/45minfit before9/25 18:00Beijing; retry0. Details/formulas/selection: docs/research/S02/PROTOCOL.md; config: configs/s02_execution.json; table: docs/research/S02/CANDIDATES.json. Same-VALID selection optimism remains; unrun models NOT_RUN/null. Train-only weights, mildcorruption and same-seedTRAINteacherKD are authorized here only. No test/special/Q1/Q3/external sentiment data or weights; no new Release. Initial champion remains original S01 CAT-zscore17 until complete frozen-rule comparison and winner recovery verify. D-DATA01..07 unchanged.


## S02 completed closeout — S02-20260925-BOUNDED-12F15W

VERIFIED:12/12 new fits and15/15 fixed postprocess configurations completed;0failed,0resource stops, retry0. All148 durable completed epochs retained. Execution commit `2b44b3d660493f3b20a78362cd4ec52bbe49714e`, canonical config `32f0001d54944a4775ec786ff00fba1ecabfaed64477c718a10199a3d6d61eec`, source `66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd`; actual commands/environment/timing in `reports/s02_execution/S02-20260925-BOUNDED-12F15W/RUN_RECEIPT.json`. Seeds17/29/43; train/valid mask roots2207/1103. No model computation was rerun during reporting.

Current champion is **M2 fixed seed17**, restored on clean+144views with exact prediction tensor values and atomically promoted under the preregistered six-metric guard. OldS01 weights/evidence and469backup members rehashed unchanged. Registry: `reports/s02_execution/S02-20260925-BOUNDED-12F15W/MODEL_REGISTRY.json`. S02 authorization is CONSUMED; training_authorized=false, no next stage. The formerS02 NOT_RUN/preregistration statements remain historical, not current result states.

Question: do fixed component combinations or bounded residual-fusion changes improve the knownS01 baseline? M2 mean cleanF1=0.621305 vs0.601850, attempted96F1=0.606892 vs0.586218; full means/SD and fixed17 sixmetrics in `reports/s02_execution/S02-20260925-BOUNDED-12F15W/RESULTS.md`. W1beta0 improves regression with unchangedclassification but ranks belowM2. M1 is in cleanPareto but misses strictmeanF1guard; M3 augmentation does not improve attempted96 means overM1; M4KD does not beatM2. No expanded search or luckyseed selection.

All results/negative tradeoffs,19candidate conditiongrids and57candidate-seed sign-inconsistency records preserved. `reports/s02_execution/S02-20260925-BOUNDED-12F15W/EPOCH_CURVES.csv` contains all148epochs; TRAIN online curves are currentview/preupdate diagnostics, not clean endcheckpoint performance. Technical reviewer found a missing finalcheckpoint binding in the draft exporter; reporting-only fix passed12syntheticchecks and realaggregate verification, no trainingcode/metrics changed.

Evidence: VERIFIED for recorded TRAIN/VALID outcomes and byte hashes; SPECIFIED for protocol/authorization; HYPOTHESIS for generalizable mechanisms; UNKNOWN for TEST/special performance and Attachment3 reliablemasks. RepeatedVALIDselection is optimistic, seedSD is not significance. D-DATA01..07/R01/S01/LATEST_RUN unchanged; no external sentimentdata/weights, TEST/special/Q1/Q3, Release or webpageZIP. Next: paper figures and writing from existing evidence; future official evaluation/deployment requires separate authorization.
