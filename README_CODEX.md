# Official competition engineering workspace

The verified development clone is this repository on `codex/mosei-auto` with origin `https://github.com/BiLiangXin/jingsai.git`. Keep development here. The old desktop `E` directory is a local data source only; do not create parallel `E-Sxx` projects. Existing folders are retained unless their owner separately authorizes cleanup. Stage code, governance, tests and published reports remain at their current root paths; a future `E/stages/` directory may be added inside this repository if needed.

The latest completed research stage is **S00B_REAL_DATA_AUDIT**. It awaits Main Research Chat review. `NEXT_STAGE_NOT_AUTHORIZED`: do not start S01, train a model, or redefine padding/missing from the audit. Start with [the stable run index](state/LATEST_RUN.json), then [the current research handoff](CHATGPT_REVIEW.md) and [data contract evidence](docs/DATA_CONTRACT_EVIDENCE.md).

## Automatic handoff for a future authorized stage

After that stage's real run, tests and Gate are complete, use the single entry point:

```powershell
python tools/stage_handoff.py --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json
```

The command validates the active `TASK_SPEC.md`, the official clone marker, origin, branch and remote HEAD; checks exact evidence SHA256 and public-file safety; stages only manifest-listed files; reviews the staged diff; makes ordinary commits and pushes; publishes a Release targeting the implementation commit; downloads and hashes its asset; then updates `state/LATEST_RUN.json`. It stops on any failed check. It never force pushes, deletes existing directories, or publishes raw data. See [handoff workflow](docs/HANDOFF_WORKFLOW.md) for the exact manifest and recovery rules.

The local marker is set only in this verified clone with `git config --local mosei.officialWorkspace true`; it is not committed. A fresh official clone must be independently verified before setting it. Existing S00A/S00B releases and reports remain unchanged.
