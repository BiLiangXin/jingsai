# Authorized-stage handoff

## Entry point

Run only from the verified official `BiLiangXin/jingsai` clone on `codex/mosei-auto`:

```powershell
python tools/stage_handoff.py --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json
```

The older `python tools/mosei_flow.py publish` command is disabled. It cannot bypass this entry point's Gate, safety, Git and remote-asset checks.

The official clone has the local-only Git setting `mosei.officialWorkspace=true`. Verify origin, branch, clean stage boundaries and remote HEAD before setting that marker in a new clone. Linked worktrees and parallel desktop projects cannot publish through this entry point.

Do not invoke handoff for a completed stage again. `state/LATEST_RUN.json` currently points to S00D's verified result; S00E is active under its own `TASK_SPEC.md`. Invoke the handoff only after the current stage's real run, tests, all mandatory Gates and required independent review pass. S01 remains unauthorized.

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

Before Git writes, it verifies the active task ID and `research_authorized: true`; official data kind in RUN; actual nonzero executed tests with zero failures; every mandatory Gate item PASS; and every acceptance evidence SHA256. It scans the complete tracked public text tree, index changes and selected files for private paths, secrets, raw IDs, sample-level CSV columns, raw-text arrays and test distribution keys. Raw PKL/MP4/Excel, local path config, private/artifact directories and large or binary files are rejected. Failed checks halt publication and are not reported as success.

For S00E, E19 requires an actual passing independent Phase D review bound to the reviewed code, tests and probe evidence by SHA256 and to the same task/stage/run. A model name, editable review JSON, or local `approved=true` field cannot authenticate independent approval. The verifier first accepts an owner-controlled detached SSH signature over the canonical review and manifest digest, checked against live GitHub signing keys for BiLiangXin. The signature stays in run/private/OWNER_APPROVAL.sig. No signing key is generated or enrolled by the agent. When no signature exists, the user-authorized local fallback directly re-reads the pinned native Codex task journal: the exact digest question, accepted tool request, and linked role=user approval must agree. Repository copies and editable receipts are ignored. This trusts the local Codex host and OS account, does not resist a compromised local account, and is not cryptographic authentication. The approval question displays that boundary. Invalid signatures do not fall back. Missing, declined, duplicated, stale or unlinked native approval retains MANUAL_REVIEW_APPROVAL_REQUIRED. Any reviewed source/report or manifest change requires fresh review and exact-digest confirmation. The synthetic tests inject a controlled verifier only to exercise validation logic; that does not grant a real approval. Pytest node IDs and setup/call/teardown records stay in the ignored run/private directory; the public test record contains their hashes and dynamically checked counts. E21 is `PREPUBLICATION_SAFETY_PREFLIGHT`: E01–E20 must pass, then run `python tools/s00e_preflight.py --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json`. This command is read-only and checks the current repository, Gate, evidence, test record, official source hash, tracked index/worktree, and explicit publication files. Its receipt can support E21 PASS only after the checks succeed. The final publisher independently repeats the critical checks before staging; it does not trust a saved receipt alone. Commit, push, Release, downloaded asset SHA256, and remote HEAD verification occur after E21 PASS.

## Publication order

1. Confirm local and remote branch HEAD match; require an empty Git index and no unrelated working changes.
2. Scan explicit public files, run `git status --short`, stage exact pathspecs, inspect `git diff --cached --name-status` and staged content, and make an ordinary implementation commit/push.
3. Build the Review ZIP from the approved files. Create a Release whose target is the exact implementation SHA. Verify tag target and asset size; download the asset to the ignored run/private directory and compare SHA256.
4. Write `PUBLISH_RECEIPT.json`, update the root review and acceptance hashes, then make and push an ordinary metadata commit.
5. Refresh and verify stage acceptance hashes after the final Review status and metadata update. Write `state/LATEST_RUN.json` with the exact implementation and metadata SHAs, Review/Release paths and core public evidence. Make and push a final index commit; verify remote HEAD and Release again.

`branch_head.ref` in the index is a live Git ref. `branch_head.verified_stage_completion_sha` records the exact metadata commit at stage completion. The index commit cannot contain its own SHA, so consumers resolve `branch_head.ref` to get the newest branch HEAD. The index never authorizes the next research stage by itself.

If a push, Release or verification step fails, the command exits nonzero and reports `HANDOFF_FAILED`. It does not force push, clobber an existing asset, erase partial commits or conceal a failed Gate. Inspect the remote branch and Release before retrying a partial publication.

## GOV-ASTRA-SERIAL-01

The user authorized local Astra High serial engineering closeout on 2026-09-25. No manual Sol/Astra switching and no mandatory Web Chat CORE ZIP. Freeze writes during a real independent Astra High review, and repeat review after changes. Keep local hashes, actual run records and safe code differences. The existing formal Review Release ZIP and downloaded SHA256 verification remain required. Only after S00E acceptance and publication are verified may the research line resume; S01 training is still unauthorized.

Update docs/PROJECT_SUMMARY.md, docs/RESEARCH_LOG.md, docs/EXPERIMENT_REGISTER.json and docs/PAPER_CLAIMS.md at significant checkpoints. Model metrics stay null in engineering runs. Missing trustworthy approval provenance is a hard blocker; an editable approval field is never a substitute for the user's actual local confirmation of the specific reviewed digest.

Implementation staging uses a per-command core.autocrlf=false override and verifies exact index/worktree bytes before commit. The formal Review Release is built from implementation-commit bytes, with the same content scanner, membership and CRC checks. Independent report review_evidence_sha256 freezes the actual reviewed runtime/tests/probe/report bytes as well as source hashes.
