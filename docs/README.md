# 项目阅读指南

[English overview](../README.md) · [按问题查结果](../results/README.md) · [按时间查实验](../EXPERIMENT_LOG.md) · [查技术报告](REPORT_INDEX.md)

这个项目研究一个实际取舍：后训练能否让 Qwen3-8B 多做对一些 KaliBench 任务，同时保住原来会的能力？实验从固定数据微调，推进到 ABA 自动训练与选择候选模型，再到教师轨迹监督。**当前保留原始 Qwen3-8B。** 下面三项结果说明了原因。

| 想了解什么 | 最值得看的结果 | 证据 |
| --- | --- | --- |
| 微调带来了哪些提升？ | 在 87 个此前未查询的内部开发样例上，严格正确数从 18 增至 26。训练中未见工具的 22 个样例仍只答对 5 个。 | [逐项分析](KALI_QWEN_UNQUERIED_CONFIRMATION_ZH_2026-10-28.md) · [前后对比图](../results/kali-qwen-confirmation-2026-10-28/before-after.png) |
| ABA 选出的模型可以替代底座吗？ | ABA 完成了两个候选的训练和评分。两个候选和固定微调对照都未同时满足旧能力保持与输出完整性要求。 | [决策与限制](../results/kali-qwen-native-aba-2026-11-15/RESULT_ZH.md) · [内部确认集图](../results/kali-qwen-native-aba-2026-11-15/confirmation.png) |
| 教师解释到底增加了什么？ | 学生能复现教师示范。在第二个单题实验中，仅答案监督就修复了漏写程序名的问题。Qwen 轨迹组还保住了另一道编译工具题。跨八个预选来源的较早对照中，原始底座得分最高。 | [单题复现与解释评分](../results/teacher-transfer-2026-11-23/RESULT_ZH.md) · [八来源对照](../results/constraint-audit-2026-11-23/RESULT_ZH.md) |

**读分数时先看分母。** 18/87 和 26/87 来自同一批开发样例。八来源对照的 23/24 来自八个来源、每题三次解码。最新筛查中另有一个 23/24，来自另一批八个来源，用途是寻找学生反复出错的题。重复解码不会增加独立题源数。这些都是内部指标，官方 TEST 保持封存。

## 找原始记录和项目材料

| 材料 | 从哪里开始 |
| --- | --- |
| 全部实验与结果 | [按主题浏览结果](../results/README.md)，或在[分阶段日志](../EXPERIMENT_LOG.md)中查时间线、失败记录和当时的决定。 |
| 技术报告与核验记录 | [报告索引](REPORT_INDEX.md)收录本目录的研究报告。[核验记录](verification/)保存早期环境、评分和数据检查记录。 |
| 训练、评测与测试代码 | [技术实现导览](../scripts/README.md)按用途指向代码。[教师 SFT 快照](../code-snapshots/teacher-sft-20261117/README.md)说明该阶段实际采用的实现和限制。 |
| 数据、模型配置与来源 | [数据目录](../data/)包含清单、合成样例和公开小型数据集。[配置](../configs/)记录模型、依赖及实验协议。[来源与使用条款](../NOTICE.md)说明各材料的发布范围。 |
| 早期集成与产物 | [合成 ABA 示例](../examples/aba-bigram/)、[上游兼容补丁](../patches/)和 [CTI 小型接口测试产物](../artifacts/cti-source-pilot-tiny-adapter/)对应早期工程验证。 |
| 在自己机器上核对数字 | [复算指南](REPRODUCTION.md)列出离线检查命令、预期输出以及需要原始环境的部分。 |
