# Research decisions

Fields: `decision_id | status | decision | evidence | reason | date | affected_stages`.

| decision_id | status | decision | evidence | reason | date | affected_stages |
| --- | --- | --- | --- | --- | --- | --- |
| ENG-001 | FROZEN | This fresh clone is the sole official development repository; the old E directory is a local source only. | VERIFIED remote main SHA and clean clone | Avoid carrying old Git history and tracked raw data | 2026-09-23 | S00A onward |
| RES-001 | UNDECIDED | Aligned versus unaligned feature interface | UNKNOWN | Requires later research review and data audit | 2026-09-23 | S00B onward |
| RES-002 | UNDECIDED | Padding and observation semantics | UNKNOWN | Requires actual data audit | 2026-09-23 | S00B onward |
| RES-003 | UNDECIDED | Missingness and corruption design | UNKNOWN | Requires research authorization | 2026-09-23 | Later stages |
| RES-004 | UNDECIDED | Model, loss, and distillation | UNKNOWN | Requires research authorization | 2026-09-23 | Later stages |
| RES-005 | UNDECIDED | Explanation and time mapping | UNKNOWN | Requires research authorization and mapping evidence | 2026-09-23 | Later stages |

Valid status values: `UNDECIDED`, `PROVISIONAL`, `FROZEN`, `REOPENED`.
