# S02 aggregate export

This implementation performs result aggregation and evidence validation only. It does not authorize or execute model work. The original draft was checked with10 synthetic tests before official execution. At closeout,12 synthetic tests passed after a final-checkpoint/stop validation fix. The terminated real S02 campaign was then read read-only and38 safe aggregate members were exported, retaining148 completed epoch rows. See the campaign validation receipts for exact evidence.

After the parent has confirmed campaign termination:

```text
python -B -X utf8 export_results.py --campaign <private-campaign> --output <new-external-export> --project <public-repository>
```

The output directory must be new and outside the campaign and repository. A terminal `campaign_status.json` is required; a killed process without terminal evidence is rejected. All checks precede output creation. Symlink/reparse paths are rejected. Selected/last checkpoint and component-cache files are streamed for whole-file SHA256 only, never deserialized.

Outputs are `SUMMARY.json`, all twelve `FITS.json` records, all fifteen `POSTPROCESS.json` configurations with all three seed slots, validated `COMPARISON.json`, `EPOCH_CURVES.csv`, `EPOCH_CURVES.json`, per-fit `epochs/*.json`, per-configuration `conditions/*.json`, `FACTOR_DESCRIPTIVES.csv`, and a verified file manifest. JSON condition/epoch records are split by configuration or fit to keep individual public files below 1 MiB.

Durable event transitions establish fit/configuration completion. Missing work has null metrics. A failed fit may retain completed epoch rows and checkpoint file hashes while its final metrics remain null. An optimizer marker establishes an attempted update; completed epoch events establish training progress. Partial W configurations preserve complete per-seed evaluations without complete-seed means or ranking. No retry is performed or accepted in the event history.

Epoch train metrics explicitly retain `ONLINE_PRE_UPDATE_CURRENT_VIEW_DIAGNOSTIC_NOT_CHECKPOINT_EVALUATION`; they are not renamed clean train checkpoint performance. All recorded completed epochs from all seeds, including failed/partial fits, are retained. A partially completed epoch with no durable row is not invented. Loss components, population counts, epoch chronology, early stopping and selected checkpoint traces are checked against the frozen reference.

The exporter checks the 96-condition/144-view structure and pairing privately, averages random replicates before equal-condition summaries, and permits across-seed means only for the full prescribed set. Condition tables contain aggregate eligibility, coverage and CLEAN_ONCE counts. Raw masks, individual predictions/labels/IDs, pairing/population fingerprints, private paths, coefficient arrays and weights are omitted. Public error messages retain exception categories only.

The recorded candidate summaries, promotion eligibility, robust ranking and Pareto set are recomputed from aggregate inputs using the exact reviewed selection source. This verifies the recorded finite protocol, not a new search. Historical S01 baseline summaries retain that evidence scope. New champion publication requires matching terminal status and comparison hashes in the atomic champion pointer, plus exact restore evidence; a transaction gap or changed hash rejects export.

Synthetic checks: run `python -B -X utf8 test_export_results.py` with `S02_PROJECT_ROOT` set to the public project root. The test expects the exporter as a sibling file; both are retained in this directory. Historical draft run had10 tests, all PASS, exit0,10.323seconds; this is not the closeout test count. The complete fixture includes twelve fits, fifteen W configurations, nineteen condition grids, all three seeds and all durable epoch records. Negative checks cover source failure, partial fit/W evidence, checkpoint mutation, population mismatch, undefined Pearson, nonfinite metrics, premature selection and stale promotion transaction hashes.

`EXPORT_SYNTHETIC_CHECKS.json` retains the exact local command/environment and is private because it contains workstation paths. Publish a sanitized receipt with explicit substitutions and whole-file hashes if needed. This is author self-check evidence, not an independent review. No model metric, campaign result or model runtime in these fixtures represents official data.

Final closeout delta: model inference-cost summaries now equal the mean of completed fit measurements. The installed sibling test suite passed13checks. A new test fixture initially failed on string seed keys, corrected to integer keys; both actual logs are retained and hashed in REPORTING_CHECKS.json. No model was rerun. Final export manifest: `f17a92169830ed8bf458579ce8196f94c211496084d46dfbfc070efc9e95708c`. All38 aggregate output bytes equal the previous verified export; only exporter source binding changed.
