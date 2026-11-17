# 教师筛选、数据隔离与学生基线：2026-11-16

当前状态：**IN_PROGRESS**。学生任务状态快照：**Pending**。这是一次无训练的准备阶段，不是新 ABA/SFT 效果报告。

## 1. 已完成的数据隔离

源文件为 publisher verified TRAIN；源文件、评分器和输入哈希在私有记录中冻结；公开 [aggregate.json](aggregate.json) 仅保留模型 revision、协议与计数。保守清点了 164 份历史文件中的 1,884 个被提及 ID，排除已出现样本及同工具/选项结构的样本，再限制为离线二进制、文件与取证分析任务。

留下 115 题，按完整结构组分为 TRAIN67 / DEV24 / confirmation24，组数分别为 57/23/22。67 题涉及 24 个工具，全用于本次 TRAIN 教师筛选。原计划最多 96 题，实际不足时没有放宽隔离规则。三份数据在 ID、完整问题哈希、工具名+选项键+位置参数数量结构上无交集。DEV24 与 confirmation24 未发给任何模型，未发布题目或答案；官方 TEST 不读取、不调用。

这不是完整语义去重，也不能证明模型预训练没有接触过来源数据。历史审计只覆盖记录到的文件。小样本、稀有工具和离线分析范围限制了可推广性。**67/67 源参考记录的发布方标签均为 PASS_RUNTIME_ERROR**：运行非零退出但未检测到工具/参数幻觉，不是成功执行证据。这里的 publisher verified 不能解释为语义正确或行为验证通过。参考答案自评分通过也不能替代行为检查。

当前保守排除历史提及的做法使剩余池偏向缺乏环境支持的稀有工具，因此这轮定位为可用性诊断，不能直接作为高质量蒸馏集。后续允许在新协议中重新使用已验证的历史 TRAIN；已用于 DEV/确认的内容仍应隔离。TRAIN 曾被模型查询过不等于数据泄漏，无需为追求 TRAIN 新颖性牺牲标签质量。不得事后替换本轮冻结的67题。

## 2. 统一输入与真实调用

所有模型收到同一个 system 指令与原始题目，要求简洁解释，并在唯一 `<output>...</output>` 中提交命令。没有参考命令、评分标签或额外工具提示。该提示不同于官方 command-only 评测。

- 教师1：NRP `qwen3-small`，实际响应报告 `Qwen/Qwen3.8-27B-FP8`。
- 教师2：NRP `gemma-small`，实际响应报告 `google/gemma-4-12B-it-qat-w4a16-ct`。
- 别名可能更新；记录了每条响应模型名和哈希，没有假装固定教师权重 revision。
- 教师均 temperature=0.6、top_p=0.95、max_tokens=4096、seed=3407；Qwen 使用 medium reasoning effort。服务端是否完全实现全部参数不能仅凭提交参数证明。
- 两个学生臂均为原始 `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`，BF16，无 adapter、无训练。分别 enable_thinking=False/True。nonthinking 为 temperature=0.7/top_p=0.8，thinking 为 0.6/0.95；均 top_k=20、min_p=0、4096 token、batch4，每批 seed=3407+offset。
- 因 nonthinking 也收到可见解释指令，本试验比较原生 thinking 模式开关，不是严格的“有解释/无解释”消融；采样参数也随模式变化。

## 3. 核验结果

| Arm | Returned | Native exact | Supplemental strict | Truncated |
|---|---:|---:|---:|---:|
| Qwen3.8-27B-FP8 teacher | 67/67 | 6/67 | 6/67 | 0 |
| Gemma 4 12B QAT teacher | 67/67 | 9/67 | 8/67 | 28 |
| Qwen3-8B non-thinking | Pending | — | — | — |
| Qwen3-8B thinking | Pending | — | — | — |

The student job is submitted but has no completed artifact. GPU scheduling is the remaining blocker; no student scores or teacher–student gaps are claimed.

评分只读取唯一闭合 output 块；解释中的选项不会混入命令。截断输出按未完成计零，另列截断数。native exact 和 native partial 使用冻结评分器；supplemental strict 另检查必需参数值。它们都不是完整执行判定。

Qwen 无截断但参考严格匹配较少；Gemma 有 28/67 截断。因此不能仅按 9 比 6 就宣布后者更适合蒸馏，也不能把未完成回答都解释为知识不足。两教师严格通过的并集为 12 题、交集为 2 题。这不是学生困难集：必须等学生输出后才能计算差集。

## 4. 已找到的数据质量风险

对若干表面通过案例进行了文档及固定 shell 参数对照；这只是 AI 辅助定向复核，不是全部推理链语义认证。

- 某个 TRAIN 案例：Gemma 输出未加引号的 `~`。参考评分 strict 通过，但普通 shell 会把它展开成用户目录，无法保证得到题目要求的波浪号分隔符。固定 Bash `set --`/`printf` 参数对照已复现；没有运行生成的取证工具命令。
- 某个 TRAIN 案例：双引号内的反斜杠 n 不等于换行。native exact 通过，supplemental strict 拒绝；因此保留两种原评分，不事后改写分数。
- 部分解释把 `--delimiter` 当作 galleta 的别名，官方用法只列 `-d`，未证实的别名不能直接进入监督目标。
- Qwen 的一个 pedis 解释提到 `txt` 格式，而官方帮助列的是 `text`；最终 HTML 命令本身不受影响，但解释仍需处理。
- pepack 默认数据库的说法应精确到文件查找，而非含糊地描述为内置数据库；pescan 的示例 verbose/details 选项缺乏文档支持。

因此 **reasoning SFT 准入为 0**，没有把命令匹配当成推理可靠的证据。逐题记录及原始对照证据保留在私有工作区，不公开题目、回答或推理。

依据：[Kali galleta 文档](https://www.kali.org/tools/galleta/)、[Kali readpe 工具帮助](https://www.kali.org/tools/readpe/)、[pepack 源码](https://github.com/mentebinaria/readpe/blob/master/src/pepack.c)、[LLVM readelf 文档](https://llvm.org/docs/CommandGuide/llvm-readelf.html)、[LLVM addr2line 文档](https://llvm.org/docs/CommandGuide/llvm-addr2line.html)。

## 5. 网络、排队与算力

Qwen 第一轮有 31 个题目遇到 HTTP500，空白中性问题也失败；服务恢复后只补齐失败题，问题和生成配置未变，原失败记录保留。提前结束旧串行调度最多可能留下 2 个未收集的在途请求，未当作已完成样本。

CPU 模型暂存和哈希核验已完成并清理。三次未分配 GPU 的排队请求已撤销；当前只保留一个兼容 GPU 请求，1 CPU / 12 GiB RAM / 24 GiB ephemeral storage / 1 GPU，Pod 最长3小时、Job包括排队最长3.5小时，backoffLimit=0。没有提高优先级、加容忍 taint 或绕过配额。公开资源状态见 aggregate.json；集群对象标识和日志保留在私有工作区。学生运行时下载固定 revision 到节点临时盘并逐文件验 SHA；运行结束自动退出，收集后清理 Job/ConfigMap。

## 6. 可复核范围与复现限制

运行 `python3 scripts/verify-kali-teacher-screen-20261116.py` 可校验公开文件哈希、聚合计数范围、零训练/零保留集调用声明的一致性。公开验证器不依赖私有工件，但也无法独立从逐题响应重算模型分数。逐题评分、哈希、题目及原始响应均留在本机；完整隔离与解析检查已在私有工作区执行，5项测试通过。

公开内容仅包含脱敏汇总、图表及绘图/汇总核验代码。它不是完整实验的公开一键复现包，当前阶段也无新模型适配器。

## 7. 下一步

先收集并验证两个学生臂的各67条响应，计算“教师 strict 通过、两个学生模式均未通过”的 TRAIN 差集。随后逐题区分工具知识、约束理解、参数值、shell 引号、截断、评分器误差；用固定环境的正反例核验命令与简短公开解释，再建立 reasoning SFT 候选。只在训练数据够用且验证方案冻结后，开展同题 answer-only 对照与 explanation+answer SFT。未验证的解释、不完整输出、参考标签疑点均留在隔离区。

本次不查询保留集来选择教师，也没有为了产出正结果扩大 token 上限、挑选重复采样中的最佳回答或开始新训练。
