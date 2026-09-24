task_id: S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS
status: ACTIVE
research_authorized: true
next_stage_authorized: false
previous_stage: S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF
stage_type: data_contract
research_owner: Main Research Chat
execution_agent: Codex GPT-6 Sol
task_version: 1.0
你现在执行新的正式阶段：

S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS

这是 S00C 通过 Main Research Chat 审核后的正式工程/科研接口冻结阶段。

不得自行启动 S01 模型训练。

==================================================
1. 启动与仓库状态
==================================================

正式仓库：

BiLiangXin/jingsai

正式分支：

codex/mosei-auto

Main Research Chat 已核验的最新远端 HEAD：

10e191a6682d9d8e94097d79db70f7fe7df8737b

最新已完成阶段：

S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF

真实 run：

20260924-014331-S00C-afeafae

首先读取：

AGENTS.md
DECISIONS.md
TASK_SPEC.md
CHATGPT_REVIEW.md
state/LATEST_RUN.json
state/NEXT_ACTIONS.md
docs/DATA_CONTRACT_EVIDENCE.md
docs/S00C_SUPPORT_EVIDENCE.md
docs/HANDOFF_WORKFLOW.md

以及 S00B/S00C 所有与 schema、mask、zero、length、
split、label 和 source integrity 有关的公开证据。

确认：

- origin 正确；
- 当前 branch 正确；
- local/remote HEAD 合理一致；
- 工作树没有其他未审核任务的修改；
- official-workspace marker 正确。

不得创建桌面 E-S00D 等平行 Git 项目。
只在正式仓库内继续。

不得删除旧 E、E-S00B 或其他目录。

==================================================
2. 激活新的 TASK_SPEC
==================================================

将根 TASK_SPEC.md 更新为：

task_id: S00D_DATA_CONTRACT_FREEZE_AND_BASELINE_READINESS
status: ACTIVE
research_authorized: true
next_stage_authorized: false
previous_stage: S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF
stage_type: data_contract
research_owner: Main Research Chat
execution_agent: Codex GPT-6 Sol

本阶段不进行模型性能实验。

不得训练正式 baseline。

不得修改以下科研决定的含义。

==================================================
3. 本轮正式冻结的数据合同
==================================================

将以下决定正式记录到 DECISIONS.md。

不能自行修改其科研含义。

------------------------
D-DATA-01
------------------------

S01 第一阶段 primary baseline interface：

aligned_50.pkl

状态：

FROZEN_FOR_BASELINE

它不是最终 aligned/unaligned 性能胜负结论。

unaligned 保留为后续受控 comparator。

不得写：

aligned is superior

只能表达：

aligned is the primary controlled baseline interface.

------------------------
D-DATA-02
------------------------

必须区分：

support mask
observed mask
corruption/missing mask

不得复用一个 mask 表达三个概念。

对于 aligned：

M_support[t] =
text_bert[:, 1, t] == 1

这是 S01 operational sequence-support rule。

它不声称 continuous text 在 mask 外数值为0。

S00C 已 VERIFIED：
mask 外 continuous text 实际仍非零。

------------------------
D-DATA-03
------------------------

对于 aligned audio/vision：

ZERO_ROW(m,t) =
all(feature dimensions == 0)

定义：

M_observed[m,t] =
M_support[t] AND NOT ZERO_ROW(m,t)

对于 text：

M_observed[text,t] =
M_support[t]

当前不根据 continuous text 的数值是否为0决定 support。

------------------------
D-DATA-04
------------------------

自然出现的 ZERO_ROW 一律称：

STRUCTURAL_ZERO

禁止自动称：

MISSING
PADDING
INVALID_OBSERVATION

缺失必须是独立的显式状态。

未来人工 corruption 使用单独：

M_corruption

不得通过 value == 0 反向推断人工 missing。

------------------------
D-DATA-05
------------------------

S01 aligned 的 operational padding：

M_padding = NOT M_support

所有 temporal pooling /
sequence aggregation /
attention summary /
loss-related temporal reduction

必须能够排除 padding positions。

注意：

ZERO_ROW != PADDING

这是正式合同。

------------------------
D-DATA-06
------------------------

第一版模型允许输入：

text continuous feature
audio
vision

text_bert channel 1 仅作为 mask metadata。

不把 text_bert 作为第四模态。

第一版不重新运行 BERT。

禁止作为预测特征：

id
raw_text
classification label
regression label
split membership
附件3/4任何统计信息。

targets：

classification_labels
regression_labels

------------------------
D-DATA-07
------------------------

所有 learned normalization statistics
只能使用 train 计算。

valid/test/附件3/4：

禁止参与 mean/std/min/max/quantile 等统计估计。

本阶段只建立 normalization infrastructure，
不选择最终 scaler。

至少支持：

none
train-only z-score

但具体选择保持 UNDECIDED，
等待 S01 valid 对比。

==================================================
4. DataContract 正式代码化
==================================================

建立清晰的数据合同模块。

建议位置：

src/mosei/data/

但可结合现有项目结构合理实现。

至少需要：

data_contract.py
dataset.py
masks.py
normalization.py

名字允许做轻微工程调整，
但职责必须分离。

建立不可含糊的数据结构，例如：

AlignedSample / AlignedBatch

至少显式包含：

text
audio
vision

text_support_mask
audio_support_mask
vision_support_mask

text_observed_mask
audio_observed_mask
vision_observed_mask

classification_target
regression_target

内部调试可有 sample key，
但模型 forward 默认不得获得 raw id。

不要用：

mask

作为无上下文的唯一字段名。

必须明确命名语义。

==================================================
5. aligned shared-support 规则实现
==================================================

在代码中实现：

support = text_bert channel 1 == 1

并验证：

dtype 合法；
shape == (N,50)；
值仅为 0/1；
每个样本形成连续 active prefix；
至少一个 active position；
长度不超过50。

支持区域外：

continuous text 即使非零，
默认也不得进入 pooled/aggregated model representation。

不要修改原始 text tensor。

只通过 support mask 控制后续有效范围。

audio_support_mask =
vision_support_mask =
text_support_mask

因为 aligned 题面定义为共同对应序列位置。

但是：

audio_observed_mask =
support AND NOT audio_zero_row

vision_observed_mask =
support AND NOT vision_zero_row

不得据此把 zero row 叫 missing。

==================================================
6. structural zero contract
==================================================

实现统一函数：

structural_zero_mask(x)

规则：

每个时间位置所有 feature dimension 精确为0。

输出仅代表：

stored structural zero

不得返回字段名：

missing_mask

建立显式 contract tests 确认：

padding position 可以是非零 text；
support position可以出现 audio structural zero；
support position可以出现 vision structural zero；
zero != padding；
zero != corruption。

==================================================
7. artificial corruption interface
==================================================

本阶段不实施正式 Q2 missing simulation，
但建立未来安全接口。

设计独立：

CorruptionMask

或等价明确数据结构。

默认所有位置：

false

必须保证：

人工 corruption 只能在允许区域显式产生；
不能通过 tensor 数值反推 corruption；
padding 不能被统计为人工 missing；
自然 structural zero 不能自动加入 corruption mask。

不得在 S00D 决定：

missing ratio
missing duration distribution
modality combinations
simulation schedule

这些仍属于之后的科研决策。

只建立接口。

==================================================
8. normalization infrastructure
==================================================

实现：

IdentityNormalizer

以及：

TrainOnlyZScoreNormalizer

要求：

fit() 只接受 train adapter/dataset。

保存：

mean
std
count
feature dimensions
fit split
config version

对于时间序列统计，
必须明确 mask 规则。

S00D 第一版规定：

用于计算统计量的位置 =
support AND observed

audio/vision：
M_observed

text：
M_support

padding 不进入 normalization stats。

结构零行默认不参与 audio/vision scaler fit，
因为它们不是观测 feature vector。

但不得把这种排除解释成：
“zero就是missing”。

它只是 normalization 的 observed-vector
统计规则。

std 为0的 feature 必须安全处理，
不得产生 NaN/Inf。

本阶段不得根据 valid 指标选择 normalizer。

==================================================
9. label contract
==================================================

将已经 VERIFIED 的标签编码写成正式合同：

Negative -> 0
Neutral -> 1
Positive -> 2

regression：

[-3,3]

且：

y < 0 => Negative
y = 0 => Neutral
y > 0 => Positive

建立 assert / validation。

不得重新编码成：

negative=0
positive=1

这种二分类形式作为数据底层 contract。

以后模型若需要派生 binary metric，
应另建派生 target，不覆盖官方三类标签。

==================================================
10. split / leakage contract
==================================================

硬编码或统一验证：

train：
唯一允许 fit model parameters /
fit normalization statistics 的 split。

valid：
只用于未来模型结构、超参数、阈值、
early stopping/model selection。

test：
LOCKED / QUARANTINED。

S00D 不读取 test 数值统计，
除非当前 TASK 明确已有的 schema-level 验证需要；
优先不要重新访问。

Attachment3/4：
完全不内容读取。

必须建立自动测试防止：

normalizer.fit(valid)
normalizer.fit(test)

以及 Dataset factory 误把 test
加入 training loaders。

==================================================
11. Dataset / DataLoader contract
==================================================

建立一个可被未来 PyTorch 模型直接使用的
baseline-ready adapter。

但本阶段不进行真正模型训练。

要求：

train/valid 可以创建 batch。

batch tensor shape 稳定：

text  : B x 50 x 768
audio : B x 50 x 74
vision: B x 50 x 35

support mask：

B x 50

observed mask：

每模态 B x 50

targets shape 明确。

dtype 明确。

必须保证：

没有 raw_text；
没有 sample ID；
没有 split 字符串；
没有 test-derived statistics

进入模型输入 dict。

可以为 debug 返回单独 metadata，
但必须与 model_inputs 明确分离。

==================================================
12. masked pooling primitive
==================================================

实现简单、模型无关的：

masked_mean
masked_sum

以及需要的 mask broadcast helpers。

测试：

padding values 改成任意巨大值时，
masked pooling 结果不变。

这是非常关键的契约测试。

尤其针对 continuous text：

在 support mask 外随机修改非零尾部，
masked pooled result 必须保持不变。

这将工程化验证：

非活跃 text 存储值不会意外泄漏进模型表示。

==================================================
13. 真实数据 contract audit
==================================================

使用官方 aligned train/valid
运行一次只读 contract validation。

不得训练。

验证：

样本数；
shape；
dtype；
标签；
support continuity；
zero-mask；
observed-mask；
normalization fit；
batch creation；
finite values。

重新确认源文件前后 SHA256 不变。

生成新的聚合证据：

docs/S00D_DATA_CONTRACT.md

reports/data_contract/
  contract_summary.json
  mask_summary.json
  label_contract.json
  normalization_contract.json
  loader_contract.json
  source_mutation_check.json

不能输出：

raw ID list
raw_text
token dump
sample-level labels
feature arrays
私人路径。

==================================================
14. Tests
==================================================

补充高质量合成测试。

至少覆盖：

1. support mask 正确提取；
2. 非二值 channel 拒绝；
3. non-prefix support 拒绝；
4. structural zero detection；
5. zero != padding；
6. zero != corruption；
7. observed mask；
8. padding exclusion；
9. text 非零尾部不能影响 masked pooling；
10. audio/vision support 内 zero 行处理；
11. train-only normalization；
12. valid fit 被拒绝；
13. test fit 被拒绝；
14. std=0；
15. NaN/Inf 防护；
16. label contract；
17. exact neutral zero；
18. model input 不含 ID/raw_text；
19. shape/dtype；
20. source no mutation；
21. Attachment3/4 guard；
22. test quarantine；
23. serialization/reload normalizer consistency；
24. deterministic batching under fixed seed（如使用 shuffle测试）。

运行：

python -m pytest -q tests

不得只运行新增 tests。

所有现有 S00A/B/C 测试仍必须通过。

==================================================
15. S00D Gate
==================================================

建立至少以下 Gate：

D01 official workspace + S00D authorization
D02 S00C evidence dependency verified
D03 aligned primary baseline interface encoded
D04 support / observed / structural-zero separation encoded
D05 padding contract encoded
D06 corruption interface separated
D07 label contract verified
D08 train-only normalization enforced
D09 model input allowlist enforced
D10 dataset/batch contract verified
D11 masked pooling leakage test passed
D12 real aligned train/valid contract audit completed
D13 source files unchanged
D14 test quarantine preserved
D15 Attachment3/4 isolation preserved
D16 public safety scan passed
D17 complete pytest suite passed
D18 documentation and evidence complete

每项：

PASS / FAIL / SKIPPED / BLOCKED

并带 evidence。

不得降低 Gate 以获得 SUCCESS。

==================================================
16. 阶段状态
==================================================

SUCCESS 需要：

真实 aligned train/valid contract validation 成功；
所有关键 contract tests 通过；
所有 Gate 通过；
源数据未修改；
数据边界未违反；
自动 handoff 完成；
Release 验证完成。

BLOCKED：

如果真实 schema 与合同无法兼容；
当前证据不能安全构造 baseline adapter；
数据/权限/环境阻止可靠执行。

FAILED：

数据泄漏；
修改原始文件；
读取专项测试内容；
使用 test fit scaler；
伪造测试；
错误 mask 语义仍宣称成功；
原始数据被 Git/Release 打包。

==================================================
17. DECISIONS.md
==================================================

将 Main Research Chat 本轮冻结决定写入 DECISIONS.md。

必须清楚区分：

FROZEN_FOR_BASELINE

和：

FINAL_MODEL_DECISION

不能把 aligned baseline selection
误写成最终模型优胜方案。

unaligned final role：

保持 UNDECIDED。

normalizer final choice：

保持 UNDECIDED。

missing simulation：

保持 UNDECIDED。

model architecture：

保持 UNDECIDED。

==================================================
18. 自动发布
==================================================

真实 contract audit
→ tests
→ Gate
→ acceptance
→ HANDOFF_INPUTS
→ stage_handoff.py
→ commit/push
→ Release
→ download SHA256 verification
→ state/LATEST_RUN.json

使用：

python tools/stage_handoff.py \
  --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json

不得手工绕过 handoff Gate。

==================================================
19. Web Chat handoff
==================================================

遵守 AGENTS.md 当前规则。

最终回复前生成新的、
唯一 bundle-id 的 Web Chat handoff ZIP。

必须包含本轮：

response.json
MANIFEST.json
README.md
CHATGPT_REVIEW.md
state/LATEST_RUN.json
DECISIONS.md
docs/S00D_DATA_CONTRACT.md
核心 contract JSON
Gate
Tests
PUBLISH_RECEIPT

前提是所有文件通过安全扫描。

不要重复使用旧：
webchat-20260924-001

生成新的 unique bundle。

==================================================
20. 严格禁止
==================================================

S00D 不允许：

训练 baseline；
比较 Accuracy/F1/MAE/Pearson；
设计 Transformer/LSTM/MoE；
设计最终融合网络；
missing simulation 实验；
蒸馏；
重建；
Q3解释算法；
读取 Attachment3/4 内容；
根据 test 调参；
宣布 aligned 最终胜出；
宣布 structural zero 就是 missing。

==================================================
21. 完成后停止
==================================================

最终：

PENDING_RESEARCH_REVIEW
NEXT_STAGE_NOT_AUTHORIZED
STOPPED_AFTER_S00D

不得自行开始 S01。

最终聊天回复按照 AGENTS.md JSON schema，
并提供新的 Web Chat ZIP 绝对路径。

等待 Main Research Chat 审核。