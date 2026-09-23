# TASK_SPEC.md — S00B_REAL_DATA_AUDIT

task_id: S00B_REAL_DATA_AUDIT
status: ACTIVE
research_authorized: true
next_stage_authorized: false

task_version: 1.1
research_owner: Main Research Chat
execution_agent: Codex GPT-6 Sol
stage_type: data_audit
previous_stage: S00A_LOCAL_RECOVERY_AND_BOOTSTRAP

## 1. Objective

对本机真实官方竞赛数据进行严格、只读、可复现的数据审计。

本阶段只建立后续科研决策所需的数据事实，不训练模型，不选择 aligned / unaligned，不最终冻结 padding / missing，不设计鲁棒模型，不开展问题1特征提取，不开展问题3解释算法，不读取附件3/4专项数据内容。

核心问题：

- 真实 schema；
- train / valid / test 真实样本数；
- ID 格式、唯一性和 split 边界；
- 标签真实编码；
- regression / classification / annotation 一致性；
- text / text_bert 实际结构；
- attention-mask candidate；
- zero rows；
- continuous zero runs；
- audio_lengths / vision_lengths；
- aligned 候选有效位置；
- NaN / Inf；
- aligned / unaligned identity 和 label consistency；
- split exact ID overlap；
- video_id 跨 split；
- 附件1完整性；
- 附件3/4 file-level inventory 与隔离证明。

所有结论严格使用：

- VERIFIED
- SPECIFIED
- INFERRED
- HYPOTHESIS
- UNKNOWN

不得把推断写成 VERIFIED。

## 2. Frozen S00B research protocols

以下协议在本阶段冻结，Codex 无权修改。

### D-S00B-01 — train / valid audit

附件2 train 和 valid 允许完整数据审计。

允许检查真实字段、数值结构、标签编码、分布统计、零值结构、length consistency、跨版本一致性等本 TASK_SPEC 明确授权的事项。

### D-S00B-02 — test quarantine

附件2 test：

QUARANTINED。

仅允许检查：

- schema；
- field names；
- shape；
- dtype；
- sample count；
- ID integrity；
- NaN / Inf；
- label field existence；
- label shape；
- label legal range；
- aligned / unaligned identity consistency。

禁止利用：

- test 详细类别分布；
- test 回归分布；
- test sample-level labels；
- test distribution；

进行任何：

- 科研设计；
- 模型选择；
- 阈值选择；
- 参数选择；
- 特征版本选择；
- padding / missing 定义。

公开报告不得输出 test 的详细类别比例、回归均值方差、直方图、sample-level labels。

必须明确：

```
TEST_LABEL_DISTRIBUTION_QUARANTINED=true
```

### D-S00B-03 — Attachment 3 / 4 isolation

附件3和附件4：

S00B 只允许 FILE-LEVEL INVENTORY。

附件3禁止：

- 反序列化专项 PKL；
- 分析 missing 比例；
- 分析 missing 位置；
- 分析模态组合；
- 读取专项特征内容。

附件4禁止：

- 反序列化专项特征；
- 分析实际特征值；
- 分析视频内容；
- 对视频运行视觉、语音或文本处理。

附件3必须证明：

```
CONTENT_NOT_INSPECTED=true
```

附件4必须证明：

```
FEATURE_CONTENT_NOT_INSPECTED=true
VIDEO_CONTENT_NOT_INSPECTED=true
```

### D-S00B-04 — no final research definitions

S00B 不得最终决定：

- aligned / unaligned 主方案；
- padding 数学定义；
- missing 数学定义。

S00B 只负责提供 VERIFIED / SPECIFIED / INFERRED / HYPOTHESIS / UNKNOWN 证据。

最终科研定义必须等待 S00B 完成后，由主研究对话单独审核和冻结。

## 3. Competition-specified expectations

以下来自赛题原文，状态属于 SPECIFIED，不得在真实审计完成前写成 VERIFIED：

- 附件1包含100条原始视频样本；
- 附件1包含37个以 video_id 命名的子文件夹；
- `label-100.xlsx` 每行对应一个视频样本；
- 附件2 aligned 版本总计4850条样本；
- 附件2 unaligned 版本总计4850条样本；
- aligned 题面形状：
  - text `(N,50,768)`
  - audio `(N,50,74)`
  - vision `(N,50,35)`
- unaligned 题面形状：
  - text `(N,50,768)`
  - audio `(N,500,74)`
  - vision `(N,500,35)`
- unaligned 的 `audio_lengths` / `vision_lengths` 描述音频和视觉有效长度；
- 情感强度合法范围为 `[-3,3]`；
- `0` 只属于 Neutral；
- ID 题面格式为 `video_id$_$clip_id`；
- `text_bert` 为 BERT 三路整数输入，不构成第四模态。

真实审计必须记录实际观测值并与这些 SPECIFIED expectations 对比。

若实际值与题面不一致：

不得静默修复，不得擅自删除或补齐样本。

必须报告：

```
COMPETITION_SPEC_MISMATCH
```

并保存证据供主研究负责人审核。

## 4. Local data & pickle safety

正式仓库不得复制原始竞赛数据。

使用 gitignored 的：

```
configs/paths.local.json
```

或等价本地配置指向真实 `E题数据/`。

公开报告必须使用：

```
<LOCAL_DATA_ROOT>
```

代替私人绝对路径。

只允许在：

```
trusted_competition_pickle=true
```

时加载用户本机官方竞赛 pickle。

禁止从：

- Internet；
- GitHub；
- 第三方网盘；
- 未知来源；

下载并反序列化 pickle。

不得写回、覆盖或修改原始竞赛文件。

## 5. Memory safety

aligned / unaligned 数据较大。

默认顺序：

1. load aligned；
2. 完成聚合统计；
3. 保存必要 ID / label / digest / metadata；
4. `del`；
5. `gc`；
6. load unaligned；
7. 完成聚合统计；
8. `del`；
9. `gc`。

跨版本比较优先保存：

- ID；
- labels；
- field digest；
- raw_text hash；
- aggregate metadata。

不要长期同时持有两份完整对象。

普通内存优化不得改变审计语义。

## 6. Source mutation protection

审计开始前，对 aligned / unaligned 官方源文件记录：

- file name；
- size；
- mtime；
- SHA256。

审计结束后重新记录并比较。

如果 hash 发生改变：

```
CRITICAL_DATA_MUTATION
```

本阶段状态必须 FAILED 并停止。

不得通过重新下载或覆盖文件掩盖差异。

## 7. Schema audit

分别生成：

- `reports/data_audit/schema_aligned.json`
- `reports/data_audit/schema_unaligned.json`

记录：

- file_name；
- size；
- sha256；
- python_type；
- top-level keys。

对每个 split 记录：

- field_names；
- sample_count。

对每个字段记录：

- Python type；
- dtype；
- shape；
- ndim。

寻找但不得预设一定存在：

- id；
- raw_text；
- text；
- text_bert；
- audio；
- vision；
- annotations；
- classification_labels；
- regression_labels；
- audio_lengths；
- vision_lengths。

其他字段记录为：

```
EXTRA_FIELDS
```

检查所有 sample-aligned 字段第一维长度一致性。

输出：

```
reports/data_audit/split_consistency.json
```

如发现第一维严重不一致：

```
DATA_ALIGNMENT_FAILURE
```

不得继续假设索引对应关系成立。

同时核对各版本全部 split 样本数之和是否与赛题 SPECIFIED 的4850一致。

实际值属于 VERIFIED。

题面4850属于 SPECIFIED。

二者必须分别标注。

## 8. ID audit

检查：

- empty ID；
- duplicate ID；
- train-valid exact ID overlap；
- train-test exact ID overlap；
- valid-test exact ID overlap。

公开报告只输出异常 count。

如需定位异常样本，公开报告使用：

```
SHA256(sample_id)
```

不得公开原始 sample ID 列表。

验证实际 ID 是否符合：

```
video_id$_$clip_id
```

解析优先：

```
split("$_$", 1)
```

统计：

- unique video_id；
- video_id 跨 split count。

video_id 跨 split 只作为 EVIDENCE。

不得擅自重分官方 split。

输出：

```
reports/data_audit/id_integrity.json
```

## 9. Label audit

### train / valid

允许完整审计。

#### regression

记录：

- dtype；
- shape；
- min；
- max；
- exact_zero_count；
- negative_count；
- positive_count；
- finite count；
- nan count；
- inf count。

验证所有有限值位于：

```
[-3,3]
```

#### annotation

记录实际 unique values 和 count。

不得只凭题面预设实际文件一定只有三类。

#### classification

不要预设具体数字编码。

必须建立：

```
annotation × classification representation × count
```

联合映射。

#### cross-label consistency

验证：

- regression == 0 与 Neutral 的关系；
- regression < 0 与 annotation 的关系；
- regression > 0 与 annotation 的关系；
- classification 与 annotation 的对应关系。

输出：

```
reports/data_audit/label_mapping_train_valid.json
```

### test

严格执行 D-S00B-02。

只检查：

- field existence；
- dtype；
- shape；
- finite；
- legal range。

不得输出 detailed distribution。

必须：

```
TEST_LABEL_DISTRIBUTION_QUARANTINED=true
```

## 10. text / text_bert audit

### text

检查：

- shape；
- dtype；
- NaN；
- Inf。

对本阶段诊断定义：

```
ZERO_ROW = all(feature_dimensions == 0)
```

这只是机械检测定义。

不得把 `ZERO_ROW` 称为：

- padding；
- missing；
- invalid observation。

聚合：

- 每样本 zero-row count；
- position frequency。

### text_bert

确认实际：

- shape；
- dtype；
- channel count。

对各 channel 统计：

- unique values；
- binary fraction；
- nonzero behavior。

目的是识别 attention-mask candidate。

如果证据充分，只可报告：

```
INFERRED_ATTENTION_MASK_CHANNEL
```

如果证据不足：

```
UNKNOWN
```

不得调用外部 tokenizer 或外部模型重新解释 token IDs 以倒推出数据含义。

若 attention-mask candidate 能高置信识别，可统计：

- candidate text valid length；
- first active；
- last active；
- active continuity。

但仍只是候选观测证据。

不得由此定义最终 padding。

## 11. Audio / vision zero diagnostics

对 audio / vision 定义严格机械检测：

```
ZERO_ROW = all(feature_dimensions == 0)
```

统计：

- zero-row counts；
- position frequency；
- contiguous zero runs。

结构分类：

- `NO_ZERO`
- `PREFIX_ZERO_ONLY`
- `SUFFIX_ZERO_ONLY`
- `PREFIX_AND_SUFFIX`
- `INTERNAL_ZERO_RUN`
- `ALL_ZERO`
- `MULTIPLE_INTERNAL_RUNS`

`INTERNAL_ZERO_RUN` 定义为：

该 zero run 前后都至少存在一个 non-zero stored row。

这些只能称：

```
structural zero pattern
```

不得自动称为 missing 或 padding。

按 prefix / suffix / internal 分别统计 run length bins：

- 1

- 2

- 3

- 4

- 5

- 6-10

- 11-20

- > 20

输出：

- `reports/data_audit/zero_run_summary.csv`
- `reports/data_audit/zero_position_summary.csv`

## 12. Unaligned lengths

若实际存在：

- `audio_lengths`
- `vision_lengths`

验证：

- integer-like；
- `0 <= L <= T`。

比较：

- `[0,L)`
- `[L,T)`

的 zero pattern。

输出至少：

- `tail_after_length_all_zero_rate`
- `nonzero_after_length_count`
- `zero_inside_declared_length_count`
- `leading_zero_inside_declared_length_count`
- `internal_zero_inside_declared_length_count`

不得据此自动冻结 padding。

输出：

```
reports/data_audit/length_consistency_unaligned.json
```

## 13. Aligned positional diagnostics

若 text attention-mask candidate 可以高置信识别：

生成 candidate text mask active / inactive 与：

- text ZERO_ROW；
- audio ZERO_ROW；
- vision ZERO_ROW；

的聚合 contingency。

统计 candidate text-valid span 内：

- audio zero rows；
- vision zero rows；
- audio internal zero rows；
- vision internal zero rows；
- 三模态 simultaneous-zero frequency。

不得给出最终 padding 或 missing 结论。

若 attention-mask candidate 不能可靠识别：

相应依赖统计允许标为 UNKNOWN / BLOCKED，不得伪造替代 mask。

输出：

```
reports/data_audit/aligned_positional_diagnostics.json
```

## 14. Finite & all-zero audit

对：

- text；
- audio；
- vision；

检查：

- NaN；
- +Inf；
- -Inf。

train / valid 完整统计。

test 只输出：

- 是否存在；
- 总 count；

不得提供详细 test 分布。

不得静默执行：

```
nan_to_num
```

检查：

- 整个 text 模态全零；
- 整个 audio 模态全零；
- 整个 vision 模态全零；
- 三模态全部全零。

不删除样本。

只标：

```
DATA_QUALITY_EVIDENCE
```

输出：

```
reports/data_audit/finite_value_audit.json
```

## 15. Aligned vs unaligned consistency

每个 split 比较：

- sample count；
- ID set；
- ID order。

如果顺序不同：

必须按 ID 匹配后再比较。

### train / valid

允许完整比较：

- annotations；
- classification_labels；
- regression_labels。

### test

仅输出：

- identity equality；
- label field existence / shape / legal range；
- labels_equal true / false。

不得输出具体 test 标签或详细 distribution。

### raw_text

只做：

- hash；
- equality。

不得公开完整 raw_text dump。

### text features

若内存和数值风险可控，可以比较：

- exact equality；
- max abs diff。

若不安全：

可标为 UNKNOWN。

此项属于非关键扩展，不得为完成它而破坏内存安全。

输出：

```
reports/data_audit/version_consistency.json
```

## 16. Attachment inventories

### Attachment 1

只进行完整性 inventory。

核对真实：

- 视频文件数量；
- video_id 目录数量；
- `label-100.xlsx` 是否存在；
- Excel row count；
- 是否存在列：
  - video_id
  - clip_id
  - text
  - label
  - annotation
- 视频文件与 label row 的对应关系。

同时与题面 SPECIFIED expectation 核对：

- 100条视频样本；
- 37个 video_id 子文件夹。

实际值必须单独记录为 VERIFIED。

不得运行：

- ASR；
- OpenFace；
- openSMILE；
- BERT；
- 特征提取；
- 时间对齐。

输出：

```
reports/data_audit/attachment1_inventory.json
```

### Attachment 3

只做 file-level inventory：

- 版本目录；
- 文件数量；
- 扩展名；
- 文件大小。

禁止打开 / deserialize PKL。

禁止分析：

- missing ratio；
- missing location；
- modality combination；
- feature values。

输出：

```
reports/data_audit/attachment3_inventory.json
```

必须：

```
CONTENT_NOT_INSPECTED=true
```

### Attachment 4

只做 file-level inventory：

- aligned / unaligned 目录或版本；
- feature file count；
- video count；
- 文件命名对应关系。

禁止：

- 反序列化特征；
- 查看实际特征内容；
- 分析视频内容；
- 抽帧；
- ASR；
- 音频分析。

输出：

```
reports/data_audit/attachment4_inventory.json
```

必须：

```
FEATURE_CONTENT_NOT_INSPECTED=true
VIDEO_CONTENT_NOT_INSPECTED=true
```

## 17. Public / private outputs

GitHub 和 GitHub Release 严禁包含：

- 完整 raw_text；
- token IDs dump；
- sample-level labels；
- features；
- raw sample IDs；
- 私人绝对路径；
- 原始 PKL；
- MP4；
- 原始大型 Excel；
- 本地 paths config；
- credentials。

公开异常样本只用 sample hash。

如果确需本地映射：

放入：

```
artifacts/private/
```

并确保：

- gitignored；
- package excluded。

必须生成：

- `reports/data_audit/DATA_AUDIT.md`
- `reports/data_audit/schema_aligned.json`
- `reports/data_audit/schema_unaligned.json`
- `reports/data_audit/split_consistency.json`
- `reports/data_audit/id_integrity.json`
- `reports/data_audit/label_mapping_train_valid.json`
- `reports/data_audit/version_consistency.json`
- `reports/data_audit/zero_run_summary.csv`
- `reports/data_audit/zero_position_summary.csv`
- `reports/data_audit/length_consistency_unaligned.json`
- `reports/data_audit/aligned_positional_diagnostics.json`
- `reports/data_audit/finite_value_audit.json`
- `reports/data_audit/attachment1_inventory.json`
- `reports/data_audit/attachment3_inventory.json`
- `reports/data_audit/attachment4_inventory.json`
- `docs/DATA_CONTRACT_EVIDENCE.md`

`DATA_CONTRACT_EVIDENCE.md` 必须按照：

- VERIFIED；
- SPECIFIED；
- INFERRED；
- HYPOTHESIS；
- UNKNOWN；

组织。

必须明确回答：

- 真实 schema；
- 实际 N；
- 与题面4850的关系；
- 标签实际编码；
- regression / classification / annotation 一致性；
- attention-mask candidate；
- unaligned lengths 与零尾部关系；
- aligned candidate 有效位置；
- 有效范围内部 continuous zero runs；
- 当前证据能否把 zero 解释为 missing；
- 当前证据能否把 zero 解释为 padding；
- aligned / unaligned identity；
- aligned / unaligned labels；
- NaN / Inf；
- exact ID overlap；
- video_id 跨 split；
- 附件1真实完整性及与100条/37目录题面预期的关系；
- 附件3/4是否存在；
- 附件3/4是否保持未内容审计；
- S00B 后哪些科研问题需要主研究负责人冻结。

## 18. Tests

至少覆盖：

- schema extractor；
- zero-row detector；
- zero-run detector；
- prefix / suffix / internal classification；
- all-zero handling；
- length consistency；
- ID overlap；
- `$_$` parser；
- label mapping；
- neutral-zero validation；
- test quarantine；
- Attachment3 loader guard；
- Attachment4 loader guard；
- path redaction；
- public package exclusion；
- source arrays no mutation；
- competition-specified expected-count comparison；
- public reports do not leak quarantined test distributions。

必须真实运行：

- aligned audit；
- unaligned audit；
- Attachment1 inventory；
- Attachment3 file-level inventory；
- Attachment4 file-level inventory。

普通工程问题允许 Codex：

- 自主实现；
- 自主 Debug；
- 自主修复；
- 自主重跑。

不得跳过失败后伪造成功。

## 19. Gate

必须建立 GATE，并至少包含：

- G01 trusted official pickle confirmed
- G02 aligned audit completed
- G03 unaligned audit completed
- G04 schemas extracted
- G05 split consistency checked
- G06 ID integrity checked
- G07 train/valid label mapping verified
- G08 test quarantine respected
- G09 zero-row diagnostics completed
- G10 zero-run diagnostics completed
- G11 unaligned lengths diagnostics completed
- G12 aligned positional diagnostics completed or evidence-based UNKNOWN/BLOCKED
- G13 version identity compared
- G14 NaN/Inf audit completed
- G15 Attachment1 inventory completed
- G16 Attachment3 inventory without deserialization
- G17 Attachment4 inventory without deserialization
- G18 source files unchanged
- G19 public output contains no raw dataset content
- G20 no original dataset tracked
- G21 no original dataset packaged
- G22 DATA_CONTRACT_EVIDENCE complete
- G23 competition-specified sample-count expectations checked and discrepancies reported
- G24 research restrictions preserved

每项必须标：

- PASS
- FAIL
- SKIPPED
- BLOCKED

并记录对应 evidence。

不得通过修改 Gate 规则隐藏真实失败。

## 20. Status semantics

### SUCCESS

仅当：

- aligned / unaligned 真实审计完成；
- 核心 Gate 通过；
- test quarantine 完整遵守；
- 附件3/4未内容审计；
- 原始数据未被修改；
- 原始数据未泄漏；
- DATA_CONTRACT_EVIDENCE 完整；
- tests 完成；
- commit / push / Release 完成；
- 无未解决的 CRITICAL safety failure。

### PARTIAL

只允许非关键扩展统计缺失。

核心事实仍必须完整。

不得用 PARTIAL 掩盖：

- test quarantine violation；
- Attachment3/4 content inspection；
- source mutation；
- raw data leakage。

### BLOCKED

可用于：

- 数据路径不可用；
- trusted official data 无法确认；
- 内存无法安全处理；
- 关键文件缺失；
- 依赖无法安全满足；
- GitHub 发布权限阻塞；
- 必需证据无法安全取得。

### FAILED

以下任何情况必须 FAILED：

- 修改原始数据；
- 违反 test quarantine；
- 反序列化附件3；
- 反序列化附件4专项特征；
- 分析附件4视频内容；
- 原始数据被 commit；
- 原始数据被 package；
- 伪造运行或指标；
- 关键一致性错误仍宣称成功。

题面 SPECIFIED expected count 与实际不一致本身不允许被静默修补。

必须报告真实差异和证据，由主研究负责人判断科研影响。

## 21. Research restrictions

Codex 不得自行宣布：

- `aligned = final`
- `unaligned = final`
- `ZERO_ROW = MISSING`
- `ZERO_ROW = PADDING`
- `attention mask = final padding rule`
- 某一标准化方法为最终方案
- 某一字段组合为最终模型输入
- 下一阶段模型结构已经确定。

如果真实证据导致现有冻结科研协议似乎需要修改，只能生成：

```
PROPOSED_RESEARCH_CHANGE
```

必须包含：

- current_decision；
- proposed_change；
- reason；
- expected_benefit；
- risk；
- required_evidence。

Codex 不能自行批准。

一旦该 proposed change 会改变：

- data split usage；
- label semantics；
- padding interpretation；
- missing interpretation；
- aligned / unaligned selection；
- test usage；
- Attachment3/4 usage boundary；

则不得继续跨越该科研边界。

停止并等待主研究负责人审核。

普通工程修复不属于 PROPOSED_RESEARCH_CHANGE。

## 22. Git & Release

正式开发分支：

```
codex/mosei-auto
```

必须先确认当前分支正确。

Git 操作遵循 AGENTS.md。

仅允许：

- 精确 pathspec staging；
- ordinary commit；
- ordinary push；
- 当前 S00B 授权下的 GitHub Release。

禁止：

- `git add .`
- `git add -A`
- `git add --all`
- force push
- force-with-lease
- filter-repo
- mirror push
- public-history rebase
- destructive clean
- hard reset existing work
- remote ref deletion

除非用户针对具体危险命令另行授权。

在 commit 前必须：

- `git status --short`
- 检查待提交路径；
- 扫描 raw data / private path / credential；
- 精确 add；
- `git diff --cached --name-status`
- 检查 staged content。

生成：

```
review-<run_id>.zip
```

至少包含：

- CHATGPT_REVIEW；
- DATA_AUDIT；
- DATA_CONTRACT_EVIDENCE；
- GATE；
- TEST_RESULTS；
- RUN；
- 公开 data_audit JSON / CSV；
- 必要的公开配置与 manifest。

不得包含：

- PKL；
- MP4；
- raw_text dump；
- token dump；
- sample-level labels；
- private paths；
- private artifacts。

GitHub Release target：

必须为 S00B `implementation_commit`。

必须验证：

- tag；
- target；
- asset；
- asset size；
- local asset SHA256；
- downloaded asset SHA256。

## 23. CHATGPT_REVIEW

S00B 完成后必须覆盖：

- task_id；
- run_id；
- status；
- repository；
- branch；
- baseline SHA；
- implementation commit；
- metadata commit；
- Release tag / URL / asset；
- 实际被审计的官方文件；
- source mutation check；
- VERIFIED schemas；
- actual split sizes；
- competition-specified count comparison；
- ID integrity；
- label mapping；
- neutral-zero consistency；
- test quarantine；
- zero-row diagnostics；
- zero-run diagnostics；
- unaligned length diagnostics；
- aligned positional diagnostics；
- version consistency；
- NaN / Inf；
- Attachment1 inventory；
- Attachment3 inventory；
- Attachment4 inventory；
- tests；
- Gate；
- failures；
- blockers；
- unknowns；
- research questions requiring review；
- `PROPOSED_RESEARCH_CHANGE`，若无则明确 NONE；
- 关键审核文件路径。

Attachment3 必须明确：

```
CONTENT_NOT_INSPECTED=true
```

Attachment4 必须明确：

```
FEATURE_CONTENT_NOT_INSPECTED=true
VIDEO_CONTENT_NOT_INSPECTED=true
```

Next stage 只能写：

```
PENDING_RESEARCH_REVIEW
```

和：

```
NEXT_STAGE_NOT_AUTHORIZED
```

不得自行进入 S01。

## 24. Stop condition

完成：

真实 audit
→ tests
→ Gate
→ report
→ safety scan
→ commit
→ push
→ GitHub Release
→ remote verification

之后停止。

不得开始：

- baseline training；
- S01；
- Q1 feature extraction；
- Q2 model design/training；
- Q3 explanation；
- aligned / unaligned 最终选择；
- padding 最终定义；
- missing 最终定义。

最终状态必须明确：

```
STOPPED_AFTER_S00B
```

等待 Main Research Chat 审核。
