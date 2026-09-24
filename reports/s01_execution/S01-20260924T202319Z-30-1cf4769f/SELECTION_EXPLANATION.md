最终记录选择为 **B-CAT-zscore，固定 seed 17，checkpoint epoch 8**。独立审计通过：30 项拟合全部完成，另 9 项保持 NOT_RUN；本文只解释已冻结、已核验的选择，不改变选择或追加实验。

阅读提示：`SUMMARY.counts.RUNNING=30` 是 30 次 RUNNING 启动转换事件的累计数，不是当前活动任务数。安全记录的终态为 COMPLETED，30 项 fit 均为 COMPLETED、另 9 项为 NOT_RUN；主流程已确认训练子进程 exit 0 并核验退出记录，本实际审计在退出确认后执行，当前无活动拟合。

共同标准化方案由 B-CAT 的三个预设种子（17、29、43）clean 指标按冻结顺序确定；11 个基线配置的冻结排序得到 B*=B-CAT-zscore。zscore 与 identity 的 B-CAT clean macro-F1 均值分别为 0.6018501688585941、0.6018390196740434，差仅 0.000011149185（约 0.001115 个百分点）。这是触发既定排序的微小描述性差异，不构成 zscore 优越性或显著性证据。

C0/R0 进入 attempted96 排序前须同时通过跨种子 clean 均值约束：F1 ≥ B*−εF，MAE ≤ B*+εMAE；冻结 εF=0.01、εMAE=0.05。因此本轮门槛为 **F1 ≥ 0.5918501688585941，MAE ≤ 0.6926265293924392**。C0 的 clean F1 为 0.5887049674873907，R0 为 0.5899681933913419，二者均未达到 F1 门槛，虽各自 MAE 通过，仍不能进入候选排序。

下表为三个预设种子的均值；attempted96 沿用“随机重复→名义条件等权→种子”的冻结聚合顺序。显示值四舍五入，判断使用导出的完整精度。

| 配置 | clean macro-F1 | clean MAE | attempted96 macro-F1 | attempted96 MAE | clean 均值约束 |
|---|---:|---:|---:|---:|---|
| B-CAT-zscore（B*） | 0.60185017 | 0.64262653 | 0.58621845 | 0.65453883 | 基线参照 |
| C0-zscore | 0.58870497 | 0.62666690 | 0.58423725 | 0.64218979 | F1 未通过；MAE 通过 |
| R0-zscore | 0.58996819 | 0.62976994 | 0.58164232 | 0.64193262 | F1 未通过；MAE 通过 |

因此，**seed17 检查之前的胜者已经是基线 B***。记录中的 `WINNER_FIXED_SEED_GUARD_PASS` 表示所选基线 seed17 相对自身的检查通过；它不表示 C0/R0 通过了约束，也不表示鲁棒候选取得胜利。此次没有触发“候选 seed17 失败后回退 B*”的分支。

R0 相对 C0 的 attempted96 macro-F1 差为 -0.00259493，保留“本轮 attempted96 未观察到 F1 增益”的负结果；其 attempted96 MAE 差为 -0.00025717。clean F1 则小幅增加 0.00126323，仍未通过相对 B* 的门槛，不能将 attempted96 的负结果扩写为所有条件均退化。以上为同一 VALID 上的选型描述，未作显著性检验或独立泛化结论；未使用 TEST 或附件3/4。

证据：[安全导出清单](MANIFEST.json)，SHA256 `51d30a562282a672c78c15dfbd45585f1036bbe6bc084e328f2456b3c2fb9339`，绑定 [配置汇总](CONFIGURATION_SUMMARY.json) 与 [基线及选择](BASELINE_AND_SELECTION.json) 的完整内容；[独立实际审计](validation/ACTUAL_FROZEN_CHOICES_AUDIT.json)，SHA256 `f106895f5a1eb0cc15114dae6abd7834f02cdfcbfb2a6863128c64fcd9a834aa`。审计依据已记录汇总与 epoch 日志，未重算样本预测；本说明仅读取这些安全导出和既有审计，原审计保持不变。
