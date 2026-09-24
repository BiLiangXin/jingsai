# S01 执行规格与授权准备

当前目标为 `S01_EXECUTION_READY_PENDING_OWNER_AUTHORIZATION`。本阶段只允许合成工程测试和真实硬件上的合成资源测量；它不是 S01 正式执行，不产生比赛模型指标。`training_authorized=false`，`NORMALIZER_SELECTED=NOT_YET_SELECTED`。本文件的验证状态以同批 `reports/s01_preparation/RESULT.json` 为准。

## 版本与权限

[VERIFIED] 准备基线为 `be2917568434450ddefc54dbafae7c1dee5862dd`，仓库 `BiLiangXin/jingsai`，分支 `codex/mosei-auto`。开始时工作树、index、untracked 均干净，实时远端一致，另一个工程任务空闲。S00E 已发布证据与 21 项 Gate 保留，`LATEST_RUN.json` 不改写成 S01 模型运行。R01-FREEZE-01 的批准来源、原文件哈希、全部冻结文件及历史报告保留。

[SPECIFIED] 本轮用户附件明确授权规格、模型/训练框架、synthetic optimizer step、资源测量、预注册及普通 Git 发布。它覆盖旧 TASK_SPEC 的 S00E 当前阶段指针；不覆盖 D-DATA-01..07，也没有授权 official train/valid optimizer run、test、附件3/4、Q3、Release 或后置模型扩展。

[UNKNOWN] 实际模型/推理档位无可验证遥测；沿用用户已确认的 Astra/xhigh 界面设置，不虚构身份探测。

## 数据与接口

三模态固定为连续 text/audio/vision，形状分别为 `B×50×768/74/35`。原始 `S=(text_bert[:,1,:]==1)`；`P=not S`；`O_T=S`；`O_A/O_V=S and not Z_A/Z_V`，其中 Z 是原始整行精确结构零。原始适配器保留结构零及 float32 转换检查。归一化与人工缺失不重新推断 Z/O。

模型唯一输入为 `{features, support, available}`，其中 `A=O and not C`，C 单独生成，原始 O 不作为额外 predictor。原始 ID、标签、raw_text、split、token IDs、专项统计均不能进入 forward。私有行序号仅供固定采样/配对，不进入模型。

`KNOWN_AVAILABILITY` 是已知人工缺失 mask 的条件接口，不能推出专项部署时同等 mask 存在。附件3可靠 mask 可得性仍为 UNKNOWN，natural structural-zero 不自动等于 artificial missing。

模型先检查 active 数据有限，再将 inactive 数据安全替换为零，随后投影、卷积、归约。非 active NaN 不参加算术；active NaN/Inf、梯度或参数溢出失败退出。原始官方文件适配器保留更严格的全源有限性检查；模型的 NaN 隔离不意味着放宽原始数据合同。

## 首轮模型

隐藏维度 64；输出三类 logits 和 `3*tanh(regression_head)` 的一个标量。无 dropout、Q3模块、额外模态或外部情感权重。

| 架构 | 定义 | 可训练参数数 |
|---|---|---:|
| B-T | text 的安全 mean pool → Linear/ReLU → 双头 | 49476 |
| B-A | audio 同上 | 5060 |
| B-V | vision 同上 | 2564 |
| B-CAT | 三模态原维度 pool 拼接 877 → 64 → 双头 | 56452 |
| C0 | 各模态 pool → 独立投影/ReLU → 等权融合，追加 b/rho → 双头；clean 训练 | 56604 |
| R0 | 与 C0 相同，仅增加冻结的人工缺失增强 | 56604 |
| R1 | 逐位置投影/ReLU → 一层 partial convolution → safe pool → 等权融合 | 93660 |
| R2 | R1 编码器，融合改为共享 gate | 98012 |
| R1-CAP | R1 等权融合加有效残差 MLP 作为容量对照 | 97932 |

参数数来自实际实例计数，可由合成测试和资源报告复核；不是训练结果。PRIOR 使用 train 三类频率与强度中位数，0 个可训练参数、4 个统计量。偶数样本的中位数取中间两值均值。LATE 复用同 seed、同 normalizer 的三个单模态 checkpoint，平均可用模态的概率与强度，不增加 fit。全部无可用模态时用 train prior/median。其容量是三个组件之和。

Partial convolution 严格实现：`E_t=ReLU(W U_t+b)` 仅在 A 生效；`v_t=ReLU(b' + sum_delta K_delta E_(t+delta)/k_t)`，delta 为 -1/0/1，k_t 为可用邻居数，非 active 中心不进入池化。`g=mean_A(v)`。Gate 输入 `[g_m,b_m,rho_m]`，共享 `66→64→1`；只在可用模态上归一化。head 输入 `[fusion,b_T,b_A,b_V,rho_T,rho_A,rho_V]`，70维。R1-CAP 残差为 `198→16→64`，参数4272；gate4352，非严格同容量/同 FLOPs。

C0/R0 的匹配模块按相同模块名和 seed 派生初始化；R1/R2/R1-CAP 共享部分同样初始化。数据顺序和 mask 是独立确定性流。R0→R1 是整个编码器包增量，不能声称纯时序因果效应；R1/R2 为端到端联合适应，不是固定 encoder 权重的门控效果。

## 训练、normalizer、选择

T0：AdamW，lr=0.001，weight_decay=0.0001，batch32，clip_norm=1，CE+MAE/3，max_epochs100。随机种子17/29/43；train mask根2207，valid mask根1103。Identity 与 train-only z-score 都已实现；z-score 只用 train 原 supported-and-observed 向量，以 float64 合并方差统计，零标准差 scale=1。transform 保留 O；均值变为零不是新的结构缺失。

未来先完成 B 的24次 fit，按 B-CAT 三 seed clean valid 的 mean macro-F1 主、MAE 次确定公共 normalizer；完全平票 Identity。当前未运行官方比较，不能记录胜出者。

B* 从8个 B 配置、2个 LATE 配置与确定性 PRIOR 中按三 seed clean 均值锁定，C0不参加 B*。完整39-fit协议中，之后 C0/R0/R1/R2/R1-CAP 共15次 fit 使用同一公共 normalizer。本次截止时间方案只拟激活 C0/R0 共6次；其余9次保持预注册但延期。

B checkpoint 目标 clean；五个机制模型共同目标 attempted96。B 每 epoch 仅 clean 评价一次，选定 checkpoint 后才额外做一次完整缺失报告；机制模型每 epoch 共同使用 attempted96。精确 `(F,-MAE)` 改善保存 checkpoint，完全平票保留最早。patience10、min_delta_F/MAE均1e-4控制耐心重置，微小改善仍可保存。主F退步时不能仅因MAE改善重置耐心。最终按实际选中 checkpoint 做跨 seed 归约，不挖取其他备用 checkpoint。

稳健配置先以三 seed clean 均值相对 B* 满足 epsilon_F=.01、epsilon_MAE=.05，再按 attempted macro-F1/MAE、参数数、配置ID排序。只检查 winner seed17 的相同 clean guard，失败即 B* seed17；不挑幸运 seed 或 runner-up，不 ensemble，不 train+valid 重训。同一 valid 多层选择有乐观偏差，普通 bootstrap 不消除它。

固定三类报告（缺类F1=0）、样本加权MAE；Pearson 样本不足/真值零方差/预测零方差返回 null+原因。合成测试中的数值只证明公式/实现行为，不得作为比赛预测指标发布。

## 缺失生成与计权

直接调用冻结 `research/r01/reference.py`，不另造随机算法。6个单/双模态组 ×4个比例 ×4个位置=96条件；72固定位置视图加24个random条件各3重复=144视图。窗口在原 supported 坐标连续，C=I∩O；每个被选模态必须 `0<sum(C)<sum(O)`。资格不足一次 clean 回退；不删样本，不重抽标签/窗口，不改窗口长度。

train 每样本每 epoch 一次 clean/抽中条件，抽中不合法条件 CLEAN_ONCE。valid mask库不含 model seed/架构/epoch；先缓存该 checkpoint 的 clean 预测，再仅对 eligible 子集前向，无资格样本复用一次 clean。每个视图先对 attempted 全集算指标，再 random replicate→condition→seed，各条件等权。不得先平均预测再算指标或把144重复当独立样本。

完整条件报告保留 eligible-only、资格率、固定三类、Pearson原因和内部有序总体/资格集合/实际view指纹；跨 seed 聚合验证配对一致性。真实逐样本预测和 mask 库未来只留私有目录，不进 Git。

## 预注册、checkpoint与失败

唯一正式登记继续为 `docs/EXPERIMENT_REGISTER.json` 的 `s01_preregistered_fits`，39个未来 fit 全部 NOT_RUN、metrics=null、retry_count=0。PRIOR/LATE是复用评价，不伪造为新增 fit。历史66行设计保留，D/T/L及其余27行不属于当前正式预注册。

每条保留 trial_id、architecture、normalizer、recipe、seed、config_hash、code_commit、data_contract、mask roots、状态、时间、checkpoint、metrics、failure_reason、retry_count。`config_hash` 绑定当前精确模板；common normalizer 待未来按规则解析，另记录 resolved_config_hash。`code_commit=null` 是未执行状态，未来绑定实际获授权的干净 HEAD，不能将旧设计 commit 冒充新实现 commit。

未来私有 append-only events 记录 RUNNING/COMPLETED/FAILED/RESOURCE_CAP_STOP，每次失败都保留；禁止覆盖已存在输出目录或自动重试。best/last checkpoint 包含模型、optimizer、normalizer、selector trace、epoch、seed、config hash、来源指纹及随机状态。恢复必须匹配配置/来源，已早停不继续。合成测试覆盖状态恢复；正式调度器不开放自动 resume/retry。一次 owner campaign 只可领取一次启动，即使失败也不能换目录重启；恢复需另行明确批准并保留所有旧尝试。

## 资源与独立授权

详见 `reports/s01_preparation/RESOURCE_ESTIMATE.md` 和同名 JSON。synthetic step/显存为 MEASURED；100 epoch 与39fits外推为 ESTIMATED；官方真实epoch时间为 UNKNOWN。硬件上测过更大的batch只是余量证据，当前T0仍为32。具体数字为 PROPOSED_NUMERIC_RESOURCE_CAP，未经负责人批准。

官方 CLI 不提供 `--training-authorized` 绕过开关。执行同时要求：项目config的布尔true、正确执行task、研究状态true、owner-approved正数cap、干净指定分支及remote、当前commit、冻结协议和完整config哈希、对应固定本地宿主会话的真实用户批准事件。批准还绑定唯一 campaign、私有输出目录规范路径 SHA256、CUDA device、实际启用24/30/39预算和绝对计算截止。独立于宿主日志的一次性 claim 阻止重复领取同一 campaign；源码/config/预算改变后旧批准不适用。普通JSON中的owner_approved或签名样式文字没有效力。test/附件3/4独立硬拒绝，valid永远不能optimizer。批准前拒绝发生在原始source读取之前。

此授权信任未受破坏的本机Codex宿主/OS账号，不是对同账号恶意代码的安全沙箱。沿用独立审查过的宿主事件解析和junction/reparse防护；本阶段没有读取真实授权日志或发起训练批准。本阶段stop；未来owner确认须绑定届时commit/config/cap，现有R01协议批准不能替代它。

## 可复核命令

在已有经过实际运行的 Python/PyTorch 环境、仓库根目录执行；不需要下载模型或数据。

```text
python -B -X utf8 -m pytest -q -p no:cacheprovider tests
python -B -X utf8 tools/s01_train.py synthetic --architecture R2 --device cuda --output-dir <NEW_PRIVATE_SYNTHETIC_DIR>
python -B -X utf8 tools/s01_resource_profile.py --output <NEW_RESOURCE_REPORT_JSON>
python -B -X utf8 tools/s01_resource_estimate.py --profile <RESOURCE_REPORT_JSON> --output <NEW_ESTIMATE_JSON>
```

合成命令不接收数据路径；checkpoints只能保存在新的私有/临时目录，不提交Git。未来正式命令为 `python tools/s01_train.py official --source <LOCAL_ALIGNED_FILE> --output-dir <NEW_PRIVATE_RUN_DIR> --device cuda`，当前必须拒绝。冻结训练尚未授权，不在本阶段执行该命令的学习路径。

## 局限与待负责人决定

需要主研究负责人决定具体资源cap并独立授权 S01 执行。用户明确论文截止为北京时间2026-09-27 00:00，要求充分修改时间。因此作者提出在任何正式实验前采用冻结允许的30fit资源方案；原39fit协议和全部预注册保持。具体小时、30fit与正式执行权限仍待一次明确范围授权。专项mask、test授权、Q3、unaligned、66fit扩展均不在本任务决策内。

尚无任何官方模型优劣、F1/MAE、显著性、真实epoch耗时、专项泛化或归一化优胜结论。有限合成案例与独立代码审查也不能证明所有硬件/数值边界均可靠。


## 截止时间约束（优先于旧72小时提案）

[SPECIFIED] 用户两次确认论文提交为北京时间2026-09-27 00:00。[PROPOSED] 计算截止2026-09-25 18:00，至少保留30小时用于结果整理、论文修改、格式检查与提交；这不宣称论文已完成。

建议30fits（B24+C0三seed+R0三seed），总硬上限12小时，单fit2小时；不折扣early stopping，保留100epoch最大值、三seed与96/144完整验证。最迟启动时间为9月25日06:00，晚于此时拒绝以12小时上限启动。若届时仍未批准或资源不满足，必须在任何正式实验前改为24fit方案并重新绑定批准：建议4小时上限、1小时单fit、最迟14:00启动；此时没有C0/R0真实机制证据，不能声称完成Q2鲁棒性验证。14:00之后不再承诺完整24fit，需另行决策，不能压缩论文预留时间。

本方案推迟R1/R2/R1-CAP九个fits。因此其实现/合成测试通过仅为工程就绪，不能作为时序编码或门控效果证据。任何方案启动后不得看结果改预算，不将未完成seed拼成完整三seed结果。到cap保留已产生checkpoint/失败事件并停止，不伪造39/30已完成。

资源外推方法使用完整纯合成3395/728规模、50个全部supported-and-observed位置，实际训练循环及CPU指标/144视图/选中checkpoint复核；25%波动系数之外另加每epoch0.25秒checkpoint余量、每fit60秒IO和全局0.5小时准备。单次合成epoch不是官方数据耗时上界，计划值不保证完成。已测最大安全batch256仅是测试下界，物理上限UNKNOWN；正式batch仍32。

独立首审发现B误走每epoch缺失网格、批准可重复调度、结果落盘失败后误记COMPLETED三个MAJOR，以及CPU默认设备问题。修复与56项回归真实运行记录见tests/review报告；这些负面证据保留。作者没有替独立审查签署通过，也没有获得训练授权。
