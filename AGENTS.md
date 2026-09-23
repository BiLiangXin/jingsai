# Project rules

## Data safety

`E题数据/` and other original competition data remain local. Never add them to Git or a Release. Never commit local path configuration, credentials, raw PKL, MP4, or large original spreadsheets.

## Research authority

`DECISIONS.md` records research decisions and `TASK_SPEC.md` limits the active stage. Codex may solve ordinary engineering problems. A change in research meaning requires a `PROPOSED_RESEARCH_CHANGE` entry with `current_decision`, `proposed_change`, `reason`, `expected_benefit`, `risk`, and `required_evidence`; Codex cannot approve its own proposal. Do not start a later stage without authorization.

## Evidence and experiments

Use `VERIFIED`, `SPECIFIED`, `INFERRED`, `HYPOTHESIS`, or `UNKNOWN` precisely. `VERIFIED` requires observed evidence. Never invent tests, Accuracy, F1, MAE, Pearson, losses, runtime, significance, or ablation results. Synthetic fixtures establish engineering behavior only. Competition train learns parameters, valid selects models and thresholds, test is final locked evaluation; special sets are final inference only. No external sentiment training data or pretrained sentiment prediction weights. Preserve the exact neutral label `y = 0` and the stated regression range `[-3, 3]`.

## Git and workflow

Run `git status --short`, scan paths and content, stage only explicit pathspecs, and review `git diff --cached --name-status` before committing. Never use `git add .`, `git add -A`, or `git add --all`. Force push, mirror push, public-history rebase, hard reset of existing work, history rewrite, destructive clean, and remote ref deletion need user approval for the exact command. Normal push and Release require current task authorization and a passing safety gate. Keep run evidence and SHA256 manifests; never claim unrun work passed.
