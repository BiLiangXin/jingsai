# Authorized-stage handoff

## Entry point

Run only from the verified official `BiLiangXin/jingsai` clone on `codex/mosei-auto`:

```powershell
python tools/stage_handoff.py --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json
```

The official clone has the local-only Git setting `mosei.officialWorkspace=true`. Verify origin, branch, clean stage boundaries and remote HEAD before setting that marker in a new clone. Linked worktrees and parallel desktop projects cannot publish through this entry point.

Do not invoke handoff for S00B again. Its Release and metadata are already published; `state/LATEST_RUN.json` points to its verified result. A later stage needs its own active and explicitly authorized `TASK_SPEC.md`. The S00B `next_stage_authorized: false` remains in force until Main Research Chat changes the research authorization.

## Required input

The authorized stage writes `reports/runs/<run_id>/public/HANDOFF_INPUTS.json` with exact paths:

```json
{
  "stage": "S01",
  "task_id": "S01_EXAMPLE_AUTHORIZED_TASK",
  "run_id": "<run_id>",
  "public_files": [
    "docs/stage_evidence.md",
    "reports/data_audit/aggregate.json",
    "src/mosei/data/adapters.py",
    "tests/test_stage_s01_data.py"
  ]
}
```

Replace example names with files from the actual authorized task. The command adds `CHATGPT_REVIEW.md`, this run's RUN/GATE/TEST_RESULTS, and the stage acceptance file automatically. The manifest must list every other implementation and public evidence file that should be pushed. Paths are exact files; directories, globs, linked files, absolute paths and `..` are rejected. Reports, documents, safe source and tests must be text files. The tool writes a SHA256 `MANIFEST.json` itself.

Before Git writes, it verifies the active task ID and `research_authorized: true`; official data kind in RUN; nonzero executed tests with zero failures; a passing Gate; and every acceptance evidence SHA256. It scans all selected files for private paths, secrets, raw IDs, sample-level CSV columns, raw-text arrays and test distribution keys. Raw PKL/MP4/Excel, local path config, private/artifact directories and large or binary files are rejected. Failed checks halt publication and are not reported as success.

## Publication order

1. Confirm local and remote branch HEAD match; require an empty Git index and no unrelated working changes.
2. Scan explicit public files, run `git status --short`, stage exact pathspecs, inspect `git diff --cached --name-status` and staged content, and make an ordinary implementation commit/push.
3. Build the Review ZIP from the approved files. Create a Release whose target is the exact implementation SHA. Verify tag target and asset size; download the asset to the ignored run/private directory and compare SHA256.
4. Write `PUBLISH_RECEIPT.json`, update the root review and acceptance hashes, then make and push an ordinary metadata commit.
5. Write `state/LATEST_RUN.json` with the exact implementation and metadata SHAs, Review/Release paths and core public evidence. Make and push a final index commit; verify remote HEAD and Release again.

`branch_head.ref` in the index is a live Git ref. `branch_head.verified_stage_completion_sha` records the exact metadata commit at stage completion. The index commit cannot contain its own SHA, so consumers resolve `branch_head.ref` to get the newest branch HEAD. The index never authorizes the next research stage by itself.

If a push, Release or verification step fails, the command exits nonzero and reports `HANDOFF_FAILED`. It does not force push, clobber an existing asset, erase partial commits or conceal a failed Gate. Inspect the remote branch and Release before retrying a partial publication.
