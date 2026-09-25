# Paper claim evidence ledger

| Claim | State | Evidence | Limitation |
| --- | --- | --- | --- |
| Frozen aligned support/observed/padding contract exists | VERIFIED | docs/S00D_DATA_CONTRACT.md; DECISIONS.md | Operational first baseline contract; no final model selection |
| S00E safety and evidence repairs pass current full tests | VERIFIED tests and independent technical review | Current run TEST_RESULTS and subsequent independent review | Synthetic engineering checks are not sentiment accuracy |
| Tiny TRAIN Torch bridge/backward can run without source mutation | VERIFIED current CPU/CUDA run | reports/engineering/s00e_pytorch_runtime.json and source mutation report | No optimizer, epochs, validation/test predictions or model performance |
| Model predictive performance | UNKNOWN | No model run; metrics null | No Accuracy, F1, MAE or Pearson claims |
| S00E publication complete | VERIFIED | E19/E21, PUBLISH_RECEIPT and R01 prerequisite recheck | Current publication supersedes historical pending notes below |


## Native local approval revision — 20260925-014500-S00E-ASTRA-d9e4edb

The owner explicitly approved the prior report/manifest, but that approval is not migrated to revised code. The local native Codex journal verifier now checks the fixed task identity, exact digest question, accepted tool call, and linked user reply on every invocation. Repository receipts are not authority. Trust assumes an uncompromised local Codex host and OS account; this is not cryptographic authentication. New actual validation: 217 main tests, 25 subtests separately; CPU/CUDA TRAIN smoke passed with unchanged source. Fresh independent review and owner confirmation are required before E19; E21 and Release remain blocked. No predictive metrics were produced.


## Junction repair checkpoint — 20260925-020000-S00E-ASTRA-d9e4edb

Independent review rejected the native approval path because Windows junctions are not symlinks. Adopted full original-path lstat reparse-point rejection before traversal/open; rejected trusting resolve/is_symlink alone. Permanent root/ancestor/intermediate/file regressions pass. Actual full collection/execution: 221 main tests and 25 separate subtests, exit 0. Targeted first attempt had one assertion-message mismatch (29 passed/1 failed); fixed the assertion, without weakening the rejection. CPU/CUDA smoke and source hash unchanged. New independent review and owner confirmation still required; no predictive metrics.


## Completed independent technical review

Current run `20260925-020000-S00E-ASTRA-d9e4edb`: independent Astra High review PASS, zero CRITICAL or blocking MAJOR. Reviewer independently ran 221 main tests and 25 subtests (exit 0), verified 58 hashes and replayed the junction rejection. Report SHA256 `26c74726eff8c52ad5a08e399c8c1d6f3e9dc577dd4f75ea7340829588e5d6d8`. User approval of this exact revised digest and E21 publication preflight remain pending. No further review expansion is planned. Model metrics remain null.


## Verified S00E publication — 20260925-020000-S00E-ASTRA-d9e4edb

All 21 Gates passed, including actual independent review plus native exact-digest user approval and read-only E21. Existing stage_handoff completed ordinary implementation/metadata/index pushes and Release target/size/download SHA256 checks. Implementation 6480bfc77ce63edca92e6a57237772cddca0c3d0; metadata 27b026051c805f946e66e90a04bff603d7a01caa; index 7c1596dbe107d9e7b174b6e959941ddaf7c0f198; asset SHA256 e6cd31f0bb9af1ea6e79e5452645fec1afda2a296166db52f1e7fe41041625bf. R01 may resume; S01 remains unauthorized. No model performance claim.

Publication retained two ordinary failed attempts: intentional two-space Markdown line breaks initially failed whitespace formatting; an exact-file local Git attribute preserved approved report bytes. The first implementation push 92137f094cd2bd75a0182dc9fd8cefbdb61c6072 then stopped before Release because four governance documents had worktree CRLF versus Git LF. Setting local core.autocrlf=false preserved reviewed bytes in the ordinary follow-up implementation commit; no research text/code/hash changed, no history rewrite, no duplicate Release. No further review or research work was added.


## R01 evidence ledger — 2026-09-25

| Claim | State | Evidence | Limitation |
|---|---|---|---|
| R01 generator satisfies selected observed retention and finite fallback on checked synthetic cases | VERIFIED within finite reference cases | reports/research/R01_LOCAL_CLOSEOUT/checks.json; research/r01/reference.py | No NumPy/PyTorch implementation or data experiment; not a universal proof |
| 96 nominal conditions receive equal weight despite144views | INFERRED algebra; VERIFIED synthetic reduction | DESIGN §3/5 and checks | Requires actual ordered sample/view provenance from a future pipeline |
| C0/R0 comparison holds checkpoint policy constant | PROVISIONAL design; INFERRED identifiability improvement | DESIGN §5/8; protocol.json | No measured enhancement effect |
| R1/R2/R1-cap can test end-to-end fusion strategies | HYPOTHESIS | DESIGN §4; finite trials | Co-adaptation remains; not causal modality contribution |
| CE large-common-offset regression is corrected | VERIFIED synthetic counterexample and check | test_closeout.py and checks.json | No gradient/runtime/model test |
| Final seed17 obeys the proposed measured clean guard or reverts to B*17 | INFERRED rule; VERIFIED synthetic cases | select_final and checks | Future valid estimates remain noisy; no population guarantee |
| Gate improves prediction under missing data | UNKNOWN | All model trials NOT_RUN, metrics=null | Must not appear as a result or innovation claim |
| Known-mask simulation deploys to Attachment3 | UNKNOWN | DESIGN §2 | Reliable S/A not confirmed; no special data opened |
| Complete Q2/Q3 solved or any official model score exists | UNKNOWN | No authorized model experiment | Main96 omits TAVlocal; Q3 pending |

Sources opened and scopes verified in docs/research/R01/SOURCES.md and sources.json. External paper scores are not competition evidence. Protocol freeze and owner approval remain pending; independent technical review is not approval. Future registry entries must retain every config/seed/attempt, including failures and nonimprovements, not only successful/best seeds.


## Owner protocol freeze — R01-FREEZE-01

| Claim | State | Evidence | Limitation |
|---|---|---|---|
| First-round research protocol explicitly frozen by owner | SPECIFIED owner approval; FROZEN_FOR_S01_PROTOCOL | docs/research/R01/FREEZE_01.json, sourcecommit120a0938c76dd457a3d95c5c2a243f3e451a3f67 | No model performance or execution approval |
| Core39fit budget and required numeric wall-time before execution | SPECIFIED | protocol.json | Actual hoursnull; bulk training blocked until configured and separately authorized |
| Attachment3 reliable mask availability | UNKNOWN | Explicit owner boundary | Natural structural-zero cannot automatically mean artificial missing |

Earlier provisional/pending text describes the preapproval checkpoint. Owner approval changes governance only, not evidence strength: all model experimentsNOT_RUN and metricsnull, historical tests/reviews unchanged.
## S01 synthetic implementation and deadline resource evidence

| Claim | Evidence level | Source | Scope limit |
|---|---|---|---|
| Frozen models/masks/selection implemented and synthetic checks performed | VERIFIED only for listed actual checks | tests/test_s01_preparation.py; reports/s01_preparation/tests.json | No predictive performance conclusion |
| RealCUDA synthetic runtime/peakmemory measured | VERIFIED | resource_profile.json; scaled_profile.json | Artificial tensors, not officialepoch/runtime |
| Proposed30fits can fit12h planning envelope | INFERRED, PROVISIONAL | RESOURCE_ESTIMATE.json | No runtime guarantee; owner authorization required |
| Paper deadline9/27 00:00 Beijing;30h revisionbuffer | SPECIFIED userdeadline; PROVISIONAL computeallocation | DECISIONS.md; configs/s01_execution.json | Paper completion not claimed |
| Remaining9temporal/gatingfits have modelresults | UNKNOWN; NOT_RUN |39preregisteredfits | No mechanism superiority/ablation claim |
| Any officialscore, normalizerwinner orspecialmask result exists | UNKNOWN; metricsnull | state/LATEST_RESEARCH.json | No officialdata/modelexperiment this task |

Earliernullcaps describe historicalfreeze; currentnumericcaps are proposals only. No synthetic accuracy/F1/loss is inserted as competitionevidence. Independent technicalreview is distinct from ownerrunapproval.


Current S01 activation is SPECIFIED user authority, not empirical evidence. Only actual future VALID results tied to trial/seed/config/code/data/checkpoint hashes become VERIFIED_OFFICIAL_VALID_RESULT. No claims about deferredtemporal/gatingmodels, held-outtest, specialmask orQ3. Samevalidmultiple-selection optimism remains; no significance claim is preapproved.


## S01 current campaign closeout — S01-20260924T202319Z-30-1cf4769f

Campaign `S01-20260924T202319Z-30-1cf4769f` ended with **COMPLETED**. Budget 30; started 30, completed 30, failed 0, resource-stop 0, incomplete-without-terminal-event 0. Runtime 5464.000000 seconds. Common normalizer `zscore`; B* `B-CAT-zscore`. Source evidence: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/SUMMARY.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/FITS.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/BASELINE_AND_SELECTION.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/CONFIGURATION_SUMMARY.json`.

The one-shot authorization is CONSUMED for this terminal outcome; training_authorized=false and retry_training_budget=0. This closeout does not activate a new campaign, test, Attachment3/4, Q3 or any deferred model. Historical activation/preparation wording below or above is evidence of earlier states, not current execution permission. The immutable 39 preregistration rows stay NOT_RUN/null; distinct actual campaign rows and all failures are appended to docs/EXPERIMENT_REGISTER.json:s01_campaign_results. LATEST_RUN and frozen R01/data contracts remain unchanged.

Recorded final model: `B-CAT-zscore`, seed17, reason `WINNER_FIXED_SEED_GUARD_PASS`. Actual clean VALID metrics: `{"Accuracy": 0.6318681318681318, "macro_F1": 0.6006312138558835, "MAE": 0.6783806467575921, "Pearson": 0.5457738264072373, "Pearson_reason": null}`. No new selection was computed by this updater.

Repeated use of VALID for checkpoint, normalizer and configuration selection causes optimistic bias; seed SD is not a confidence interval and no significance is claimed. KNOWN_AVAILABILITY, 96 conditions/144 views, replicate → equal-weight condition → seed aggregation and CLEAN_ONCE are unchanged. Continuous windows use supported-coordinate fractions, not seconds. Attachment3 reliable masks remain UNKNOWN; natural structural-zero is not artificial missing. R1/R2/R1-CAP nine fits remain NOT_RUN; a 24-fit campaign supplies no C0/R0 mechanism evidence.

Evidence level: VERIFIED for the exported completed fit records and recorded selection; SPECIFIED for frozen protocol/authorization; HYPOTHESIS for population robustness mechanism; UNKNOWN for held-out test, deployment masks, deferred temporal/gating models and Q3. Earlier no-score statements describe historical checkpoints and do not replace this scoped empirical evidence.

Descriptive R0−C0 differences (all three prespecified seeds): clean ΔF1=+0.001263, ΔMAE=+0.003103; attempted96 ΔF1=-0.002595, ΔMAE=-0.000257. Negative/no-improvement outcomes are retained without follow-up search.

Actual execution command and environment: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/validation/RUN_RECEIPT.json`. The executed activation snapshot is commit `98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7`; its manifest is historical and is intentionally not rewritten to describe the closed authorization.


## S02-RES-01 / S02-EXEC-AUTH-01 — 2026-09-25

SPECIFIED and USER_PREAUTHORIZED by the explicit current S02 request: a new finite follow-up after known S01 results, not a change to S01's historical restrictions or R01 freeze. Freeze exactly W0/W1/W2 × five Neutral biases and M1/M2/M3/M4 × seeds17/29/43, bounded4h total/45minfit before9/25 18:00Beijing; retry0. Details/formulas/selection: docs/research/S02/PROTOCOL.md; config: configs/s02_execution.json; table: docs/research/S02/CANDIDATES.json. Same-VALID selection optimism remains; unrun models NOT_RUN/null. Train-only weights, mildcorruption and same-seedTRAINteacherKD are authorized here only. No test/special/Q1/Q3/external sentiment data or weights; no new Release. Initial champion remains original S01 CAT-zscore17 until complete frozen-rule comparison and winner recovery verify. D-DATA01..07 unchanged.


## S02 completed closeout — S02-20260925-BOUNDED-12F15W

VERIFIED:12/12 new fits and15/15 fixed postprocess configurations completed;0failed,0resource stops, retry0. All148 durable completed epochs retained. Execution commit `2b44b3d660493f3b20a78362cd4ec52bbe49714e`, canonical config `32f0001d54944a4775ec786ff00fba1ecabfaed64477c718a10199a3d6d61eec`, source `66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd`; actual commands/environment/timing in `reports/s02_execution/S02-20260925-BOUNDED-12F15W/RUN_RECEIPT.json`. Seeds17/29/43; train/valid mask roots2207/1103. No model computation was rerun during reporting.

Current champion is **M2 fixed seed17**, restored on clean+144views with exact prediction tensor values and atomically promoted under the preregistered six-metric guard. OldS01 weights/evidence and469backup members rehashed unchanged. Registry: `reports/s02_execution/S02-20260925-BOUNDED-12F15W/MODEL_REGISTRY.json`. S02 authorization is CONSUMED; training_authorized=false, no next stage. The formerS02 NOT_RUN/preregistration statements remain historical, not current result states.

Question: do fixed component combinations or bounded residual-fusion changes improve the knownS01 baseline? M2 mean cleanF1=0.621305 vs0.601850, attempted96F1=0.606892 vs0.586218; full means/SD and fixed17 sixmetrics in `reports/s02_execution/S02-20260925-BOUNDED-12F15W/RESULTS.md`. W1beta0 improves regression with unchangedclassification but ranks belowM2. M1 is in cleanPareto but misses strictmeanF1guard; M3 augmentation does not improve attempted96 means overM1; M4KD does not beatM2. No expanded search or luckyseed selection.

All results/negative tradeoffs,19candidate conditiongrids and57candidate-seed sign-inconsistency records preserved. `reports/s02_execution/S02-20260925-BOUNDED-12F15W/EPOCH_CURVES.csv` contains all148epochs; TRAIN online curves are currentview/preupdate diagnostics, not clean endcheckpoint performance. Technical reviewer found a missing finalcheckpoint binding in the draft exporter; reporting-only fix passed12syntheticchecks and realaggregate verification, no trainingcode/metrics changed.

Evidence: VERIFIED for recorded TRAIN/VALID outcomes and byte hashes; SPECIFIED for protocol/authorization; HYPOTHESIS for generalizable mechanisms; UNKNOWN for TEST/special performance and Attachment3 reliablemasks. RepeatedVALIDselection is optimistic, seedSD is not significance. D-DATA01..07/R01/S01/LATEST_RUN unchanged; no external sentimentdata/weights, TEST/special/Q1/Q3, Release or webpageZIP. Next: paper figures and writing from existing evidence; future official evaluation/deployment requires separate authorization.


## S03 registered — 2026-09-25

SPECIFIED: zero new fits; M2seed17 preserved; two fixed nonoracle profiles and exact group explanations under S03 protocol. VERIFIED byte-for-byte independent S01/S02 backup: reports/s03_readiness/BACKUP.json. Restore and new profile/explanation results pending, not claimed as completed. Official Q3 source mapping UNKNOWN. S01/S02 consumed and historical evidence retained.


## S03 readiness and independent review — 2026-09-25

VERIFIED: backup356files; exact M2seed17 clean restore;148epoch/12fit continuity and22figure exports; Q1 extraction100/100,66 computed temporal checks and0 human-verified alignments; two profiles x3seeds complete96/144, V1 wins (mean attempted F1=0.6068921445, MAE=0.6185338719). Q3 all728 group explanations and36 preselected local checks complete; feature-space numericalPASS, official mappingUNVERIFIED. Signed/negative outcomes retained. Same VALID selection and intervention-based explanation selection limit inference; no causal or significance claim.

Independent Astra/medium review identified3MAJOR final-entry issues; repaired before special access using existing inventory only. Final19synthetic checks and exact55file review PASS. Reports: reports/s03_readiness; protocol: docs/research/S03. Q2 readinessPASS still requires actual commit+fresh runtimepreflight before aligned30special inference; unaligned30notread. Q3 finalgateBLOCKED, Attachment4notread. Fixedweights/scaler and task-level onceclaim prevent reselection/replay.0newfits; original S01/S02 consumed, frozencontracts/engineeringindex untouched.


## S03 terminal closeout — 2026-09-25

VERIFIED: M2 seed17 epoch2 preserved; final rehash of356 original files and356 independent copies passed. Q1 features100/100,66 computed temporal checks,0 human word-boundary validations,34 UNALIGNED. V1 selection used only two fixed profiles x3 existing models on VALID96/144. Q3 group explanations728 and prespecified local cases36 passed numerical feature-space checks; official source mapping remains UNKNOWN/UNVERIFIED. No new fits or test selection.

Attachment3: reviewed activation commit c8d33ed4ef3169e49bce3dcfe628d41545e86bf9 passed clean local=remote and runtime hash checks. Original path-classifier failure was before content; reviewed one-time recovery retained its claim. Recovery then opened first aligned object and failed frozen required field text. No predictions or CSV; no schema redevelopment or reread. Attachment4 never opened. Both final deliverables BLOCKED. Error/receipt hashes: reports/s03_readiness/ATTACHMENT3_RESULT.json. Original57-file manifest/review binds the execution commit, not the now-closed config.

Paper is a9-page anonymous DRAFT. Private incomplete archive has478 members,12.251028MB, all477 payload hashes/sizes andCRC/set/path checks PASS; not a complete competition submission. Hidden Word image-path fields were removed with cached media preserved. Q1 preview image originally failed at Unicode-path cv2.imwrite; byte-safe encoding repair verified exact saved descriptor and actual PTS. No feature/label/alignment rewrite. Evidence: MATERIALS_CHECK.json, PAPER_CHECKS.json, Q1_CASE_ASSET_CHECK.json, FINAL_BACKUP_CHECK.json. Cases, weights and materials remain private.

Evidence levels: VERIFIED for actual saved checks/outputs and byte hashes; SPECIFIED for fixed protocols; HYPOTHESIS for external generalization; UNKNOWN for true special corruption masks, held-out TEST performance and official feature-to-time mapping. Same-VALID selection optimism and within-case top-window selection remain; no causal/significance claim. Monolithic aligned pickle materializes its container including TEST objects, but only allowlisted VALID fields were accessed for these calculations; no TEST metric, prediction or selection.

Authorization is CONSUMED, new fits0, retries0, special execution false. S01/S02/data contracts and LATEST_RUN unchanged. No Release, upload, new training or automatic next stage. Next is owner paper revision and a separately scoped resolution of special schema/mapping; this task stops.

## S04 special delivery claim boundary — 2026-09-25

VERIFIED: frozen M2 seed17 epoch2/V1 produced 20 aligned Attachment4 private PARTIAL prediction/explanation rows after an independent preinference technical review; full source population and output schema were checked, but no source-time correspondence was established. Report feature-index explanations only, with null timestamps and `UNVERIFIED_MAPPING`; do not call them causal or final complete evidence. Attachment3 yielded no prediction because every aligned file lacks continuous text; official schema clarification is needed. No special truth labels or metrics were read. Q1 still has 66 mechanical passes and 0 human-verified word alignments. The corrected paper draft states M3=M1+augmentation and M4=M3+KD; M2 class weights are not inherited. The S04 private archive is a runnable partial draft, not the ≤50MB final anonymous submission. Source: docs/research/S04/CLOSEOUT.md and reports/s04_io/FINAL_STATUS.json.
