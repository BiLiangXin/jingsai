# Official workspace and handoff workflow validation

Task scope: engineering publication flow only. No new research stage, model run or raw-data audit was started.

## Workspace reconciliation

- VERIFIED: The official `BiLiangXin/jingsai` clone was clean on `codex/mosei-auto` at the prior S00A commit. Its origin matched the authorized repository.
- VERIFIED: The remote branch was at S00B metadata commit `4b0aa79b059db150f74c10cfe284781a211cda53`. The official clone was safely advanced by `git fetch` and `git merge --ff-only` to that exact commit.
- VERIFIED: The pre-existing desktop `E-S00B` checkout had no staged, modified or nonignored untracked changes and the same HEAD, so its tracked tree did not differ from the synchronized official clone. It also contains ignored local path configuration, private/run artifacts and Python test caches; these remain in place and were not copied or published. The checkout was not deleted or edited. The old desktop `E` source directory was not changed.
- The official clone has a local-only `mosei.officialWorkspace=true` Git marker. The handoff tool also checks that `.git` is a directory, origin and branch are exact, and local/remote HEAD agree. It refuses a linked worktree or an unverified parallel checkout.

## Publication controls

`tools/stage_handoff.py` is the one-command entry point for a **future, separately authorized** stage. It requires an exact-file manifest and verifies TASK_SPEC authorization, real RUN evidence, nonzero executed passing tests, passing Gate and acceptance SHA256 before Git writes. It scans each public file and uses exact Git pathspecs, reviews the staged diff, then performs ordinary commits and pushes. Release target, tag, asset size and downloaded SHA256 are checked before publication is marked verified. A failed check stops the process without a success claim. The former direct `mosei_flow.py publish` entry now exits with a clear refusal, so it cannot bypass this Gate.

The stable `state/LATEST_RUN.json` now points to S00B's already published implementation, metadata commit, Review Release and core evidence. Its `branch_head.ref` is a live pointer; the exact S00B stage-completion SHA is recorded separately because a Git commit cannot contain its own SHA. S00B remains `PENDING_RESEARCH_REVIEW` and `NEXT_STAGE_NOT_AUTHORIZED`.

## Verification boundary

Actual engineering test command: `python -m pytest -q tests/test_stage_handoff.py tests/test_stage_s00b_audit.py tests/test_stage_s00a_bootstrap.py` — **48 passed, 0 failed**. A direct legacy publish command was also run and exited nonzero with the intended refusal. The publisher was exercised with synthetic engineering fixtures only; no new stage was authorized for a live GitHub publication in this task. All new/updated public text files passed the repository safety scan. `git ls-files E题数据/**` returned zero paths. Existing S00B Release metadata was read and matched the index. The engineering [Gate](ENGINEERING_GATE.json) has seven PASS checks. This task does not create another research Release; its code and documentation are versioned through ordinary Git commits on the official branch.
