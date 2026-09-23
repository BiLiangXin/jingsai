task_id: S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF
status: ACTIVE
research_authorized: true
next_stage_authorized: false
previous_stage: S00B_REAL_DATA_AUDIT
research_owner: Main Research Chat
execution_agent: Codex GPT-6 Sol
stage_type: targeted_data_audit
task_version: 1.0
# Codex GPT-6 Sol：执行 S00C 数据边界诊断与真实自动交接验证

## 一、任务身份与权限

你是本项目的工程和实验执行代理。主研究负责人根据已完成的 S00B 真实审计，授权本轮目标明确、范围有限的后续数据诊断任务。

**本次任务：**

`S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF`

本轮只负责进一步调查真实数据中的有效范围、候选 mask 和零值结构问题，并验证新的自动 GitHub 交接流程可以在真实研究运行后安全完成发布。

本次授权不包含 S01、模型训练、最终特征版本选择、最终 padding/missing 定义或任何问题2/问题3算法设计。

本指令作为主研究负责人发布的 S00C 阶段规格。首先将其准确落实到正式仓库根目录的 `TASK_SPEC.md`，再执行后续工作。

阶段头信息必须为：

```yaml
task_id: S00C_SUPPORT_BOUNDARY_EVIDENCE_AND_REAL_HANDOFF
status: ACTIVE
research_authorized: true
next_stage_authorized: false
previous_stage: S00B_REAL_DATA_AUDIT
research_owner: Main Research Chat
execution_agent: Codex GPT-6 Sol
stage_type: targeted_data_audit
```

本次 S00C 授权仅限本指令所列的研究问题、实现与发布工作。不得自行扩大为模型开发阶段。

## 二、必须首先完成的仓库检查

正式仓库：

`BiLiangXin/jingsai`

正式开发分支：

`codex/mosei-auto`

已核验的本轮参考 HEAD：

`1b0b20901deca9017637bf4974e26ff3529c8ed0`

首先读取以下正式仓库文件：

1. `AGENTS.md`
2. `DECISIONS.md`
3. `TASK_SPEC.md`
4. `CHATGPT_REVIEW.md`
5. `state/LATEST_RUN.json`
6. `state/NEXT_ACTIONS.md`
7. `docs/DATA_CONTRACT_EVIDENCE.md`
8. `docs/HANDOFF_WORKFLOW.md`
9. S00B 的真实审计报告、关键 JSON、测试、Gate 和现有实现代码

核对最新 GitHub 分支状态。如果最新 HEAD 与上述参考提交不同，先核实新增提交的实际内容，不能盲目覆盖。

只能在已经核验的正式开发仓库中执行工作。不得在桌面竞赛目录中创建新的平行 `E-S00C` 或其他 Git 仓库。

不要修改、清理、删除旧 `E` 和 `E-S00B` 目录。原始竞赛数据只能通过安全的本地路径配置读取。

首先检查当前工作区是否有未提交改动。如果存在其他任务的工作，不得覆盖或擅自清理。

## 三、阶段激活

目前 GitHub 根目录 `TASK_SPEC.md` 仍是 S00B 的冻结规格。S00B 已完成，但旧规格不能自动授权 S00C。

根据本指令创建新的 S00C 阶段规格，替换当前根目录 `TASK_SPEC.md`，明确本轮目标、数据使用边界、实施要求、输出、测试、Gate、失败条件及停止条件。

必须保留现有 `AGENTS.md` 的长期治理规则，不得因为切换阶段而重写其研究权限、数据安全或 Git 安全规则。

保持 `DECISIONS.md` 中尚未冻结的科研决定不变。可以记录已经核验的 S00B 数据事实及本轮研究边界，但不得将尚未取得充分证据的假设直接标记为 FROZEN。

先完成阶段激活的独立安全检查，再对本次规格使用精确 pathspec 暂存、普通 commit 和普通 push。确认远端根目录的 `TASK_SPEC.md` 已正确激活 S00C，之后才能读取本地官方 PKL 开始真实诊断。

不得把规格激活提交伪装成 S00C 真实数据审计的 implementation commit。

## 四、S00B 基线核对

本次任务不重复整个 S00B，而是基于已有证据开展针对性调查。

S00B 的真实 run_id：

`20260924-001338-S00B-fc277357`

已报告的 train/valid/test 样本数为：

* train：3395
* valid：728
* test：727

Aligned 和 unaligned 两版各4850条样本。Train/valid 的实际分类编码为 Negative=0、Neutral=1、Positive=2。

读取并交叉核对 S00B 原始聚合报告、生成这些报告的程序和测试。检查其记录是否彼此一致。

本轮诊断应能重现以下已报告的关键事实：

* Unaligned audio 声明长度之后的非零行数为0。
* Unaligned vision 声明长度之后，train 为36,928个非零行，valid 为8,455个非零行。
* Unaligned vision 的 train 中，声明长度内部还有30个零值行。
* `text_bert` 第1号通道是 attention-mask 候选通道，train/valid 均呈连续活跃前缀。
* Aligned 候选非活跃位置上的 `text` 连续特征仍然非零。

如果本轮重新计算的结果与 S00B 不同，先检查数据版本、代码、统计口径、路径及输入顺序，明确记录差异来源。不得静默修改旧报告或调整统计方法使结果看起来一致。

## 五、研究问题 A：Unaligned 视觉声明长度诊断

本节只对附件2官方 unaligned 数据中的 train 和 valid 进行深入诊断。

使用已有长度诊断代码作为工程基础，补充以下样本级计算和公开聚合结果：

1. 每条样本的 `vision_lengths`、存储序列长度、最后一个非零特征行位置，以及声明长度后的非零行数。
2. 声明长度之后非零行的连续结构、相对位置、距离声明边界的偏移和零值间隔。
3. 声明长度内部非零与零行的结构，包括前缀、尾缀和内部零值段。
4. 声明长度前后特征行范数的聚合分布，检查后续非零值的数量级及其与内部非零值的关系。
5. 检查异常是否集中于少量样本，或分布于大量样本。
6. 检查不同声明长度区间中的异常频率，以及是否存在可复现的 off-by-one 或固定偏移现象。
7. 检查整段视觉全零样本与声明长度是否一致。
8. 对音频重复必要的对照统计，解释音频和视觉的实测结构差异。

允许使用仅包含聚合统计的直方图、分位数表和交叉统计表。不公开原始样本 ID、原始特征、样本级标签或敏感本地路径。必要的样本级诊断留在 gitignored 的私人目录。

必须将以下事项严格区分：

* 官方声明的长度；
* 数值非零位置；
* 推断出的候选支持区域；
* 是否存在真实观测；
* 是否构成模态缺失。

尤其不能仅因为声明长度之外存在非零值，就断言官方长度一定错误，也不能据此认定后续非零值都是有效原始观测。

本阶段必须保留无法通过现有数据判断的情况，并给出缺少哪类独立证据。

## 六、研究问题 B：Aligned 文本候选 mask 诊断

本节仍只对 train 和 valid 进行真实诊断。

检查 `text_bert` 的实际形状、dtype、第1号通道的二值性、连续活跃前缀和各样本候选活跃长度。

对 aligned 连续 `text` 特征，比较候选活跃和非活跃位置的数值结构，包括：

* 非零行比例和聚合范数；
* 同一样本尾部各行是否存在完全相同或高度相似的特征；
* 尾部非活跃位置是否具有可重复的数值结构；
* 候选活跃区域与非活跃区域的数值分布差异；
* 候选 mask 与音频、视觉结构性零行的位置交叉关系。

只进行数值诊断，不使用互联网恢复 token、下载外部 MOSEI 标签或运行未授权的 BERT 重新编码。

如果部分关系能得到较强证据，应明确标记 `INFERRED`；如果仍无法解释，应保持 `UNKNOWN`。

不得把候选 attention mask 直接定义为连续文本特征的最终 padding 规则。

## 七、研究问题 C：结构零值与候选有效范围

基于已有的 zero-row 和 zero-run 实现，对 train/valid 进行必要的补充聚合诊断。

必须保留 S00B 已冻结的机械零值检测含义，不得修改原始数组或替换零值。

区分并报告：

* 全零模态样本；
* 前缀零值段；
* 尾缀零值段；
* 两端零值段；
* 内部连续零值段；
* 多个内部零值段；
* 与候选文本活跃区域重叠的零值段；
* 与 unaligned 声明长度发生位置冲突的零值段。

对音频和视觉分别报告，不能简单合并后给出统一解释。

报告哪些现象能直接由真实数组验证，哪些仅能提出假设，哪些必须等待后续科研实验。

不对结构性零值自动赋予 missing、padding 或 invalid observation 的含义，也不修改已有样本集合。

## 八、数据使用和安全边界

本轮只允许对附件2官方 train/valid 开展新增数值诊断。

Test 继续严格隔离。不得重新计算 test 标签分布、数值特征分布、候选 mask 分布，也不得用 test 做任何边界选择或科研判断。S00B 已完成的合法性与一致性检查可作为历史证据引用。

附件3和附件4本轮不读取内容。不得反序列化专项 PKL、分析真实 missing 分布、检查专项特征值、抽帧或分析专项视频。

外部 MOSEI 数据、第三方情感数据及互联网标签禁止用于本轮诊断。

只能从用户本机已经确认可信的官方竞赛源文件读取。不得重新下载未知 pickle，原始文件只读，审计前后记录文件大小、mtime 和 SHA256，发现改变立即停止并报告。

默认依次加载所需官方特征文件；避免长期同时持有 aligned 和 unaligned 两份完整对象。若现有 S00B 聚合证据足以支持某项结论，无须为形式而重复加载全部数据。

不得修改已有 S00B 历史结果或 Release。

## 九、输出数据合同证据

建立独立的 S00C 公开证据文件，不覆盖原有 S00B 审计产物。

至少产生：

* `docs/S00C_SUPPORT_EVIDENCE.md`
* `reports/data_audit/s00c_vision_length_boundary.json`
* `reports/data_audit/s00c_text_mask_diagnostics.json`
* `reports/data_audit/s00c_zero_mechanism_matrix.json`
* `reports/data_audit/s00c_s00b_reconciliation.json`
* `reports/data_audit/s00c_source_mutation_check.json`

具体 JSON 字段可按真实工程需要细化，但不得改变本任务的科研含义或减弱隔离要求。

`S00C_SUPPORT_EVIDENCE.md` 必须按 VERIFIED、SPECIFIED、INFERRED、HYPOTHESIS、UNKNOWN 整理。

每项主要发现应标明实际来源、计算口径、证据文件、已知限制和需要主研究负责人审核的问题。

单独设置研究决策候选表，列出能够由本轮证据支持的候选含义和仍存在的替代解释；该表不是最终科研决定。

## 十、工程测试与阶段 Gate

补充针对本轮诊断代码的合成工程测试。至少覆盖：

* 长度边界和越界值；
* 全零样本；
* 内部连续零值段；
* 多段零值；
* 声明长度之后的非零行；
* 特征行范数及统计汇总；
* mask 连续性和非活跃位置诊断；
* 数据审计结果可复现；
* train/valid 限制；
* test quarantine；
* 附件3/4禁止内容读取；
* 数据不变性；
* 公开报告脱敏；
* 交接清单完整性。

真实运行本轮所需的官方 train/valid 数据诊断，记录命令、环境、实际样本数和真实执行结果。合成测试通过不得代替真实数据证据。

建立 S00C 阶段 Gate，至少包含：

* C01：正式仓库与阶段授权核验。
* C02：S00B 基线证据读取与一致性核对。
* C03：官方源文件可信及前后完整性核验。
* C04：train/valid 使用边界与 test quarantine。
* C05：unaligned 视觉长度补充诊断完成。
* C06：音频长度对照诊断完成。
* C07：aligned 文本候选 mask 诊断完成。
* C08：结构零值交叉诊断完成。
* C09：科研事实、推断和未知严格区分。
* C10：工程测试真实运行通过。
* C11：公开报告安全及原始数据保护检查。
* C12：数据合同证据、run 和验收文件完整。

每项必须记录 PASS、FAIL、SKIPPED 或 BLOCKED 及真实证据。

数值异常本身不等于工程失败；但是没有完成要求的统计、发生数据泄漏、违反隔离或伪造结果，不能被标记为成功。

## 十一、真实运行与阶段产物

为本轮创建唯一 run_id，不覆盖已有运行目录。

必须创建：

* `reports/runs/<run_id>/RUN.json`
* `reports/runs/<run_id>/GATE.json`
* `reports/runs/<run_id>/TEST_RESULTS.json`
* `reports/runs/<run_id>/public/HANDOFF_INPUTS.json`
* `reports/stages/S00C/acceptance.json`

RUN 必须真实记录本轮读取了哪些官方文件、实际执行的诊断、数据边界、前后哈希核验及运行状态。

由于本轮执行真实官方数据诊断，RUN 的 `data_kind` 应使用现有发布工具接受的真实官方数据类别，而不是把实际研究运行伪装为纯合成工程任务。

对于仍无法判定的科学含义，应记录 UNKNOWN，不得因为科学解释尚未冻结而伪造工程失败，也不得用 Gate PASS 冒充科研结论成立。

如真实数据证据与 S00B 已核验的事实冲突，明确列出冲突及代码复核结果，必要时停止发布，交由主研究负责人决定是否需要重开审计。

## 十二、使用新的自动交接流程

完成真实运行、全部必要测试和阶段 Gate 后，使用仓库当前唯一的自动交接入口：

```powershell
python tools/stage_handoff.py --manifest reports/runs/<run_id>/public/HANDOFF_INPUTS.json
```

先根据 `docs/HANDOFF_WORKFLOW.md` 建立精确文件清单。必须包含本轮必要的公开代码、测试、聚合报告和数据合同证据。不得使用目录通配符或整个仓库导出。

该入口必须核验正式工作区、origin、分支、远端 HEAD、当前 TASK_SPEC 授权、真实 RUN、测试、Gate、阶段验收证据及公开文件安全。

只能执行安全的精确 staging、普通 commit/push 和本轮已授权的 Review Release。禁止使用 force push、filter-repo、destructive clean 或任何旧历史清理流程。

Release target 必须为实际通过测试和 Gate 的 implementation commit。发布后下载资产，比对 SHA256、资产大小和 tag target，并更新稳定运行索引 `state/LATEST_RUN.json`。

这次是该自动流程首次用于新阶段的真实研究发布。遇到普通工程故障可自主诊断、修复和重跑，但不得为了获得成功而削弱 Gate、安全扫描或修改科研协议。

如发布失败，记录真实的部分提交、远端 Release 状态及失败原因，检查后安全恢复。不得凭已存在的部分资产声称完整成功。

## 十三、Web Chat 自动交接 ZIP

遵守最新 `AGENTS.md` 的 Web Chat handoff 规则。

使用现有 `tools/web_chat_handoff.py` 为最终回复生成独立、可上传网页 Chat 的本地 ZIP，包含 `response.json`、`README.md`、`MANIFEST.json` 和理解本轮结果必需的公开文件。

本地 ZIP 与 GitHub Review Release 是不同的交接产物：二者都必须安全核验，不能相互替代。

最终回复给用户提供该本地 ZIP 的真实绝对路径、SHA256、运行状态、实际测试与 Gate 结果，以及最新 GitHub Review、Release 和稳定索引路径。

如果无法生成或核验 ZIP，明确报告失败，不得给出虚构路径。

## 十四、主研究审核入口

本轮最终 `CHATGPT_REVIEW.md` 必须包含：

* task_id、run_id、状态；
* 正式仓库和分支；
* baseline、implementation、metadata 提交；
* 真实运行和源文件完整性证据；
* S00B 基线数值重现情况；
* unaligned 视觉长度诊断；
* aligned 文本候选 mask 诊断；
* 结构零值交叉结果；
* tests 和 Gate；
* 未解决的科学问题；
* 对后续数据合同的候选建议及替代解释；
* 发布记录和 SHA256；
* `PROPOSED_RESEARCH_CHANGE`，没有则明确 NONE。

最终只将具有证据支持的事实标为 VERIFIED，科研解释按其证据等级标记。

不得自行修改 `DECISIONS.md` 中未获授权的核心科研决定，不得宣布已经选择主特征版本或确定最终 padding/missing 规则。

如果出现必须变更已冻结科研协议的情况，生成完整 `PROPOSED_RESEARCH_CHANGE`，停止越界执行，等待主研究负责人审核。

## 十五、完成条件

按以下闭环执行：

阶段激活与远端核验 → 基线审查 → 真实针对性诊断 → 聚合报告 → 测试 → Gate → 数据合同证据 → 公开安全扫描 → 自动 Git/Release 交接 → 远端核验 → Web Chat ZIP → 停止。

最终状态必须明确：

`PENDING_RESEARCH_REVIEW`

`NEXT_STAGE_NOT_AUTHORIZED`

`STOPPED_AFTER_S00C`

不允许自行开始 S01、训练 baseline、实施模型融合、蒸馏或重建，也不允许将新的统计证据直接宣布为最终模型设计。

将全部真实结果与公开证据交回 Main Research Chat，等待下一次科研审核。
