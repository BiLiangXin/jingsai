# 数据说明与字段字典

本页汇总已发布的 S00B/C/D 审计事实与当前冻结的工程边界。证据分别见 [S00B 数据审计](DATA_CONTRACT_EVIDENCE.md)、[S00C 支持边界](S00C_SUPPORT_EVIDENCE.md)及 [S00D 数据契约](S00D_DATA_CONTRACT.md)。阶段授权以仓库根目录的 `TASK_SPEC.md` 和 `DECISIONS.md` 为准。公开仓库不提供样本级标签、原始文本或竞赛原始文件。

## 附件与用途

| 附件 | 已核验范围 | 本阶段用途 |
| --- | --- | --- |
| 1 | 100 个 MP4、对应标签表与文件级完整性 | Q1 来源规则登记；S00E 不提取特征 |
| 2 | aligned/unaligned 官方特征的 train/valid 完整审计；test 仅有限完整性检查 | S00E 只用 aligned TRAIN 极小批次做工程 smoke |
| 3 | 文件级 inventory | 最终专项推理；S00E 不打开内容 |
| 4 | 文件级 inventory | 最终专项推理；S00E 不打开视频或特征内容 |

附件1的音频来源为实际 MP4 声轨，文本来源为官方 `label-100.xlsx` 的 `text` 列，视觉来源为 MP4 帧。这是主研究负责人提供的 2026-09-24 竞赛论坛专家答复，证据状态为 **SPECIFIED**，本阶段没有独立复核论坛原文。默认保留全部 100 条；音文不一致、静音、非英语、不清楚或无人脸均需记录不确定性，不自行丢弃或强制对齐。异常到 missing 的精确映射仍未决定。

## 官方附件2接口

两版均含 train 3,395、valid 728、test 727 条，版本间 split ID 集合与顺序一致。test 数量属于完整性记录；test 标签分布、样本级标签及指标不在公开材料中展示。train/valid 的实际标签映射为 Negative=0、Neutral=1、Positive=2；连续回归范围为 [-3,3]，仅严格等于零为 Neutral。官方 PKL 没有 `annotations` 字段；附件2标签工作簿为 train/valid 提供了核验所需的文字极性。

官方样本标识的实际分隔符为 `$_$`。公开材料只记录格式与唯一性检查结果，不列出完整 ID。连续特征与原始 `raw_text` 不得混为同一个字段；`text_bert` 是整数数组，通道 1 在 train/valid 是非空连续的二值前缀。

| 版本 | text | audio | vision | 接口状态 |
| --- | --- | --- | --- | --- |
| aligned | (N,50,768) | (N,50,74) | (N,50,35) | D-DATA-01 冻结为 S01 首个受控基线接口 |
| unaligned | (N,50,768) | (N,500,74) | (N,500,35) | 后续独立对照；不得混合接口 |

74 维音频和 35 维视觉特征没有已核验的逐维物理含义。unaligned `audio_lengths` 与 `vision_lengths` 是源文件声明的长度；S00C 证实部分视觉非零行出现在声明长度之后，因此不能仅凭长度把那些行判定为有效观察或 padding。没有已核验的特征位置到秒级时间映射。

## 冻结的 aligned 基线数据契约

共享 `support` 取 `text_bert` 通道 1 等于 1 的非空连续前缀；`padding = NOT support`。text observed 等于 support；audio/vision observed 等于 support 且该位置原始整行不为精确零。自然结构零行只标为 `STRUCTURAL_ZERO`，不自动等于缺失、填充或人工损坏。人工损坏另用显式 mask。未选定最终 missing 规则。

首个基线的模型输入仅允许连续 text/audio/vision 与明确的 mask 元数据。分类和回归标签仅作为目标；ID、raw_text、划分、附件3/4统计都不是预测输入。train 估计可学习的标准化统计量；identity 与 train-only z-score 只是备选基础设施，最终选择仍待授权阶段比较。

## 隔离与公开约束

train 用于参数及统计量学习，valid 仅用于之后获授权的模型选择，test 保留给最终锁定评价。附件3/4只用于最终专项推理，不能被 S00E 的工程 smoke 读取。S00E 不训练正式模型，不产生预测指标。

竞赛原始 PKL、MP4、大型 Excel、样本级标签、完整原始文本与 token dump 保持本地，不进入 Git 或 Review Release。公开运行证据只包含必要的聚合结构、哈希、测试及 Gate 状态。
