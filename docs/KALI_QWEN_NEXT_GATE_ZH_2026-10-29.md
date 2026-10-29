# KaliBench Qwen：下一轮数据复核与外部验证准入准备（2026-10-29）

**当前状态：已完成准备，尚未建立合格盲测集，也未运行新模型实验。** 上一轮 505 条派生训练的内部 DEV128 严格正确为 44/128，原 512 条方案为 43/128，但精确命令匹配同为 36/128、原生综合分数略低。不能继续用这 128 题挑数据或调参。本轮只处理复核与外部来源准入。

## 私有复核包

把此前分散的争议材料整理成 **52 个待裁定案例**：优先 10 个（训练数据中 7 个有逐题文档冲突风险的案例，以及两版 Qwen 适配器自动评分不同的 3 个 DEV 案例），后续 42 个有终端环境错误提示、但无法仅凭回执判错的 TRAIN 案例。每例保存原题、发布方参考、已有 AI 提示和可用文档；DEV 分歧案例还保留两版输出。另生成独立审核空白表，要求记录目标工具版本、证据、判定人与日期。原始题目、命令和输出只在私有工作区；**人工签核仍是 0/52**。公开只保留数量与哈希。[聚合记录](../results/kali-qwen-next-gate-2026-10-29/summary.json)；可在持有私有材料的工作区用 [`prepare-kali-qwen-next-review-packet.py`](../scripts/prepare-kali-qwen-next-review-packet.py)重建。

## 新外部候选来源

[Lyptus Research 公开的 CyBashBench 任务](https://github.com/lyptus-research/cyber-task-horizons-data/tree/main/data/tasks/cybashbench)包含 200 题命令生成及其他题型；其仓库说明数据许可为 CC-BY-4.0。我们固定仓库版本 `178c0da1800f9c07311e1b8d6c61dd8104e7b4ae`，只读下载任务文件，SHA-256 为 `3ad067b036d8d28cfd8cef23b594c635c7b040ce8494fd5466f9a88184334935`。本轮**没有执行其中任何命令**。

事先按任务元数据选取 `task_type=nl2bash`、`timing_source=human_reviewed` 且类别为 web／forensics／pwn／reverse／crypto 的 37 题；第一次静态准入发现 1 条重复命令，于任何模型输出产生前按来源 ID 固定排序、保留首条，得到 **36 条、24 种命令工具**。类别为 web 9、forensics 10、pwn 5、reverse 6、crypto 6；有 7 条带 shell 控制符，需优先检查。**`timing_source=human_reviewed` 描述计时来源，不能当成参考命令已经人工审核。** [候选摄取脚本](../scripts/intake-cybashbench-qwen-holdout-candidates.py)保留去重前后的私有审计记录。

准入脚本只读比较它们与现有官方 TRAIN512、内部 DEV128 和已查询 DEV93 的问题／参考命令。按固定的标准化和高相似阈值，未发现精确或高相似重合；这**不能保证语义无重合或模型预训练未见过**。36 条的目标工具版本均未核实，也没有独立语义签核，所以准入结果为 `NOT_ADMITTED`，**不是冻结盲测集**。[准入脚本](../scripts/gate-kali-qwen-external-holdout.py)要求来源、许可、工具版本、逐题独立审核和零模型查询声明齐全后才能冻结；一条故意与旧 TRAIN 重复的负例已验证会被拒绝。脚本不执行候选命令，也不调用模型。

CyBashBench 的这 36 条更适合作为**跨来源命令能力／保留能力候选面板**。其中一些任务很简单，与 KaliBench 的多工具选项值题分布不同；即使完成审核，也不应单独充当 KaliBench 领域主验证集。还需另找或构建有来源、工具版本和可核验标签的领域任务。作为另一备选，[CLI-1M 数据卡](https://huggingface.co/datasets/carosh/cli-1m/blob/main/README.md)把默认 validation 描述为手工整理；但对其公开 API 的 [0](https://datasets-server.huggingface.co/rows?dataset=carosh%2Fcli-1m&config=default&split=validation&offset=0&length=100)、[5000](https://datasets-server.huggingface.co/rows?dataset=carosh%2Fcli-1m&config=default&split=validation&offset=5000&length=100)、[10000](https://datasets-server.huggingface.co/rows?dataset=carosh%2Fcli-1m&config=default&split=validation&offset=10000&length=100)、[14900](https://datasets-server.huggingface.co/rows?dataset=carosh%2Fcli-1m&config=default&split=validation&offset=14900&length=100) 四个相隔较远页面抽样时，所见 400 条均标成 `quality_tier=synthesized`、来源为模型合成。因此本轮没有把它直接纳入高可信验证集；这只是抽样观察，不是整个数据集审计。

## 下一道门槛

1. 独立人员优先裁定 10 个高优先案例，再处理 42 个环境干扰案例；AI 提示不能替代签名。
2. 对外部 36 条逐题核对参考命令与目标版本，处理 7 条 shell 控制符案例，再运行准入脚本；若某题有争议，保留 `UNCLEAR`，不强行计入金标。
3. 在**任何新模型输出之前**锁定外部候选的文件哈希、评分规则和查询次数。该面板只作次要跨来源检查，主领域验证仍待建立。官方 KaliBench TEST 保持未使用。

本轮新增模型调用 **0**、优化步数 **0**、GPU 作业 **0**、官方 KaliBench TEST 使用 **0**；原有模型选择不变。

公开聚合可用 `python3 scripts/verify-kali-qwen-next-gate-public.py` 检查；这不会访问私有题目或重新运行模型。
