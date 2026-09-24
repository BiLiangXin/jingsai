# S01 aggregate reporting tools

These standard-library tools export and render existing campaign evidence. They do not contain a training entry point or grant permission for another model run. Use them after the campaign has exited. Keep private campaign directories and every newly generated export/report outside the Git repository.

Run commands from the repository root after installing this directory as `tools/s01_reporting`:

```text
python -B -X utf8 -m unittest discover -s tools/s01_reporting -p "test_*.py" -v
python -B -X utf8 tools/s01_reporting/export_campaign.py --campaign PRIVATE_CAMPAIGN_DIRECTORY --destination NEW_EXTERNAL_SAFE_EXPORT
python -B -X utf8 tools/s01_reporting/export_condition_aggregates.py --campaign PRIVATE_CAMPAIGN_DIRECTORY --main-export NEW_EXTERNAL_SAFE_EXPORT --destination NEW_EXTERNAL_CONDITION_EXPORT
python -B -X utf8 tools/s01_reporting/render_results_report.py --input-dir NEW_EXTERNAL_SAFE_EXPORT --output-dir NEW_EXTERNAL_RENDERED_REPORT
```

Replace uppercase path placeholders with local directories. The main exporter defaults to `docs/EXPERIMENT_REGISTER.json`; `--registry` can supply the same canonical public preregistration from another checkout. The condition exporter defaults to the hash-verified `research/r01/reference.py`; `--reference` can select that frozen public file explicitly. If the campaign lacks its final status file, both exporters require the actual completed external watchdog record through `--watchdog-receipt`. They reject missing or mismatched evidence; they do not reconstruct events or restart the campaign.

The main export preserves all 39 preregistered fits, including failures, incomplete attempts and deferred fits. Only completed fits supply final metrics. The condition export uses the existing 96 nominal conditions / 144 views, checks the main export manifest and private input fingerprints, and streams selected checkpoint bytes solely for SHA256 verification. It exports counts and aggregate metrics. Three-seed means stay null until seeds 17, 29 and 43 have all completed.

Tests read only two public metadata files: `docs/EXPERIMENT_REGISTER.json` and `research/r01/reference.py`. Their synthetic fixtures are written to the operating system temporary directory. `S01_REPORTING_PROJECT` can override the inferred repository root; `S01_REPORTING_TEST_TMP` can select an existing external temporary directory. These two path settings are useful when testing this folder before publication. Artificial path and metric sentinels in the fixtures are synthetic redaction probes, not private workstation information or official experimental results.

The renderer reads four safe JSON payloads, validates counts and recorded selections, and recomputes descriptive means/standard deviations for presentation. It does not independently validate the main export manifest: render the freshly verified, unchanged main export. It does not recompute the model-ranking decision or derive predictive metrics from sample labels. Markdown displays six decimal places; its CSV preserves 17 significant digits. Missing Pearson values retain their reasons, incomplete seed groups retain missing means, and the fixed seed17 selection remains the recorded selection. Its report covers configuration comparisons; detailed condition/factor outputs remain in the separate condition export.

Repeated use of VALID for selection still causes optimistic bias. Seed standard deviations and condition summaries are descriptive. These tools provide no TEST results, attachment inference, new significance claim or additional training authorization.

`PORTABILITY.json` records the unchanged helper hashes, the test-only path adaptations, and the actual portable-copy check counts. The independent aggregate-export review applies to the exact main and condition helper hashes; changing helper code requires a new review of the change.
