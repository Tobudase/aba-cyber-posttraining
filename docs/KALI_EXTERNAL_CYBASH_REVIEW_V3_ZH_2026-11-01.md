# KaliBench 外部候选题逐题复核进展（2026-11-01）

本轮复核的是此前 32 道 CyBashBench 外部候选题的**题意与发布方参考命令**，没有向候选题调用模型，也没有打开 KaliBench 官方 TEST。复核使用发布方固定版本的题目以及工具的官方文档；这是 AI 辅助静态筛查，**不是**独立真人复核或运行环境验证。

| 静态结论 | 题数 | 处理 |
| --- | ---: | --- |
| 明确不适合作为原题的标准答案 | 2 | 从下一版复核队列剔除 |
| 题意或环境需要先明确 | 9 | 保留待人工裁定 |
| 命令看起来符合题意，但尚未认证 | 20 | 保留待版本与夹具验证 |
| 同上，但发布方时间标签来源较弱 | 1 | 单独标记 `model_estimated`，严格复核 |

两道明确偏差是：

1. `forensics/nl2bash_116`：要求构造最近 24 小时文件修改时间线；参考命令把 `find -ls` 的人类可读月/日字段交给 `sort -k8,9` 排序，不能可靠按完整时间戳排列。[GNU find 文档](https://www.gnu.org/software/findutils/manual/html_mono/find.html)、[GNU sort 文档](https://www.gnu.org/software/coreutils/manual/html_node/sort-invocation.html)。
2. `reverse/nl2bash_097`：要求提取**长于** 20 个字符的字符串；`strings -n 20` 包含**恰好** 20 个字符的字符串。[GNU strings 文档](https://sourceware.org/binutils/docs-2.19/binutils/strings.html)。

两道 `find` 题是否把目录算作“file”取决于约定，因此列入待澄清的 9 题，没有直接判错。[GNU find 的文件类型说明](https://www.gnu.org/software/findutils/manual/html_mono/find.html)。此前已剔除的 5 道题不计入上述 32 题。

剔除 2 题后原队列剩 30 题，低于预设的 32 题门槛。为方便继续复核，从**同一来源**增加 6 道发布方标为 `human_reviewed` 的 `misc` 类、与安全运维或 Linux 命令相关的候选题，形成 **36 题 V3 审核队列**。这是看过 V2 标签后的适应性补题；它没有增加来源多样性，也不是已冻结的外部验证集。新增题涉及 `sudo`、`tcpdump`、`find`、`ss`、`env`、`chown`；其中网络抓包和改属主命令未运行，`ss` 题的“所有端口”范围也需人工确定。

V3 的固定发布方源版本为 [`178c0da…`](https://github.com/lyptus-research/cyber-task-horizons-data/tree/178c0da1800f9c07311e1b8d6c61dd8104e7b4ae)，源文件 SHA-256 为 `3ad067b036d8d28cfd8cef23b594c635c7b040ce8494fd5466f9a88184334935`。36 题与现有内部训练/开发文件未出现精确或现有门槛定义的近似重合；与 KaliBench 完整官方 TRAIN 3504 题的题目/命令**精确**重合为零。来源分离不能证明模型预训练时没有接触过类似题目。

**当前准入状态：`NOT_ADMITTED`。** 36 题中独立真人签核 **0**、目标工具版本验证 **0**；静态准入门返回 72 个待办（每题各缺版本验证和独立复核）。填写表格的程序也只能检查字段，不能证明填写者身份或语义正确。后续需独立研究成员逐题验证题意、命令和目标版本，明确 9 道有条件题，剔除不合格题；只有至少 32 题通过、复核真实性由负责人核验且在模型输出前冻结，才可作为外部验证数据。需要补题时须再次记录补题规则和来源。

上述**静态核查阶段**新增模型调用、优化器步骤、GPU 作业、发布方命令执行和官方 TEST 访问均为 **0**。现有模型选择不变。

## 后续有限 Linux 夹具核验

在 Nautilus 提交一个限时、无 GPU、避开 GPU 节点的 CPU Job，对**自造的无敏感临时文件**做 10 项离线工具行为检查，全部通过。使用的工具版本包括 GNU findutils 4.8.0、GNU binutils 2.38（`strings`/`readelf`）、GNU coreutils 8.32（`sort`）、GNU tar 1.34、OpenSSL 3.5.2 和 glibc `ldd` 2.35。`strings -n 20` 确实包含恰好 20 字符的字符串；`sort -k8,9` 在跨月份的示例中未按时间顺序排列；`find` 的两个相关例子确实包含目录。断链、压缩包、证书解析/公钥、ELF 头/节表及**可信系统 `/bin/ls`** 的依赖查询也通过了各自的窄夹具。相关证据可支持 11 道题的局部判断，但**不是 11 道题已经认证为标准答案**，更不覆盖全部 36 题。[脱敏夹具结果](../results/kali-external-review-v3-2026-11-01/linux-safe-fixtures.json)。

CPU Job 及 ConfigMap 已删除，剩余自有集群对象为 0；没有运行外部目标扫描、抓包、真实文件属主修改或不可信二进制的 `ldd`。其中 3 条发布方参考命令是在**自造文件或可信系统 `/bin/ls`** 上原样运行的，不涉及真实目标。新形成的 V3 AI 静态分类为 **10 道需明确上下文、25 道看起来可行但未认证、1 道较弱时间标签来源且未认证**。独立真人签核仍为 0，目标工具版本作为全部题目标准答案的认证仍为 0；准入状态不变。Nautilus 的[批处理与资源规范](https://nrp.ai/documentation/userdocs/running/jobs/)要求任务自行结束并清理资源，本次 Job 已按此执行。
