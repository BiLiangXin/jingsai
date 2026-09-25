S02 文献采用与排除说明（访问日期：2026-09-25，北京时间）

本次完整阅读 S02 提示词，核查七篇原论文的相关方法与协议、作者实现及可见许可。仅形成研究依据；未执行实验、下载模型或数据、读取官方数据、复制作者代码或修改正式仓库。下列“采用”指本任务的有限设计借鉴，均不构成完整论文复现或提升保证。

**S02-LIT-01 · SOTA** — [SOTA: Self-adaptive Optimal Transport for Zero-Shot Classification with Multiple Foundation Models](https://arxiv.org/html/2506.13723v3)。arXiv:2506.13723v3（2026-03-12）。

采用：仅作为同 seed 模型互补的动机；W0/W1/W2 是本任务固定组合，不称 SOTA 复现。 排除：拒绝在 test/附件3/4 整体分布上求 transport、GMM、模型权重或伪标签；不下载基础模型。
核对要点：v3 同时含 inductive（训练集拟合后测试）与 transductive（整份待测集参与）设定；training-free 不代表没有分布适配。
作者代码：[仓库](https://github.com/Afleve/self-adaptive-Optimal-Transport)；许可未核实。

**S02-LIT-02 · MAG** — [Integrating Multimodal Information in Large Pretrained Transformers](https://aclanthology.org/2020.acl-main.214.pdf)。ACL 2020 proceedings, pages2359-2369（2020-07）。

采用：M 的文本主干与受控音视频残差只受该思想启发。 排除：不复现 BERT/XLNet 内部插层与端到端微调；不改为 token 接口或导入外部情感权重。
核对要点：本轮小型连续特征网络不等于 MAG-BERT；论文指标不能直接写成本轮结果。
作者代码：[仓库](https://github.com/WasifurRahman/BERT_multimodal_transformer)；许可未核实。

**S02-LIT-03 · ALMT** — [Learning Language-guided Adaptive Hyper-modality Representation for Multimodal Sentiment Analysis](https://aclanthology.org/2023.emnlp-main.49.pdf)。EMNLP 2023 proceedings, pages756-767（2023-12）。

采用：作为语言主干及可见非语言门控的动机；不实施完整 ALMT。 排除：不导入其情感权重；不采用跨 epoch 拼接最佳指标，保留本轮同一冻结 checkpoint 的全部指标。
核对要点：作者 README 说明 acc2/F1 与 MAE 最佳值可来自不同 epoch，并另报同epoch结果；论文二分类 F1 不等于本题三分类 macro-F1。
作者代码：[仓库](https://github.com/Haoyu-ha/ALMT)；[MIT](https://github.com/Haoyu-ha/ALMT/blob/master/LICENSE)。README 标注2025-03-06更新与整理；不是已核验的2023代码快照。

**S02-LIT-04 · P-RMF** — [Proxy-Driven Robust Multimodal Sentiment Analysis with Incomplete Data](https://aclanthology.org/2025.acl-long.1075.pdf)。ACL 2025 long papers, pages22123-22138（2025-07）。

采用：仅提醒明确缺失可用性与不确定性，保留小型合规对照。 排除：完整 VAE/proxy/reconstructor 不实施；论文随机擦除与文本[UNK]协议不替代本题连续局部缺失及官方特征接口。
核对要点：原文是训练后在缺失条件评价；不能误写为必然使用 test 拟合。本次没有审计其不可访问代码。
作者代码：[仓库](https://github.com/aoqzhu/P-RMF)；许可未核实。GitHub根页/README抓取失败；尝试main分支raw README/LICENSE返回404；不能据此断言整个仓库不存在。

**S02-LIT-05 · Gradient-Blending** — [What Makes Training Multi-Modal Classification Networks Hard?](https://arxiv.org/html/1905.12681v5)。arXiv:1905.12681v5; CVPR 2020（2020-04-03）。

采用：保留单模态对照，作为解释多模态未提升的一种待检验机制。 排除：不增加 Gradient-Blending 内部试训或自适应网格；其权重估计使用训练集留出部分，不能换成官方 valid 的梯度训练。
核对要点：论文视频/音频分类现象不能证明本题性能原因；同名方法未在S02实施。
作者代码：[仓库](https://github.com/facebookresearch/VMZ)；[Apache-2.0](https://raw.githubusercontent.com/facebookresearch/VMZ/main/LICENSE)。仓库已归档；README标注Gradient-Blending为Caffe2实现。

**S02-LIT-06 · Knowledge distillation** — [Distilling the Knowledge in a Neural Network](https://arxiv.org/html/1503.02531v1)。arXiv:1503.02531v1（2015-03-09）。

采用：M4限于同seed已冻结S01教师在官方train上的stop-gradient软目标；固定0.1、tau=2来自S02提示词，非论文推荐最优值。 排除：不使用valid/test伪标签训练，不把完整teacher输入提供给推理student；不引入外部情感教师。
核对要点：固定teacher时KL(teacher||student)与软标签交叉熵仅差teacher熵，梯度等价。arXiv备注NIPS2014 workshop，Google页标2015；采用可核对的2015 arXiv版本，不猜测会议年。
作者代码：本次所读原文及作者机构页面未识别官方实现；未用第三方实现补作作者证据。

**S02-LIT-07 · Temperature scaling** — [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf)。ICML 2017; PMLR70:1321-1330（2017-08）。

采用：区分校准和分类决策；同一logit向量正温度缩放不提升其argmax Accuracy/F1。 排除：不新增温度搜索；Neutral logit偏置是本任务预定义决策候选，不冒称Guo温度缩放。
核对要点：argmax不变结论针对单一logit向量的正标量缩放；不推广为任意多模型概率组合都不变。
作者代码：[仓库](https://github.com/gpleiss/temperature_scaling)；[MIT](https://raw.githubusercontent.com/gpleiss/temperature_scaling/master/LICENSE)。作者README明确标注不再维护、原为PyTorch0.3演示。

SOTA 实际阅读来源是指定 arXiv v3；其作者仓库 README 与 CVF 主站检索支持 CVPR 2026 归属，但本次未取得会议 PDF 正文，也未声称读过用户本地 PDF。SOTA、MAG 的许可证未核实；P-RMF 代码访问未成功，不能推断其许可证或代码行为。已确认的软件许可不等于数据/权重许可。

S02 仅保留提示词内的 15 个组合/偏置配置与最多 12 个新 fit；固定参数来自该任务约束。文献不授权 test/附件3/4 适配，不增加搜索或使用外部情感权重。原论文的二分类 F1、不同 epoch 最佳指标及基准数据设置不可直接作为本题三分类成绩的对比。

机器可读版本、完整版本说明、正文定位、许可链接与访问限制见 [sources.json](sources.json)。
