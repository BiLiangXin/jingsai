# Next actions

S00E is completed and published; state/LATEST_RUN.json remains its original evidence pointer. R01-FREEZE-01 is FROZEN_FOR_S01_PROTOCOL. S01 preparation result:reports/s01_preparation/RESULT.json; specification:docs/S01_EXECUTION_SPEC.md.

Historical dependency: S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS established the frozen data contract in [docs/S00D_DATA_CONTRACT.md](../docs/S00D_DATA_CONTRACT.md). Its pending wording does not supersede the subsequently completed S00E publication.

Main Research Chat must review and explicitly authorize one bound future campaign, including30fit pre-execution fallback,12h/2h caps,CUDAdevice and absolute9/25 18:00 Beijing compute stop. Currenttraining_authorized=false. Approval after9/25 06:00 cannot start that12hplan; choose24fits/4h before anyexperiment and rebind, or reportdeadlineblocked. Never sacrifice the30h paper revisionbuffer or change budgets afterresults.

No officialtraining, test, Attachment3/4, Q3 oroptionalexpansion is currentlyauthorized. No automaticnextstage. NormalizerNOT_YET_SELECTED; all39registryrecordsNOT_RUN/metricsnull. No newRelease orWebZIP.


## Current activation — supersedes prior pending-authority wording

S01-EXEC-AUTH-01 explicitly preauthorizes campaignS01-20260924T202319Z-30-1cf4769f/30fits. After finalreview/tests/safetypush andfreshpreflight, automatically claim andexecute; no furtherownerquestion/nativejournal. Scopeandcaps:docs/S01_EXEC_AUTH_01.json. Stoponcap/failure,retainallattempts,publishsafeaggregateevidence; neverautoactivateQ3/special/testoradditionalcampaign.


## S01 current campaign closeout — S01-20260924T202319Z-30-1cf4769f

Campaign `S01-20260924T202319Z-30-1cf4769f` ended with **COMPLETED**. Budget 30; started 30, completed 30, failed 0, resource-stop 0, incomplete-without-terminal-event 0. Runtime 5464.000000 seconds. Common normalizer `zscore`; B* `B-CAT-zscore`. Source evidence: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/SUMMARY.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/FITS.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/BASELINE_AND_SELECTION.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/CONFIGURATION_SUMMARY.json`.

The one-shot authorization is CONSUMED for this terminal outcome; training_authorized=false and retry_training_budget=0. This closeout does not activate a new campaign, test, Attachment3/4, Q3 or any deferred model. Historical activation/preparation wording below or above is evidence of earlier states, not current execution permission. The immutable 39 preregistration rows stay NOT_RUN/null; distinct actual campaign rows and all failures are appended to docs/EXPERIMENT_REGISTER.json:s01_campaign_results. LATEST_RUN and frozen R01/data contracts remain unchanged.

Recorded final model: `B-CAT-zscore`, seed17, reason `WINNER_FIXED_SEED_GUARD_PASS`. Actual clean VALID metrics: `{"Accuracy": 0.6318681318681318, "macro_F1": 0.6006312138558835, "MAE": 0.6783806467575921, "Pearson": 0.5457738264072373, "Pearson_reason": null}`. No new selection was computed by this updater.

Repeated use of VALID for checkpoint, normalizer and configuration selection causes optimistic bias; seed SD is not a confidence interval and no significance is claimed. KNOWN_AVAILABILITY, 96 conditions/144 views, replicate → equal-weight condition → seed aggregation and CLEAN_ONCE are unchanged. Continuous windows use supported-coordinate fractions, not seconds. Attachment3 reliable masks remain UNKNOWN; natural structural-zero is not artificial missing. R1/R2/R1-CAP nine fits remain NOT_RUN; a 24-fit campaign supplies no C0/R0 mechanism evidence.

Next: verify/apply these terminal records, publish safe aggregates by ordinary exact-path Git commit/push, then revise the paper using existing evidence. No new execution permission is granted.

Actual execution command and environment: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/validation/RUN_RECEIPT.json`. The executed activation snapshot is commit `98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7`; its manifest is historical and is intentionally not rewritten to describe the closed authorization.


## S02 completed closeout — S02-20260925-BOUNDED-12F15W

VERIFIED:12/12 new fits and15/15 fixed postprocess configurations completed;0failed,0resource stops, retry0. All148 durable completed epochs retained. Execution commit `2b44b3d660493f3b20a78362cd4ec52bbe49714e`, canonical config `32f0001d54944a4775ec786ff00fba1ecabfaed64477c718a10199a3d6d61eec`, source `66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd`; actual commands/environment/timing in `reports/s02_execution/S02-20260925-BOUNDED-12F15W/RUN_RECEIPT.json`. Seeds17/29/43; train/valid mask roots2207/1103. No model computation was rerun during reporting.

Current champion is **M2 fixed seed17**, restored on clean+144views with exact prediction tensor values and atomically promoted under the preregistered six-metric guard. OldS01 weights/evidence and469backup members rehashed unchanged. Registry: `reports/s02_execution/S02-20260925-BOUNDED-12F15W/MODEL_REGISTRY.json`. S02 authorization is CONSUMED; training_authorized=false, no next stage. The formerS02 NOT_RUN/preregistration statements remain historical, not current result states.

Question: do fixed component combinations or bounded residual-fusion changes improve the knownS01 baseline? M2 mean cleanF1=0.621305 vs0.601850, attempted96F1=0.606892 vs0.586218; full means/SD and fixed17 sixmetrics in `reports/s02_execution/S02-20260925-BOUNDED-12F15W/RESULTS.md`. W1beta0 improves regression with unchangedclassification but ranks belowM2. M1 is in cleanPareto but misses strictmeanF1guard; M3 augmentation does not improve attempted96 means overM1; M4KD does not beatM2. No expanded search or luckyseed selection.

All results/negative tradeoffs,19candidate conditiongrids and57candidate-seed sign-inconsistency records preserved. `reports/s02_execution/S02-20260925-BOUNDED-12F15W/EPOCH_CURVES.csv` contains all148epochs; TRAIN online curves are currentview/preupdate diagnostics, not clean endcheckpoint performance. Technical reviewer found a missing finalcheckpoint binding in the draft exporter; reporting-only fix passed12syntheticchecks and realaggregate verification, no trainingcode/metrics changed.

Evidence: VERIFIED for recorded TRAIN/VALID outcomes and byte hashes; SPECIFIED for protocol/authorization; HYPOTHESIS for generalizable mechanisms; UNKNOWN for TEST/special performance and Attachment3 reliablemasks. RepeatedVALIDselection is optimistic, seedSD is not significance. D-DATA01..07/R01/S01/LATEST_RUN unchanged; no external sentimentdata/weights, TEST/special/Q1/Q3, Release or webpageZIP. Next: paper figures and writing from existing evidence; future official evaluation/deployment requires separate authorization.


## S03 terminal closeout — 2026-09-25

VERIFIED: M2 seed17 epoch2 preserved; final rehash of356 original files and356 independent copies passed. Q1 features100/100,66 computed temporal checks,0 human word-boundary validations,34 UNALIGNED. V1 selection used only two fixed profiles x3 existing models on VALID96/144. Q3 group explanations728 and prespecified local cases36 passed numerical feature-space checks; official source mapping remains UNKNOWN/UNVERIFIED. No new fits or test selection.

Attachment3: reviewed activation commit c8d33ed4ef3169e49bce3dcfe628d41545e86bf9 passed clean local=remote and runtime hash checks. Original path-classifier failure was before content; reviewed one-time recovery retained its claim. Recovery then opened first aligned object and failed frozen required field text. No predictions or CSV; no schema redevelopment or reread. Attachment4 never opened. Both final deliverables BLOCKED. Error/receipt hashes: reports/s03_readiness/ATTACHMENT3_RESULT.json. Original57-file manifest/review binds the execution commit, not the now-closed config.

Paper is a9-page anonymous DRAFT. Private incomplete archive has478 members,12.251028MB, all477 payload hashes/sizes andCRC/set/path checks PASS; not a complete competition submission. Hidden Word image-path fields were removed with cached media preserved. Q1 preview image originally failed at Unicode-path cv2.imwrite; byte-safe encoding repair verified exact saved descriptor and actual PTS. No feature/label/alignment rewrite. Evidence: MATERIALS_CHECK.json, PAPER_CHECKS.json, Q1_CASE_ASSET_CHECK.json, FINAL_BACKUP_CHECK.json. Cases, weights and materials remain private.

Evidence levels: VERIFIED for actual saved checks/outputs and byte hashes; SPECIFIED for fixed protocols; HYPOTHESIS for external generalization; UNKNOWN for true special corruption masks, held-out TEST performance and official feature-to-time mapping. Same-VALID selection optimism and within-case top-window selection remain; no causal/significance claim. Monolithic aligned pickle materializes its container including TEST objects, but only allowlisted VALID fields were accessed for these calculations; no TEST metric, prediction or selection.

Authorization is CONSUMED, new fits0, retries0, special execution false. S01/S02/data contracts and LATEST_RUN unchanged. No Release, upload, new training or automatic next stage. Next is owner paper revision and a separately scoped resolution of special schema/mapping; this task stops.

## After S04-IO-RECOVERY-01 — 2026-09-25

Ask the organizer the exact Attachment3 continuous-text field/source and legal support schema using docs/research/S04/OFFICIAL_QUESTIONS.md. Obtain verifiable official Attachment4 feature-index to source timing/token/segment mapping; retain current private PARTIAL CSV meanwhile. A teammate should review the prioritized real Q1 case with the existing audio/frame worksheet, then triage all 34 failures at clip granularity. Review the revised draft paper and required submission components before the 2026-09-27 00:00 Beijing deadline. S04 authority is consumed; any new special run or model work requires separate scope. No Release or contest upload occurred.
