# R01 本地研究入口

状态：FROZEN_FOR_S01_PROTOCOL（仅R01-FREEZE-01批准范围）。父任务R01_Q2_BASELINE_AND_ROBUST_MODEL_RESEARCH_DESIGN；本轮R01_ASTRA_LOCAL_RESEARCH_CLOSEOUT。S00E已验收发布并重新核验；本轮没有正式模型实验，S01未激活。

- DESIGN.md：完整公式、mask接口、缺失生成、三层选择、有限预算和机制边界。
- DECISIONS.md / decisions.json：P01至P11审批前建议及备选理由；当前批准以FREEZE_01.json为准。
- protocol.json / trials.json / 两张R01矩阵：首轮冻结39核心；66仅历史后置计划、未批准。全NOT_RUN、metrics=null。
- SOURCES.md / sources.json：固定commit差异、来源、原论文核验范围与局限。
- REVISION_TRACE.md / CLOSEOUT.md：继承修订01及本次实质变化。
- ../../../research/r01/：纯标准库参考和合成检查；不是正式训练入口。
- ../../../reports/research/R01_LOCAL_CLOSEOUT/：前置核验、历史边界、本轮检查、独立技术审查和发布安全证据。
- ../../../state/LATEST_RESEARCH.json：独立科研状态；不改工程LATEST_RUN。

在仓库根运行 python -X utf8 -B research/r01/run_checks.py --output <SCRATCH_RESULT_JSON> 可复核本轮合成检查。不要将scratch结果写回已发布证据后仍声称原SHA256有效。原修订ZIP保留本地，不复制入Git，不再生成网页交接包。本目录为研究设计工作稿，不是最终比赛论文或训练批准。

FREEZE_01.json绑定负责人明确批准的原commit与文件hash。wall-time上限原则已冻结但具体小时数未设定，null禁止批量训练。S01仍需独立规格及执行授权，专项可靠mask仍UNKNOWN。旧CLOSEOUT、REVISION_TRACE、sources和reports保留历史状态；旧MANIFEST/独立探针应对其绑定commit复核，不把当前治理元数据变化算作历史校验失败。
