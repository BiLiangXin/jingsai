# S03-EXEC-01 / GOV-ASTRA-MEDIUM-02

SPECIFIED by the current explicit user instruction. Astra / medium for author and independent read-only reviewer; user confirmed the UI setting, no runtime model telemetry is claimed. Overrides historical High/next-stage prohibition only for this new bounded S03 and conditional S04. Single official-tree writer. S01/S02 remain CONSUMED; zero new fits, no optimizer or buffer updates. No change to D-DATA-01..07 or historical results. Exact-path safe commit/push authorized; no Release.

Budget starts conservatively at 12:40 Beijing, ends 16:40 on 2026-09-25, also bounded by the preexisting 18:00 ceiling. Offline evidence writing may continue. Prior source HEAD and full request hash are in configs/s03_execution.json. Backup/restore, existing figures, Q1, deployment, Q3, final gates, paper are serial stages. Restore tolerance is fixed before comparison: atol=1e-6, rtol=1e-5; identical device also reports exact equality.

## S03-DEPLOY-01 — before new results

Only V0 and V1, each with existing M2 seeds17/29/43. The predictor adapter receives only visible continuous features and support. Evaluate clean and the same 96 nominal/144 views. Evaluation creates corruption from frozen S/O and sets corrupted raw contents to zero BEFORE the adapter. Original S/O/C remain separate evaluation objects. Ineligible rows use the clean prediction once and remain in every attempted condition. Replicate means precede equal condition means, then seed means; repetitions do not increase sample count.

V0 text A=S; audio/vision A=S AND NOT visible exact whole-row zero. V1 every modality A_proxy=S AND NOT visible exact whole-row zero. Both computed before normalization. Transform only available vectors with the frozen TRAIN mean/std; set unavailable contents to standardized zero for safety. The proxy is not observed/corruption truth. No label, ID, text, token ID, split, O or C enters the adapter. No fitting or thresholds.

Eligibility requires clean F1 loss<=0.01 AND MAE increase<=0.05 versus original M2 at BOTH three-seed mean and fixedseed17. Eligible profiles ranked by attempted96 F1 desc, MAE asc, clean F1 desc, MAE asc, exact tie V0. Never change seed/epoch/champion. Both fail => BLOCKED, do not inspect Attachment3.

## S03-Q3-01 — before explanation results

Fixed M2seed17, original clean KNOWN_AVAILABILITY for VALID explanation. Exact three-group Shapley: phi_m=sum over U excluding m of |U|!(2-|U|)!/3! * [v(U union m)-v(U)]. Absent coalition contents become standardized zero (TRAIN mean); every mask and b/rho stays fixed. Classification v is the SAME full-input predicted-class logit across all eight coalitions; regression v is scalar intensity. Signed phi and abs(phi)/sumabs(phi) reported separately; exactly zero sumabs => NO_RESOLVABLE_EFFECT with null relative effects, not thirds. Check efficiency and full-coalition equality at the preregistered numeric tolerance.

Full VALID receives group explanations. Local cases fixed before local computation: first six ascending VALID ordinals in each true class x correct/error stratum, at most36; never fill a short stratum using result-dependent choices. Windows width3 supported positions, stride1, affect only A=true contents. Up to3 disjoint windows separately ranked by absolute fixed-class delta and absolute regression delta; ascending start breaks ties. Signed effects retained. Equal-length random disjoint windows from fixed seed3103; deletion/retention comparisons retain all cases and negative results. Full-minus-deleted and retained-minus-empty are reported, alongside absolute magnitudes; no guaranteed faithfulness gain or causal claim. Attention/gates auxiliary only.

Official feature index does not imply time. Q1 self-generated alignment cannot establish Attachment4 mapping. Mapping without verified source correspondence returns timestamp=null / UNVERIFIED_MAPPING, blocking Attachment4 gate. No special data used to develop methods.

## Final gates and evidence

Before the first special open: freeze weights/scaler, algorithm, schema/error handling, VALID checks, independent exact-hash review, FINAL_INFERENCE_SPEC and manifest, then commit. Q2 and Q3 gates independent. No special distribution adaptation. Private sample outputs/weights/frames/official submission stay outside Git; safe aggregates/code/docs only. Four existing ledgers reused. Existing VALID comparisons are optimistically selected; sample SD is not a CI/significance. All historical NOT_RUN entries retained.
