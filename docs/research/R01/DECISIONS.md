# R01 决策收敛登记

[SPECIFIED] 主研究负责人已明确批准R01-FREEZE-01，当前状态FROZEN_FOR_S01_PROTOCOL。批准对象为commit120a0938c76dd457a3d95c5c2a243f3e451a3f67中的16项限定协议，见FREEZE_01.json。下面保留P01至P11的原建议及备选理由；decisions.json是审批前历史建议记录，不作为当前批准状态。批准来自本轮用户指令，不来自作者自审或独立技术审查。

| 决策 | 处置 | 明确建议 | 备选/否决/推迟 | 理由 |
|---|---|---|---|---|
| R01-P01 | 采用 | 三单模态+原始拼接+prior/late；C0只作机制底座 | 仅文本可作24档内参考，否决未比较就称最优 | 覆盖弱对照并复用late已训练组件，39档可解释增量 |
| R01-P02 | 采用 | B块比较Identity与train-only z-score，按B-CAT三seed定公共normalizer | 不为各鲁棒架构单独搜索normalizer | 控制搜索量且保持D-DATA-07；未确定哪一种更好 |
| R01-P03 | 采用 | 96名义条件/144视图；共同窗口∩O；无资格一次clean回退；attempted主评分 | eligible-only仅并列诊断；独立窗/TAV局部协议推迟 | 不删难样本、不把random重复增权；适用范围不涵盖全部Q2组合 |
| R01-P04 | 采用 | C0/R0/R1/R2/R1-cap，共同attempted96选点；首轮39run | 预算不足在运行前选择24或30；否决据结果临时加模型 | C0/R0增强因素不再混入选择规则；R0/R1仍是编码器包 |
| R01-P05 | 推迟 | 交互R3和cross-attention R4不纳入首轮 | 否决因论文效果直接升级本题主模型 | 额外容量/信息/搜索因素尚无本题实证收益 |
| R01-P06 | 采用 | 固定CE+MAE/3、w=1、lambda=1；真实重建函数仅合成核验 | Huber/类权重L块推迟且不进入不对称最终搜索 | 保持首轮目标简单与可辨识；不把解析设定称最优 |
| R01-P07 | 采用 | 三层选择；macro-F1主、MAE次，epsilon .01/.05；共同机制选点 | 无可行鲁棒候选保留B*；否决bootstrap消除选择偏差 | 固定三类与null Pearson，明确同valid重复选择局限 |
| R01-P08 | 采用 | 17/29/43三seed均值排名，最终17额外clean守卫失败回B*17 | 关闭ensemble；否决挑最好seed或事后改阈值 | 均值约束并不保证部署seed满足；新增守卫保护实际选定模型 |
| R01-P09 | 推迟 | KD与重建训练均不进入首轮 | 若再研究须独立有限预算和独立监督来源 | teacher错误/过拟合和重建成本未实证；现在只保留正确公式 |
| R01-P10 | 采用限定范围 | KNOWN_AVAILABILITY模拟研究可继续，专项部署UNKNOWN | U1优先请求可信mask规范；U2无oracle可靠性适配推迟另批 | 不因forward不收C就宣称无oracle；不能用text零行补洞 |
| R01-P11 | 推迟 | Q3只保留映射/归因provenance接口 | 否决注意力=因果解释或index/50造秒 | 独立Q3授权与真实映射证据未具备 |

## 已批准范围：R01-FREEZE-01（FROZEN_FOR_S01_PROTOCOL）

本轮批准冻结以下限定研究协议：KNOWN_AVAILABILITY；96/144窗口与回退计权；train根2207、valid根1103、训练seed17/29/43；B*与共同机制选点；macro-F1/MAE优先级与epsilon_F=.01、epsilon_M=.05；patience10/min_delta1e-4/max_epochs100；seed17及失败回B*17；39run核心预算；D/T/L不启用；实际资源时限必须另填后方可执行。批准版本的文件SHA256由FREEZE_01.json绑定；旧MANIFEST保持原字节并仍指向其历史commit。

这次确认只冻结协议，不启动训练、不激活S01、不允许读取test/专项。若负责人选择24或30档，须同步删去不可支持的机制主张。U2、新TAV局部协议、Q3、unaligned、ensemble、KD/REC、66扩展及任何训练授权均不包含在此范围。

[SPECIFIED] 批准已取得，但training_authorized=false。必须设定wall-time上限的原则已冻结；具体小时数未给定，resource_walltime_cap=null，未来S01激活前需实际硬件/非选模资源测量与execution config。为空禁止批量训练。附件3可靠mask availability保持UNKNOWN。下一阶段仅为S01_SPECIFICATION_AND_EXECUTION_AUTHORIZATION，未激活。
