# S00E PHASE C engineering review

task_id: `S00E_S01_PRESTART_ENGINEERING_HARDENING`
run_id: `20260925-020000-S00E-ASTRA-d9e4edb`
status: `READY_FOR_INDEPENDENT_REVIEW`
activation_commit: `b98fd8fce558bb80aaa22c1cd2c057eab641d54d`
safety_governance_precommit: `078028f022cc175361cb8bf908f760087f35f709`

The separate ordinary safety commit removed both sample-level CSVs from the current branch and corrected current governance/navigation. CURRENT_TREE_REMOVAL != HISTORICAL_ERASURE. A repository owner may assess historical access as a separate PROPOSED_SECURITY_ACTION; no history rewrite was attempted.

Engineering changes enforce the existing aligned baseline mask equalities, post-float32 finite and strict-zero target checks, NumPy/Torch storage separation, and NaN-safe masked pooling. Publication now validates complete mandatory Gate items and scans the tracked public text index/worktree. The S00D test-count constant was replaced with actual pytest collection/execution. Frozen D-DATA-01 through D-DATA-07 and archived S00D evidence were not rewritten.

The birdAL full suite actually collected and executed 221 tests: 221 passed, 0 failed, 0 skipped (exit 0); 25 subtests passed separately. The tiny official aligned TRAIN smoke used a batch of two on CPU and available CUDA, with three-modal pooling, a throwaway linear backward and finite gradients. No optimizer, epoch, checkpoint, prediction, metric, valid/test indexing or Attachment 3/4 content access occurred. The trusted pickle container was deserialized structurally; only its train key was indexed.

The official source SHA256 before/after is `66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd`; it matches the S00D baseline. Aggregate runtime, source evidence and the B01–B13 repair matrix are in `reports/engineering/`. Full code review input is the working-tree diff from the safety precommit plus newly added files listed in the run evidence. The ignored private run directory also contains `PHASE_C_DIFF.patch` for local review.

Astra's second PHASE D review found R01–R04 and M01. This D2 repair adds scalar and duplicate-key scans, run-bound evidence, a manual independent-review approval hard gate, shared runtime/test checks, and actual pytest node-phase proof. E19 remains BLOCKED pending a fresh independent review and trustworthy external approval. E21 remains BLOCKED until E19 and read-only prepublication checks pass. Release verification is postpublication and is not an E21 prerequisite. This evidence does not claim S00E completion or S01 authorization.
