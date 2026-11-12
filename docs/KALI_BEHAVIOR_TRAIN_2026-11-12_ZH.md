# KaliBench：可执行核验的新增训练数据

本轮已经冻结 **64 条新增 TRAIN 银标、32 个任务类型、4 个工具**。它们来自 68 条自编候选，均在固定 Linux 镜像中实际执行参考命令，并以一条故意改错的命令检查行为判定程序的敏感性。64 条参考命令均通过本地行为检查，64 条配对错误命令均被拒绝；另 4 条参考命令未通过预设行为检查，继续隔离。4 条隔离样本的问题可能出在命令或检查假设，不能仅凭退出码为零认定正确。

| 工具 | 准入行数 | 任务类型 | 行为检查例子 |
| --- | ---: | ---: | --- |
| hardlink，util-linux 2.37.2 | 14 | 7 | 比较临时重复文件的 inode、链接数和内容；检查 dry-run、文件名过滤、大小、权限等要求 |
| virtualenv 20.26.6 | 16 | 8 | 检查环境配置、解释器复制/链接、激活脚本、旧目录清理和 seeding 状态 |
| dnstwist 20240812 | 14 | 7 | 对 `.invalid` 保留域使用离线 list 模式，检查生成域名是否符合指定变换 |
| pyi-makespec，PyInstaller 6.10.0 | 20 | 10 | 解析生成 spec 的 AST，检查打包模式、console、数据、导入、UPX 和 collect-all 等设置；不执行生成 spec |

所有文件操作都在自动清理的临时目录中进行。验证任务没有申请 GPU；对应 Job 和 ConfigMap 清理错误为 0。每种任务包含两个表面变体，因此 **64 行不能当作 64 个独立任务类型**。这些仍是 AI 自编、特定运行环境下验证的银标，未经独立专家复核。

## 数据与 SFT 格式核查

- 与发布方 3,504 条 TRAIN 比较后，归一化题目、完整命令均无完全重复；新数据内部也无这两类重复。这个检查不证明完全不存在语义重叠。
- 与受保护的内部 DEV、锚点、封存 final64 输入指纹无重合。封存输入只用于排除检查；没有生成其模型输出。官方 TEST 未读取。
- 使用固定 KaliBench 原生 prompt builder 生成消息，64 个参考目标在固定原生评分器下自评满分，且通过选项值检查。这只核查标签与评分格式的一致性。
- RedSage tokenizer 的 64 条完整序列均通过逐字回解。训练提示损失全部屏蔽，补全正确闭合已打开的 `<think>`，最后包含 EOS；最大序列 **411 token**，有效监督 token 总数 **1,626**，截断为 0。没有执行任何 LLM 优化器更新。

[训练数据](../data/kali-behavior-train-2026-11-12/train.jsonl) · [冻结清单](../results/kali-behavior-train-2026-11-12/manifest.json) · [逐条配对检查](../results/kali-behavior-train-2026-11-12/checks.json) · [SFT 编码核查](../results/kali-behavior-train-2026-11-12/encoding-summary.json)

## 复核方式

发布的 [Linux fixture 程序](../scripts/kali-behavior-fixture-worker-v2-20261112.py) 包含候选配方、临时输入和行为检查。请在一次性 Linux 容器或专用虚拟环境中运行；程序会安装所列版本的 Python 工具，并输出完整 JSON。原测试镜像摘要见冻结清单；实际解析的依赖也受基础镜像与软件仓库影响，重跑应检查实际版本和行为结果。

```bash
python scripts/verify-kali-behavior-train-20261112.py
# 在固定 Linux 验证环境执行：
python scripts/kali-behavior-fixture-worker-v2-20261112.py > /tmp/fixture-result.json
python scripts/verify-kali-behavior-train-20261112.py --runtime-receipt /tmp/fixture-result.json
```

发布核查同时确认：文件 SHA256、源配方与训练题/命令的对应、每条准入记录的正例通过和错例拒绝。该检查已对本轮实际运行回执通过。

## 使用范围

这是下一轮数据干预对照可用的探索性 TRAIN 补充。工具选择受到已暴露 DEV 错误分析的影响，不能用同一 DEV 宣称独立泛化；也不能仅从这 64 条数据推断全部退化已修复。下一轮仍需冻结等预算 SFT 对照和 ABA 候选规则，再用封存数据确认。当前没有新模型分数，E0 仍是正式默认模型。

文档依据：[util-linux 固定版本](https://github.com/util-linux/util-linux/tree/v2.37.2/misc-utils)、[virtualenv CLI](https://virtualenv.pypa.io/en/stable/reference/cli.html)、[dnstwist 固定版本](https://github.com/elceef/dnstwist/tree/20240812)、[PyInstaller 6.10.0](https://pyinstaller.org/en/v6.10.0/man/pyi-makespec.html)。本地版本的执行证据优先于新版网页中的可选参数。
