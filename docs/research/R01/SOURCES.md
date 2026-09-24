# 来源、公式和局限

[VERIFIED] 研究固定基线ec228a04e9c6579a3fd95342e4438c20425a34dc；较修订01的4bd0c6c更新81文件，详见reports/research/R01_LOCAL_CLOSEOUT/source_ledger.json逐路径差异及8份治理/合同指纹。S00E更新预期内，D-DATA七行语义逐行相同。docs/DATA_CONTRACT_EVIDENCE.md工作树CRLF与Git blob LF不同；记录两个原始hash，研究依据固定commit字节，未静默混合快照。

[VERIFIED] S00E可信批准从原生host事件重读；25份源码/6份证据绑定hash一致，21Gate全PASS，E21记录实际read-only preflight；Release再次下载188247字节、SHA256 e6cd31f0bb9af1ea6e79e5452645fec1afda2a296166db52f1e7fe41041625bf匹配。工程任务idle，正式工作树初始干净。该批准只覆盖S00E，不批准R01模型。

[VERIFIED] 旧修订ZIP SHA256 3339d6c805f3d1048dd97004f1d0b083df2205b556bb528f385accd69c6cbd20；77成员/76非MANIFEST成员的字节hash、size、CRC、集合、路径、独立MD都通过。本轮读取七项回应、完整设计、P01至P11、矩阵、源码及历史检查记录；未将历史64/28重命名为本次检查。既有题面提取/公开聚合事实继续按来源引用，没有重读原始PKL、样本CSV或专项内容。

公式分类：S/O/Z/P来自冻结合同；局部窗口、attempted策略、C0/R0/R1/R2/R1-cap、双头组合与三层选型是本研究的提案构造（derived/design），不主张首创。维度和边界推演见DESIGN，有限参考检查不等于公式的通用证明。R1的partial convolution是这里明确写出的邻居均值变换，未声称复现其他同名论文。

- [Tsai et al. (2019), Multimodal Transformer for Unaligned Multimodal Language Sequences](https://aclanthology.org/P19-1656/)：Abstract; directional crossmodal attention motivation only, no formula equivalence or competition efficacy。来源字节指纹见sources.json。
- [Arevalo et al. (2017), Gated Multimodal Units for Information Fusion](https://arxiv.org/abs/1702.01992)：Abstract; gating motivation only; R2 shared scalar softmax construction is our proposed variant。来源字节指纹见sources.json。
- [Hinton, Vinyals, Dean (2015), Distilling the Knowledge in a Neural Network](https://arxiv.org/pdf/1503.02531)：Section 2, PDF pages2-3, temperature probabilities and T squared soft-target scaling。来源字节指纹见sources.json。
- [Cawley and Talbot (2010), On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation](https://www.jmlr.org/papers/volume11/cawley10a/cawley10a.pdf)：Abstract and introduction, PDF pages1-3; model selection can overfit its evaluation criterion。来源字节指纹见sources.json。

[INFERRED] KD的KL与教师soft-target交叉熵仅差不依赖student参数的教师熵；teacher stopgrad时梯度相同。回归蒸馏项与本题联合权重是提案，不来自该论文的本题实测。MulT/GMU仅提供机制研究动机，不支持本题效果或R2完全同构。Cawley/Talbot支持模型选择偏差风险；本设计的cluster/bootstrap限制另为统计推论，未声称普通bootstrap消除偏差。

[UNKNOWN] 专项可靠S/A、contextual文本向量的信息残留、真实时间映射、性能/耗时/显著性均未知。论文目前只能写合同、设计推导、有限合成校验和局限；不能写模型优胜或完成比赛。未学习历年语料风格，未进行最终版式/匿名比赛提交审核。AI使用为OpenAI Codex本地研究辅助，用户此前确认Astra/xhigh；作者底层模型身份无独立遥测，发布日期UNKNOWN。独立审查模型设置由spawn工具请求Astra/xhigh，技术审查不构成研究负责人批准。
