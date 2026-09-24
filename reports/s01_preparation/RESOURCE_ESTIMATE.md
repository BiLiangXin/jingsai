# S01 deadline-aware resource proposal

**PROPOSED_NUMERIC_RESOURCE_CAP — no owner execution authorization.** Paper deadline is2026-09-27 00:00 Beijing. Proposed compute stop is2026-09-25 18:00, leaving30hours for results, writing, revision, formatting and submission.

| Plan | New fits | Planning estimate | Proposed hard cap | Decision |
|---|---:|---:|---:|---|
| Frozen full core |39|27.87h|28h, comparison only|Does not fit the deadline; not active |
| Deadline proposal |30|11.49h|12h total;2h/fit|B24+C0/R0six; defer9temporal/gating fits |
| Before-start fallback |24|2.99h|4h total;1h/fit|B only; no empirical robustness-enhancement claim |

R01 core remains39 and all39 are preregisteredNOT_RUN/metricsnull. Switching to24/30 occurs before any official experiment and is bound to owner approval. The currentproposal is30. Never select a downgrade after observing performance. At a cap, preserve partial/failed evidence and stop without claiming a complete seed set.

The12hour plan must start by9/25 06:00;4hour plan by14:00. Approval arriving later requires a new feasible pre-execution decision, never silently moving the18:00 cutoff or reducing the paper buffer. No automatic training is scheduled.

## MEASURED: closed synthetic hardware and complete path

Python3.11.14,PyTorch2.9.1+cu128,CUDA12.8,cuDNN91002,oneNVIDIA GeForce RTX5070Ti(17,094,344,704bytes VRAM),Ryzen7 2700X8cores/16threads,34,261,053,440bytes systemRAM. Exact environment and volume-free snapshots:resource_profile.json andscaled_profile.json. CPUthreads4,deterministic algorithms,TF32off,cuDNNbenchmarkfalse. Timed CUDA microregions synchronize before/afterperf_counter; complete fit uses finite-value synchronization and finalCUDA synchronization.

Syntheticdense50tensors use the frozen768/74/35dimensions, valid masks and artificial targets. Closed factory exposes no inputdata argument. Full-size3395train/728valid counts come only from the historical public data-contract aggregate, not originalPKL. Fixtureseeds7301/7302;modelseed17. Six architectures actually ran one syntheticepoch each, including modelcheckpoint roundtrip and the restored-checkpoint144-view evaluation. The public reports suppress predictive metrics; private synthetic checkpoints are not Git artifacts.

| Architecture | Measured train loop seconds | Checkpoint validation seconds | Final selected-checkpoint validation seconds |
|---|---:|---:|---:|
|B-T|1.73446|0.15837|25.13374|
|B-A|1.80100|0.16351|26.32300|
|B-V|1.77870|0.15471|25.65378|
|B-CAT|1.91559|0.19388|29.45803|
|C0|2.54474|36.42478|36.83268|
|R0|3.59855|36.79993|36.82474|

B checkpoint usesclean only each epoch; its selectedcheckpoint receives one extra completegrid report. C0/R0 checkpoint usesclean+144views each epoch. This fixes the initial reviewer finding that baseline work was wrongly multiplied by144 everyepoch. Masks are computed once per population; eligible-only inference and CPUmetric aggregation are included in actual timing.

The microprofile also measures all9architectures atbatch32 andR2/R1-CAP at8/16/32/64/128/256, with3warmups and10timedsteps/forwards. The maximum actually tested safe batch is256, not the physicalmaximum (UNKNOWN). NoOOM occurred;OOMboundary=null. Largest sampled allocatedGPUtensor memory is300,376,576bytes; this excludes driver/context/otherprocess memory. Fixed trainingbatch remains32. GlobalGPU guard is80%of totalmemory;privateartifactcap5GiB. No batch selection uses officialvalid.

## ESTIMATED: finite campaign

For directly measured architecturea:

`fit_seconds(a) = 1.25 × [100 × (train_epoch_seconds + checkpoint_validation_seconds + 0.25) + final_validation_seconds + measured_fixed_seconds] + 60`.

The25%factor covers ordinary runtime fluctuation beyond the measured completepath. Additional allowance is0.25seconds/epoch forcheckpoint persistence,60seconds/fit forIO and0.5hours/campaign fordatahashing/preprocessing,masklibrary,normalizers,prior/late reused evaluation and bookkeeping. No early-stop or favorable-performance discount is used. Identity/zscore share the same dense modelpath; normalization is outside epoch loops and covered by setup/IO allowance. OnlyIdentity was used in the scaled profiler, so zscore officialoverhead remains unmeasured.

The three deferredtemporal/gating architectures have microprofile measurements but no full-sizeepoch measurement. Full39comparison scales R0 bythe larger ofstep/forwardmaximum ratios, clamped at1; it is explicitlyINFERRED. It is not used to activate those9fits. Sourceprofile hashes, exact arithmetic, counts, conservative allowances and estimatedperfit values are inRESOURCE_ESTIMATE.json; code:tools/s01_resource_estimate.py.

These are planningupperestimates, not mathematical or empirical bounds onofficialruntime. A single dense syntheticepoch and limitedbatch sweep cannot guarantee officialtiming, noOOM, diskperformance or systemload. Wall-time/VRAM/storage guards may stop a campaign early. Officialdata epoch time, fullfit time, modelranking, F1/MAE/Pearson andsignificance remainUNKNOWN/null.

## Preserved negative/history evidence

resource_profile_attempt_1.json andresource_estimate_attempt_1.json retain the originalmicroprofile andsuperseded72hproposal. That profile preceded completecommand/sourcebinding; do not treat it as exactfinalsource proof. Finalresource_profile.json/scaled_profile.json bind measured sourcehashes andunchanged-source checks. The original72hproposal is not an activecap. Initial independent findings and finaldelta review are separate from owner approval.

Reproduction commands (existingenvironment, no downloads/data):

```text
python -B -X utf8 tools/s01_resource_profile.py --output NEW_MICRO_PROFILE_JSON
python -B -X utf8 tools/s01_scaled_profile.py --private-output-dir NEW_EXTERNAL_DIRECTORY --report NEW_SCALED_PROFILE_JSON
python -B -X utf8 tools/s01_resource_estimate.py --profile NEW_MICRO_PROFILE_JSON --scaled NEW_SCALED_PROFILE_JSON --output NEW_ESTIMATE_JSON
```

Originalmeasurements are never overwritten; newmeasurements obtain newpaths. Syntheticoptimizer steps are NOT_MODEL_EXPERIMENT. Currenttraining_authorized=false, normalizerNOT_YET_SELECTED, no officialdata/test/Attachment3/4inspection.
