# KaliBench 训练工具覆盖与外部数据来源核查（2026-11-01）

## 官方 TRAIN 的静态覆盖

对项目保存且哈希固定的 [KaliBench 官方 TRAIN](https://risys-lab.github.io/KaliBench/) 3504 条记录进行了**只读**统计，同时检查发布方的 `tool_name` 字段和参考命令的首个可执行 token。记录覆盖 **962 个 `tool_name`**，其中 157 个工具只有一条记录，307 个工具最多两条；26 条记录的工具元数据与命令首 token 不完全一致，因此两种口径都单独统计。

本项目此前检查的 12 种常见命令工具——`grep`、`tshark`、`openssl`、`sha256sum`、`wc`、`head`、`tail`、`jq`、`tcpdump`、`nmap`、`find` 和 `strings`——在这 **3504 条 TRAIN** 中，按两种口径均为 **0 条直接样本**。这比先前只核对已选 638 条训练样本更全面。它说明现成官方 TRAIN **不能直接提供这些工具的监督示例**；并不证明覆盖缺口是模型退化的唯一原因，也不说明模型没有预训练知识。没有打开或查询 KaliBench 官方 TEST。[可核算汇总](../results/kali-train-tool-coverage-2026-11-01/summary.json)

## 不同来源的候选

当前 32 题 [CyBashBench V2 清单](KALI_EXTERNAL_REVIEW_V2_ZH_2026-10-31.md)仍属**同一来源**，且独立真人签核为零。为寻找另一来源，核查了下列发布方材料：

| 来源 | 与当前任务的关系 | 目前用途 |
| --- | --- | --- |
| [Lyptus 发布的 NL2Bash](https://github.com/lyptus-research/cyber-task-horizons-data) | 有自然语言到 Bash 配对，但本地固定的 136 条以通用 Shell 为主，安全相关题存在重复或弱标签 | 暂不纳入网络安全验证；可继续逐题调查 |
| [IBM NL2Bash 执行评测](https://github.com/IBM/nl2bash-eabench) | 含系统管理与脚本任务，发布方以容器执行结果评分；其中不少题要求完整脚本而非 KaliBench 的单条命令 | 适合作为独立的执行式辅助评测研究，不能直接混入当前单命令清单 |
| [NL2SH-ALFA](https://huggingface.co/datasets/westenfelder/NL2SH-ALFA) | 其发布方测试集侧重一般 Bash 翻译；项目已固定版本但未查询模型 | 保留为未来一次性通用能力检查，不当作网络安全领域验证 |
| [CLI-1M 数据卡](https://huggingface.co/datasets/carosh/cli-1m) | 提供安全领域的自然语言—命令训练数据；发布方的标准评测集位于另一个需申请访问的数据仓库 | 不能把训练样本直接当独立验证金标准 |

这是一轮**有限来源调查**，不能证明不存在其他合适的数据集。调查期间没有新增模型调用、训练、GPU 作业、数据集命令执行或官方 TEST 访问。可操作的下一步是让独立研究成员复核 CyBashBench 逐题语义与目标工具版本，并继续寻找有公开题目、可核对标签、与单命令安全任务匹配的第二来源。在验证集冻结之前，不用这些已见候选题选择模型。
