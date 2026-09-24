# S01 有限实验执行结果

状态：**COMPLETED**。预先选择 30 fits；已启动 30、完成 30、失败 0、资源停止 0、缺少终止事件 0。保留全部 39 项预注册记录。
实际总耗时：5464.000 秒（1.518 小时）。该数字来自最终安全导出，不是预计完成时间。
公共 normalizer：**zscore**；已锁定 clean 参考 B*：**B-CAT-zscore**。
渲染器只展示已有选择记录并复核描述性均值/标准差，没有重新排序、选模型、挑 seed 或读取训练数据。

## 已记录的最终模型

配置：**B-CAT-zscore**；固定 seed：**17**。记录理由：获胜配置的固定 seed17 clean 守卫通过。

| clean VALID 指标 | seed17 实际记录 |
|---|---:|
| Accuracy | 0.631868 |
| macro_F1 | 0.600631 |
| MAE | 0.678381 |
| Pearson | 0.545774 |

Pearson 为 null 时保留原因，不能填 0。以上是已选 seed17 的指标，不是三 seed 均值，也不是 ensemble 指标。

选中 epoch：8；已评价 epoch：18。
checkpoint SHA256：`f34dc27a35be1c149907852094ba9f69a759fb312e65fbc6e50981a41b24fee1`。
该 fit 已解析配置 SHA256：`53d302ef80270dd1cc4d2816066ddf98cc32e7fbf84c01aedc0914ecb013688b`。

## Clean 基线比较

| 配置 | 状态 / 完成 seed 数 | macro-F1 均值 ± SD | MAE 均值 ± SD |
|---|---|---:|---:|
| B-T-identity | COMPLETE_3_SEEDS / 3 | 0.595558 ± 0.003263 | 0.613922 ± 0.004133 |
| B-T-zscore | COMPLETE_3_SEEDS / 3 | 0.599452 ± 0.011987 | 0.642345 ± 0.012294 |
| B-A-identity | COMPLETE_3_SEEDS / 3 | 0.307565 ± 0.013329 | 0.818711 ± 0.035901 |
| B-A-zscore | COMPLETE_3_SEEDS / 3 | 0.365476 ± 0.009694 | 0.845023 ± 0.006930 |
| B-V-identity | COMPLETE_3_SEEDS / 3 | 0.366048 ± 0.010983 | 0.788372 ± 0.004238 |
| B-V-zscore | COMPLETE_3_SEEDS / 3 | 0.385336 ± 0.021955 | 0.774166 ± 0.007475 |
| B-CAT-identity | COMPLETE_3_SEEDS / 3 | 0.601839 ± 0.009791 | 0.674089 ± 0.033511 |
| B-CAT-zscore | COMPLETE_3_SEEDS / 3 | 0.601850 ± 0.003927 | 0.642627 ± 0.031009 |
| LATE-identity | COMPLETE_3_SEEDS / 3 | 0.505057 ± 0.022250 | 0.676099 ± 0.010805 |
| LATE-zscore | COMPLETE_3_SEEDS / 3 | 0.498700 ± 0.032528 | 0.673635 ± 0.007748 |
| PRIOR | COMPLETE_3_SEEDS / 3 | 0.211382 ± 0.000000 | 0.769002 ± 0.000000 |

8 个 B 配置各用预先指定的 17/29/43 三 seed；2 个 LATE 配置复用同 normalizer、同 seed 的单模态模型。PRIOR 的三个记录是同一确定性统计参考，重复记录产生的 SD 不代表独立训练稳定性。未齐全三 seed 时不计算部分均值来替代完整结果。

## C0 / R0 连续局部缺失比较

| 配置 | 状态 / 完成 seed 数 | clean F1 ± SD | clean MAE ± SD | attempted96 F1 ± SD | attempted96 MAE ± SD |
|---|---|---:|---:|---:|---:|
| C0-zscore | COMPLETE_3_SEEDS / 3 | 0.588705 ± 0.011333 | 0.626667 ± 0.012628 | 0.584237 ± 0.003672 | 0.642190 ± 0.009377 |
| R0-zscore | COMPLETE_3_SEEDS / 3 | 0.589968 ± 0.011420 | 0.629770 ± 0.008091 | 0.581642 ± 0.003230 | 0.641933 ± 0.005568 |

以下差值固定为 R0 − C0，仅作描述；F1 越高越好，MAE 越低越好。负增益同样保留，不追加模型或搜索幸运 seed。

| 评价条件 | Δmacro-F1 | ΔMAE |
|---|---:|---:|
| clean | +0.001263 | +0.003103 |
| attempted96 | -0.002595 | -0.000257 |

SD 为三个 seed 的样本标准差（ddof=1），不是置信区间或显著性检验。attempted96 先按每个随机条件的 replicate 求均值，再对 96 个名义条件等权平均，最后跨 seed 汇总；144 视图不是 144 个独立样本。无合法窗口使用 CLEAN_ONCE，不删除样本。

## 执行范围与未运行项

本轮上限为预先授权的 30 fits（B24 + C0/R0 各3）；若执行前锁定 24-fit 降级，则仅 B24，不能声称完成增强机制比较。冻结核心总表仍为 39 fits。R1、R2、R1-CAP 合计 9 fits 继续 NOT_RUN，指标为空；不得写成时序或门控优越性的消融证据。D/T/L、KD、重建、cross-attention、ensemble、unaligned、TAV-local、66-fit 扩展均未纳入。

FAILED、RESOURCE_CAP_STOP、缺终止事件及 NOT_RUN 均保留在 FITS.json；不只展示最佳 seed 或成功尝试。本报告不授权重试、继续训练、test 或专项推理。

## 数据隔离及论文解释边界

仅 train 学习参数和归一化统计；VALID 用于 checkpoint、normalizer、配置和最终守卫选择。重复使用同一 VALID 会带来选择乐观偏差，普通 bootstrap 或三 seed SD 不能消除；本报告不作显著性或无偏泛化结论。test 未用于选择，Attachment3/4 未检查。
结果条件为 KNOWN_AVAILABILITY 人工连续缺失模拟。可靠专项 mask availability 仍为 UNKNOWN；natural structural-zero 不自动等于 artificial missing。窗口比例是 supported 坐标上的位置比例，不能换写成秒级时长；未验证真实时间映射。主 96 条件只覆盖已注册的单/双模态共同窗口，不补写 TAV-local 或 Q3 结论。

## 来源与复现指纹

campaign：`S01-20260924T202319Z-30-1cf4769f`；协议：`R01-FREEZE-01`。
实际执行代码 commit：`98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7`。
执行配置 SHA256：`fac22717e5f736dff917de238757c422e97279a52411ccfe344da1e787afbdf1`。
授权执行 manifest SHA256：`107f5ead4a0dd6b91f21748ae40d7827af452e3a225de2ec9e01fb387ecf4c1d`。
官方输入整体 SHA256：`66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd`；来源是安全导出，本渲染器没有重读原数据。
每个已完成 fit 的源码、预注册/已解析配置、checkpoint 和证据哈希均保留在 FITS.json；checkpoint 本体、原始数据、样本行和私有路径不进入报告。

| 本次只读输入 | SHA256 | 字节数 |
|---|---|---:|
| SUMMARY.json | `662f21c6de17c6e7bb349c1c13afec2000f420d1dd2352389350ac8ec9378fd4` | 4006 |
| FITS.json | `0081bd341f2c692f629da65afe83aee9d03f9257defbf9a2990c700feb88f628` | 118624 |
| CONFIGURATION_SUMMARY.json | `fe8428fe6c5beed7bb5b06cb1a5e7fa551543c1f86c4a23534e342d9231ec914` | 7846 |
| BASELINE_AND_SELECTION.json | `96e41a9de70f70aa9d892b357af1ef067335c73a2acde43d200f7f9902e4a318` | 53487 |

CONFIGURATION_TABLE.csv SHA256：`3abc31305b3d46b4aa7da5f153b47a97a584a5b2cc5c700cc0144b2aa130686e`。
Markdown 指标显示到小数点后6位；CSV 保留17位有效数字，原 JSON 为完整事实依据。

离线报告重现命令（不训练）：

```text
python -B -X utf8 render_results_report.py --input-dir SAFE_EXPORTED_JSON_DIRECTORY --output-dir NEW_EXTERNAL_REPORT_DIRECTORY
```

正式训练命令仅作接口记录，以下占位符不能作为执行授权；本次一次性 campaign 已消费，任何重跑须另行取得未来授权：

```text
python -B -X utf8 tools/s01_train.py official --source AUTHORIZED_ALIGNED_SOURCE --output-dir NEW_AUTHORIZED_PRIVATE_DIRECTORY
```
