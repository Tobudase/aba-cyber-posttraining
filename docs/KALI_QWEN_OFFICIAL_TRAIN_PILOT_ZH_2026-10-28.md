# KaliBench 官方 TRAIN：Qwen3-8B 高置信度试点（2026-10-28）

## 结论与数据性质

第二底座改用 [KaliBench-Verified 发布方 TRAIN](https://huggingface.co/datasets/RISys-Lab/KaliBench) 中的已验证记录，避免让此前 240 条自编且尚待独立审查的数据进入这次 SFT。发布方的 `ACCURATE` 和终端 `pass_review` **不是逐条独立专家金标**。原始 3,504 条 TRAIN 中，终端结果有 954 条 `PASS_EXECUTED`、2,355 条运行环境错误、195 条超时。项目既有的评分一致性筛查保留 3,376 条，排除了 128 条；其中 `PASS_EXECUTED` 为 936 条。本次只从这 936 条构建试点，保留“发布方核验的银标”名称。原始命令只作为文本标签，未被本项目执行。

| 阶段 | 训练 | 开发 | 说明 |
|---|---:|---:|---|
| 完整高置信度分组划分 | 715 | 221 | 按工具和空白标准化后的标准命令分组 |
| 固定小试点 | 512 | 128 | 开发集 125 种工具，均在训练侧有该工具示例 |

精确问题、分组键、试点中的精确标准命令在训练与开发之间均无交叉。配置与划分在任何 Qwen 模型输出前冻结。开发题源自**官方 TRAIN 的内部留出**，不能称为独立外部验证，更不能称为官方 TEST 成绩。官方 TEST 读取 0 条。

## Qwen 编码与实测

底座固定为 [Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) 的 revision `b968826d9c46dd6066d109eabc6255188de91218`。使用其原生 chat template，`enable_thinking=false`，提示词末尾是已经闭合的空 `<think>` 块；训练目标只含发布方 `<output>` 命令块及 EOS。全部 512 条训练行的提示词 token 以 `-100` 遮蔽，目标和 EOS 才计算损失；完整解码往返、长度上限 2,048 token 和私有文件哈希均已通过独立复核。最长训练序列 520 token。128 条开发输入与私有答案分开保存，开发输入没有标准命令或目标字段。

固定试点配方为单卡、BF16、LoRA `q_proj/v_proj` 全层、rank 16、alpha 32、1 epoch、最大 512 次优化、batch 1、学习率 `2e-5`；评测拟用贪心解码、最多 512 个新 token，并同时报告 KaliBench 原生分项指标与精确命令匹配。它是**预先固定的 SFT 工程试点，不是 ABA 自动搜索**。配方尚未通过真实 GPU 内存与训练验证。

## 当前边界与运行门槛

本次完成的是数据划分和本机 tokenizer/标签检查：**模型推理 0、GPU Job 0、优化步 0、官方 TEST 0**。Qwen 五个权重分片总大小约 15.26 GiB，尚未在 Nautilus 缓存。2026-10-28 的只读集群检查显示普通 Pod 配额有空间，但这不保证空闲 GPU；同命名空间另有任务在使用 A100。不能让 GPU 等待权重下载。先用有截止时间的 CPU Job 下载并校验固定 revision 权重，在不占用他人任务的情况下再做单卡加载检查、同协议开发基线、固定 SFT、同开发集复测。所有任务应普通优先级、有限时长、结束后清理；开发结果不会自动替换现有 RedSage-K 默认模型。

公开仓库提供[固定划分配置](../configs/kali-qwen-official-executed-pilot-2026-10-28.json)、[划分脚本](../scripts/prepare-kali-qwen-official-executed-pilot.py)、[编码配置](../configs/kali-qwen-official-executed-encoding-2026-10-28.json)、[编码脚本](../scripts/prepare-kali-qwen-official-executed-encoding.py)和[汇总回执](../results/kali-qwen-official-executed-pilot-2026-10-28/summary.json)。原始 TRAIN、逐题划分、token 数组和开发答案保留在私有本地工作区。此前较宽松划分仅有 159/640 条成功执行记录，已记录但不作为本试点的训练数据。
