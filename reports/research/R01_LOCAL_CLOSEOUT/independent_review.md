# 实际独立只读技术审查

来源：本任务实际spawn的独立上下文 /root/r01_readonly_review，工具请求GPT-6 Astra/xhigh。作者未冒签独立审稿。以下为独立审查结果的转录与结构化归档，文件绑定见independent_review.json；不构成用户批准。

第一次审查从修订01复现四个问题：C0/R0选择目标不同导致增强归因混杂；三seed均值通过不能保证seed17；等1e20logits的CE返回0而不是log3；相同人数但不同资格集合被aggregate接受。它未重跑历史64/28检查。96/144计权、有理数窗口、共同合法集合、一次clean回退在所读范围未发现新算术缺陷。gate计数4352与4272差1.84%为代数更正。

最终定向复核：四项问题及gate计数在设计/标准库参考层闭合，未发现新增实质缺陷。C0排除B*且与R0统一attempted96选点；seed17失败回B*17；CE先top-target后logsumexp并拒绝溢出；聚合绑定有序群体、资格集合、同replicate视图与编号，单seedcheckpoint独立支持。

审查者实际执行15项只读合成反例/一致性探针，全部通过exit0，未写文件。父任务63项检查记录及四源码hash与当前一致。未读原始数据、未跑官方tests/模型训练。PROVISIONAL未变，不是负责人冻结批准。

实际探针命令为PowerShell stdin管道调用本机Anaconda Python -X utf8 -B -，cwd为OS_TEMP；审查者未采集该解释器版本，不能借用作者的3.12.14版本。路径去敏的命令记录见JSON。research/r01/independent_probes.py保留同逻辑、仓库相对root的可移植版本，归档后未另跑，不能把它的文件hash冒充原stdin字节hash。
