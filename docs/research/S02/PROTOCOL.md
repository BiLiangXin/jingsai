# S02 有界改进协议（S02-RES-01）

证据层级：本文为 **SPECIFIED**，来自用户当前明确授权；方法收益为 **HYPOTHESIS**，没有运行的模型记录保持 NOT_RUN / metrics=null。S02 是观察 S01 结果后的探索性后续研究，同一 VALID 的反复选择存在乐观偏差，seed 样本 SD 不是显著性或无偏泛化证据。

本次独立任务 S02_CHAMPION_CHALLENGER_IMPROVEMENT，不恢复 S01。S01 基准提交 `95342eb58bf0494bcc90934f76958b71becb8687`，执行代码 `98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7`。其 30 个 fit、60 个 best/last 和全部私有评价先普通独立复制、逐文件 SHA256/size 核验，再恢复预测。旧模型和旧指标永不覆盖，回退只改新模型注册指针。

## 数据与接口

D-DATA-01…07 的原文与含义不变。aligned 连续 text/audio/vision 维度为 50×768/74/35。S=text_bert[:,1,:]==1；padding=~S；O_T=S；O_A/O_V=S AND NOT 原始整行精确结构零。人工 C 与自然结构零分离，A=O AND NOT C。归一化或损坏后不重新判断 O。predictor 只收到连续特征、S、A，以及由 A/S 得到的 b/rho；不收标签、ID、raw_text、split、token、O/C 旁路或专项统计。

只有 TRAIN 学习权重、类别频数、normalizer、prior/median；VALID 仅选择本文固定集合。test 不评价/选模；附件3/4不开启。原 PKL 为单文件容器，信任 SHA256 通过后反序列化该文件，只访问 train/valid 允许字段；不声称 pickle 未物化其他内部对象。KNOWN_AVAILABILITY 是仿真条件，附件3可靠 mask availability 仍 UNKNOWN。禁止从自然结构零直接推断人工缺失。

## W：固定 15 个无需训练配置

固定 seeds=17,29,43，同 seed 配对 B-CAT-zscore 与 B-T-identity；每个组件保留原 TRAIN scaler。W0 两头来自 CAT；W1 分类来自 CAT、回归来自 T；W2 分类概率与回归预测分别等权平均。W0/W1 使用 CAT logits，W2 使用平均概率的 log（数值下界1e-30）。仅 Neutral 坐标加 beta∈{-0.4,-0.2,0,0.2,0.4} 后 argmax，共15配置，禁止继续搜索。beta=0原样对照，真实Neutral仍严格 y=0。

clean 和完整96 nominal conditions/144 views 均评价；每个专家都用同一实际 A，缺失 text 不能由 T 回归专家绕过。缓存绑定样本总体/顺序、原始 masks、实际 corruption view 指纹、replicate、组件 checkpoint 和normalizer哈希。只对eligible样本新增损坏forward，其他样本复用clean一次；同一cache可供固定15配置复用。输出分类与回归符号不一致率，不能重定义标签掩盖。

## M：固定 4 配方 × 3 seeds，最多12新fit

结构对四配方一致，初始化与 recipe 名无关。各模态 Linear(d_m,64,bias=True)→GELU；注意力打分为 Linear(64,32,bias=True)→tanh→Linear(32,1,bias=False)。仅 A 上 softmax，全空分支先以有限零向量替代打分再全部屏蔽；inactive NaN先屏蔽，active NaN拒绝。h_m=Σ_t softmax_A(score_mt)e_mt，空模态h_m=0。

b_m=1[ΣA_mt>0]，rho_m=ΣA_mt/ΣS_t。gate输入 concat(h_T,h_A,h_V,b_T,b_A,b_V,rho_T,rho_A,rho_V) 198维，Linear198→32→tanh→Linear32→2→sigmoid。

\[h=h_T+b_Ag_AP_Ah_A+b_Vg_VP_Vh_V.\]

P_A/P_V 是64→64无bias线性层，权重全零初始化，其余线性层使用基于seed与模块名的确定性初始化。双头是Linear64→3及3*tanh(Linear64→1)，总可训练参数77,542。无text时允许A/V路径；三模态全空时输出TRAIN prior的logits与TRAIN median。注意力不代表真实秒级映射、因果解释或已完成Q3。

|配方|固定训练差异|新增fit|
|---|---|---:|
|M1|clean；CE+MAE/3|3|
|M2|M1的CE替换为固定TRAIN类别加权CE|3|
|M3|M1加 p_corrupt=0.25 连续缺失增强|3|
|M4|M3加固定同seed S01 CAT教师的小权重KD|3|

M2：w'_c=clip(sqrt(N/(3n_c)),0.5,2)，w_c=w'_c/(Σ_c n_c w'_c/N)。若某类别TRAIN计数为0，先使用clip上界2，再做相同归一化。损失是 mean_i(w_yi CE_i)，不使用随minibatch变化的权重分母；只由TRAIN计算。

M3/M4：原train根2207、原96条件和合法连续窗口生成器不变。每行哈希键(train,2207,seed,epoch,private ordinal,'clean_or_corrupt')均匀取0..3，值3才尝试corrupt，否则clean；条件仍由原'condition'键选取，随机位置namespace=train:seed:epoch。无合法窗口CLEAN_ONCE，权重1，不删样本、不重采样、不按标签选择。VALID根1103、96/144、random三重复完全不变。

M4：在每一个TRAIN行的当前student view上增加 0.1×2² KL(softmax(z_teacher_clean/2) || softmax(z_student/2))，包括75%clean与CLEAN_ONCE行；这是预先固定的解释。教师eval、requires_grad=False且soft目标detach，只在TRAIN使用；对应seed的S01 B-CAT-zscore，normalizer与student共同TRAIN zscore一致。student推理没有教师或完整隐藏特征。保留真实CE/MAE监督。

统一 AdamW lr=.001, weight_decay=.0001, batch32, clip_norm1, max_epochs100，TRAIN zscore，seeds17/29/43；没有额外宽度/学习率/normalizer/seed搜索；M始终beta0。只运行M1三seed，然后M2三seed，再M3、M4。

用户补充要求逐轮保存用于论文制图。每个epoch持久保存全量聚合轨迹：按样本数加权的TRAIN CE/加权CE/MAE/KD/总loss，当前训练view上的在线Accuracy/F1/MAE/Pearson，clean VALID四指标及监督loss，学习率、样本数、corruption/fallback计数、训练/验证/累计耗时、bestepoch/checkpoint_saved/early_stop。TRAIN在线指标来自该轮各minibatch更新前的预测，模型权重随batch改变，不能称整轮结束checkpoint在clean TRAIN上的独立评价。最终导出所有seed每一轮的安全CSV/JSON，保留非最优轮次；逐样本数据不入Git。

## 三层选择、聚合与晋升

每次训练以clean VALID macro-F1最大、MAE最小、完全平票最早epoch选best checkpoint。early stopping采用原reference.choose_checkpoint：patience10，min_delta_F=1e-4，min_delta_MAE=1e-4，max_epochs100；“实际最优checkpoint”与“显著进步patience锚点”分开。选中后才做完整144view评价。S02该规则不同于S01 C0/R0的attempted96 checkpoint，因此跨阶段比较不能声称只改变一个机制；M1–M4的选点规则彼此相同。

每次view的attempted总体保留全部样本。先random replicate均值，再96条件等权，再3seed均值；144view不可直接等权。所有候选报告每seed与三seed均值/样本SD，fixed seed17；clean四指标和attempted96 F1/MAE，以及模态组、位置、窗口长度、eligibility条件汇总。Pearson无定义保留null+原因；任一seed Pearson未定义则三seed均值也null，不忽略该seed。

clean Pareto描述四项均值。robust排序先满足相对原S01三seedmean clean F1≥原值−.01、MAE≤原值+.05，再按attempted96 F1降、MAE升、参数少、实测完整144view推理时长低、稳定ID顺序。时长只用于最后的精确平票，不据此推断硬件无关优越性。

CURRENT_CHAMPION自动晋升更严格：三seed完整；相对原S01 champion，在三seed均值和seed17两个层面，clean Accuracy/F1/Pearson都不降、MAE不升，attempted96 F1不降且MAE不升；至少一个被比较指标改善>1e-8。其余不劣只允许1e-8计算容差，不称真实收益。任何无法比较的Pearson均拒绝自动晋升。多候选满足时依次按attempted96 F1、MAE、clean F1、clean MAE、推理成本、ID选择。绝不搜索seed/runner-up。

完整计划终止前不改注册指针；本实现更保守，只有全部15配置与12fit完成才考虑晋升，资源/错误停止一律保留原指针。胜者fixedseed17从冻结checkpoint重新恢复，clean+144view预测必须与本轮保存输出精确数值一致，才原子更新指针。旧champion继续保留。没有合格者即保留原模型，记录所有负结果和trade-off。

## 有界资源与可信执行

S02-EXEC-AUTH-01源于当前用户指令，仅授权本任务；无需第二次“批准”或伪造native event。候选评价+新训练共4小时，fit含其最终评价45分钟；绝对计算截止2026-09-25 18:00北京时间。启动时必须还留有完整4小时窗口。备份/原模型恢复独立记录，不算新候选结果；其自身也受绝对截止监督。synthetic成本测量不作模型性能证据，预计时间不保证12fit完成。

新claim使用独立S02固定本机ledger，一次消费、retry0、不能换目录重试。先真备份恢复、无数据测试、独立只读技术审查、文件manifest、精确pathspec commit/push与实时clean/local=remote preflight，再读取train/valid并运行候选。每fit前后重新核验完整数据源指纹和执行源文件；目录必须不存在且在仓库外。全部best/last、RNG、normalizer、配置、source/code/config/checkpoint hash、预测、失败、轨迹留私有目录。错误/OOM/cap都落盘，不写COMPLETED、不自动重试；仅公开安全聚合。依赖已安装运行时，不下载外部数据/权重。

本机OS账户/Git发布者为信任基础，非针对恶意同账户代码的安全沙箱。公共manifest/独立审查绑定代码和配置，不冒充密码学用户身份遥测。GPU显存80%和私有存储5GiB为额外上限。外部监督器与内部batch边界检查双重限制，强制终止若发生会保留原始证据并标记异常，不能伪报优雅完成。

文献采用/否决和版本见内含主要结论的 SOURCES.md。文献效果不是本赛题效果；不新增Release、不生成网页交接ZIP、不启动Q1/Q3/专项推理或未列出的训练。
