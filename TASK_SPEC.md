task_id: S04_IO_COMPATIBILITY_AND_DELIVERY_RECOVERY
status: ACTIVE_AUTHORIZED
authorization: S04-IO-RECOVERY-01
training_authorized: false
new_fit_budget: 0
test_authorized: false
attachment3_4_authorized: CONDITIONAL_FROZEN_REVIEWED_COMMITTED
protocol: docs/research/S04/PROTOCOL.md
config: configs/s04_execution.json

# Historical S03 closeout — consumed

task_id: S03_Q1_Q3_AND_DEPLOYMENT_READINESS
status: CLOSED_PARTIAL_BLOCKED
authorization_status: CONSUMED
training_authorized: false
new_fit_budget: 0
retry_budget: 0
attachment3_4_authorized: false
next_stage_authorized: false

# Current closeout

Q1 coverage100; computed word alignment66, human verified0. Q2 V1 validated; Q3 feature-space numerical checks passed but official mapping unverified. Attachment3 first content rejected for missing required text field; no CSV. Attachment4 not opened. Private draft materials incomplete; no competition submission or Release. Historical activation below cannot restart execution.

# Historical S03 activation — consumed

task_id: S03_Q1_Q3_AND_DEPLOYMENT_READINESS
status: ACTIVE_AUTHORIZED
training_authorized: false
new_fit_budget: 0
test_authorized: false
attachment3_4_authorized: CONDITIONAL_SEPARATE_COMMITTED_GATES
protocol: docs/research/S03/PROTOCOL.md
config: configs/s03_execution.json

# Historical task specifications — authority consumed

task_id: S02_CHAMPION_CHALLENGER_IMPROVEMENT
status: CLOSED_COMPLETED
training_authorized: false
s01_training_authorized: false
authorization_status: CONSUMED
campaign_id: S02-20260925-BOUNDED-12F15W
retry_training_budget: 0
next_stage_authorized: false
test_authorized: false
attachment3_4_authorized: false
q3_authorized: false

# Current S02 closeout

12fits and15postprocess configurations completed. M2 fixedseed17 promoted after full frozen comparison and restore. Evidence: reports/s02_execution/S02-20260925-BOUNDED-12F15W/RESULTS.md. Only safe reporting/publication remains authorized; no model execution or new Release.

# Historical S02 activation — preserved, authority consumed

The following ACTIVE_AUTHORIZED wording is historical and cannot authorize a second execution.

task_id: S02_CHAMPION_CHALLENGER_IMPROVEMENT
status: ACTIVE_AUTHORIZED
training_authorized: true
s01_training_authorized: false
campaign_id: S02-20260925-BOUNDED-12F15W
execution_fit_budget: 12
postprocess_budget: 15
retry_training_budget: 0
resource_walltime_cap_hours: 4
per_fit_walltime_cap_minutes: 45
latest_compute_finish: 2026-09-25T18:00:00+08:00
test_authorized: false
attachment3_4_authorized: false
q3_authorized: false
next_stage_authorized: false

# S02 finite champion/challenger task

Explicit current user S02 instruction supersedes prior no-new-task permission only in its new finite scope. S01 remains CLOSED_COMPLETED/CONSUMED. No second owner approval event is required. Before any candidate: complete independent backup and restore checks, frozen protocol/config/15W+12fit table, synthetic checks/resource measurement, independent exact-hash technical review and ordinary safe commit/push. Runtime then requires clean local=remote HEAD, exact manifest, unused S02 claim, four-hour window and private bound output. Never reuse S01 claim or mutate old checkpoints.

Canonical protocol: docs/research/S02/PROTOCOL.md. Scope: train/valid only, fixed seeds17/29/43, no retries/expansion, full96/144 aggregation. Preserve D-DATA01..07, original R01/S01 records, LATEST_RUN and reliable-special-mask UNKNOWN. Strong conservative promotion only after complete comparison and restored fixedseed17 verification; failure/partial resource stop retains original pointer. No Release/WebZIP/Q1/Q3/test/special inference. Only safe aggregate/code/config evidence and canonical four paper ledgers may be committed/pushed by exact paths to codex/mosei-auto.

## Historical S01 TASK_SPEC (closed; not current authority)

task_id: S01_FROZEN_BASELINE_EXECUTION
status: CLOSED_COMPLETED
research_authorized: true
s01_training_authorized: false
training_authorized: false
next_stage_authorized: false
owner_authorization_mode: PREAUTHORIZED_BY_CURRENT_USER_INSTRUCTION
authorization_status: CONSUMED
protocol_freeze: R01-FREEZE-01
campaign_id: S01-20260924T202319Z-30-1cf4769f
execution_fit_budget: 30
retry_training_budget: 0
test_authorized: false
attachment3_4_authorized: false
q3_authorized: false

# S01 terminal closeout

Campaign `S01-20260924T202319Z-30-1cf4769f` ended with **COMPLETED**. Budget 30; started 30, completed 30, failed 0, resource-stop 0, incomplete-without-terminal-event 0. Runtime 5464.000000 seconds. Common normalizer `zscore`; B* `B-CAT-zscore`. Source evidence: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/SUMMARY.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/FITS.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/BASELINE_AND_SELECTION.json`, `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/CONFIGURATION_SUMMARY.json`.

The one-shot authorization is CONSUMED for this terminal outcome; training_authorized=false and retry_training_budget=0. This closeout does not activate a new campaign, test, Attachment3/4, Q3 or any deferred model. Historical activation/preparation wording below or above is evidence of earlier states, not current execution permission. The immutable 39 preregistration rows stay NOT_RUN/null; distinct actual campaign rows and all failures are appended to docs/EXPERIMENT_REGISTER.json:s01_campaign_results. LATEST_RUN and frozen R01/data contracts remain unchanged.

## Historical activation TASK_SPEC — preserved, authority consumed

The following is historical content only. Its ACTIVE_AUTHORIZED/true flags cannot authorize a second execution.

task_id: S01_FROZEN_BASELINE_EXECUTION
status: ACTIVE_AUTHORIZED
research_authorized: true
s01_training_authorized: true
next_stage_authorized: false
owner_authorization_mode: PREAUTHORIZED_BY_CURRENT_USER_INSTRUCTION
protocol_freeze: R01-FREEZE-01
campaign_id: S01-20260924T202319Z-30-1cf4769f
execution_fit_budget: 30
resource_walltime_cap_hours: 12
per_fit_walltime_cap_hours: 2
latest_compute_finish: 2026-09-25T18:00:00+08:00
retry_training_budget: 0
test_authorized: false
attachment3_4_authorized: false
q3_authorized: false
device: cuda

# S01 one preauthorized official campaign

Source: current explicit user S01_PREAUTHORIZED_OFFICIAL_EXECUTION instruction; docs/S01_EXEC_AUTH_01.json. It supersedes historical preparation/nativeowner-confirmation requirements for this campaign only. No further confirmation or nativejournal event is required. S00E completed publication and R01-FREEZE-01 remain intact. D-DATA-01..07 unchanged.

Budget selected once before originaldata bytes or optimizer access, using currenttime and the user's12h/4h rule. Selected30fits; no result-dependent downgrade, expansion orretry. TRAIN fits; VALID uses frozencheckpoint/normalizer/config selection. Test and Attachment3/4, Q3, unaligned, optionalblocks andexternal sentiment weights/data remain prohibited.

Before source access: clean correct Gitbranch/origin andlocal=remoteHEAD, exactcriticalmanifest, frozenfiles, independent0CRITICAL/0blockingMAJOR review, currenttests andpublicsafety; ordinaryactivationcommit/push; freshcompletepreflight; one-shotclaim to a bound newexternalprivate directory. No author self-approval. Runtime permits only the claimed process and concrete24/30plan. No CLIboolean bypass.

Privatecheckpoint/result logs never enterGit. At anycap/failure preserveexistingatomiccheckpoints andallattempts, no automaticretry. Aftercompletion orstop, publish safeaggregateevidence andordinarycommit/push only; noRelease. Maintain canonicalfourledgers; LATEST_RUN stays the priorengineeringrun until a separate formalstage acceptance, while LATEST_RESEARCH records thisactualcampaign outcome. Paperdeadline2026-09-27 00:00Beijing; absolutecompute stop9/25 18:00 leaves30hours.

Actual execution command and environment: `reports/s01_execution/S01-20260924T202319Z-30-1cf4769f/validation/RUN_RECEIPT.json`. The executed activation snapshot is commit `98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7`; its manifest is historical and is intentionally not rewritten to describe the closed authorization.
