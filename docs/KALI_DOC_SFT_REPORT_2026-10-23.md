# 文档驱动数据与固定后训练对照：已完成，保留原基线

实验跨2026年10月22–23日在本机Apple M2 Pro/16GiB完成。结果没有通过预先冻结的采用标准，因此保留原始RedSage-K-SFT-GRPO权重，不采用本轮adapter。以下是来源银标工程试验，不是官方KaliBench成绩或真实ABA结果。

## 本轮交付

- 48道现有候选题的AI文档辅助复核，逐题保留理由和适用前提；参考答案、分区和原生评分器未修改。它不是独立专家审核或Linux执行验证。完整逐题复核记录留在本机，以保留新确认题；公开训练数据及搜索题证据。
- 新训练集`data/benchkit/kali-doc-train-v1/`：108行、55个相关任务模板、25工具、10工具包。每个模板最多两个具体场景；两个无参数任务的重复变体已去重。数据含文档行号、来源哈希、标签结构与AI语义说明，质量明确为来源银标。
- 数据边界检查：与作者开发/确认题的query和命令精确重叠0，工具＋选项键组＋位置参数数量的结构重叠0；四个保留确认工具包未进入新训练。原生gold-echo全部通过。结构排除不证明完全没有语义相似；工具/工具包与search-dev允许共享，相关文档也可能早已被底座模型见过。
- 训练前冻结一次性协议`configs/kali-doc-sft-v1.protocol.json`，SHA256 `782d1d83668c8e0ea3bfcd3bd8781daedd5c1312a154e11a46edc4407bbe4acc`。
- 完成真实108步LoRA，以及独立进程加载adapter后的36题领域开发和72题retention评测；零确认题/官方TEST推理、零数据命令执行、零Nautilus作业。
- 打包并自检仅含TRAIN的Linux worker及评测接口合同。包不含开发题、确认题、官方TEST、权重或凭证。实际Linux CUDA与ABA调度/私有evaluator尚未运行；详见[Kali文档任务接口](KALI_DOC_ABA_INTERFACE.md)。

## 固定配方与真实训练证据

底座：`RISys-Lab/RedSage-K-SFT-GRPO`，revision `843e2e3096e7de68f5c35eb16238f4909f21695a`，使用已校验官方源权重本机转换的MLX affine4/group64。

配方：从原基线重新初始化，未加载之前20步adapter；学习率1e-5、batch1、shuffle seed42、108个样本各一次。最后4层q/v的LoRA，rank8、MLX scale2、dropout0，AdamW/weight_decay0。原生full-chat、assistant-only final答案监督，没有伪造思维链，训练输入也没有工具帮助文档。最长序列457tokens，没有截断。

16个LoRA tensor、425,984个可训练参数真实更新，保存重载后的探针logits最大差为0。固定同8条训练探针的平均交叉熵约1.268→0.296，证明拟合了这些训练记录，不证明开发泛化。

训练约346.8秒、峰值Metal5.79GB；108条后评测约262.2秒、峰值5.14GB。训练分支没有加载开发题正文，没有开发梯度。所有模型进程均已退出。

## 匹配E0/E1结果

E0复用已完成且校验过的固定基线输出。E1使用同样的ID、逐字相同的提示哈希、同一原生评分器、对齐SFT边界的prefix、greedy/seed42、1,024输出上限。两边均不提供工具帮助文档，因此这次不把文档辅助25/36混入训练收益比较。

| 指标 | E0原模型 | E1新108步adapter |
| --- | ---: | ---: |
| 领域36题：Native Exact /参数值诊断匹配 | 6/36（16.67%） | 5/36（13.89%） |
| 领域Native Total | 73.41 | 76.45 |
| 领域Optional F1 | 37.25 | 43.12 |
| 领域Positional F1 | 82.98 | 88.99 |
| 原能力72题：Exact /参数值诊断匹配 | 66/72（91.67%） | 54/72（75.00%） |
| 原能力Native Total | 97.22 | 89.63 |
| E1完整XML | — | 36/36及72/72 |
| E1运行失败/截断 | — | 0/0 |

领域平均组件分数改善，但完整命令匹配没有改善；不能只挑Total上升来声称实验成功。预定采用规则要求领域Exact/参数诊断严格改善、领域Total不降、retention不降且格式/运行正常。本轮只有后两项中的领域Total和运行格式检查通过，完整采用规则失败。

## 错误与数据覆盖分析

领域完整匹配0题新增成功、1题退化：模型把要求的`pescan`改成了`pe-scan`，不符合查询中指定的工具名称。是否存在别名也不能直接当作此处已验证；固定来源仅提供`pescan`。

retention的12个新增规范匹配失败集中在两个tshark模板族（DNS/TLS各6个相关文件名变体），不是12种独立能力。所有新增命令带`-q`，其中两条还增加了`sudo`。按照[官方TShark手册](https://www.wireshark.org/docs/man-pages/tshark.html)，读文件时`-q`会抑制包信息，和这两类“显示匹配数据包”的请求有实际冲突。因此不能把这些退化全归因于评分器仅接受一种写法；但这里也没有进行Linux运行验证。

新的TRAIN覆盖了18种领域开发工具中的16种，但34/36道开发题仍有该工具的必需选项组没有在新TRAIN里直接出现。刻意隔离整个操作结构保留了新的任务组合，也使很多具体API映射没有被直接教授。另两条“选项组全覆盖”中，一条本来无选项，不能把它当成完整知识覆盖。见`flag-coverage.json`。

因此，可确认的是训练集拟合改善、这份开发集上的完整匹配及两类retention表现下降。覆盖不足、数据规模小、未加入独立通用能力回放，都是下一轮可检验的原因假设；本次没有相应消融，不能断言已证实唯一原因或整体模型灾难性遗忘。

## 固定决策与下一轮设计建议

本轮不追加候选追分，不用确认题筛选，不改gold/scorer。原基线继续作为工作模型；本轮adapter只保留为负结果证据，不部署、不自动发布权重。

下一轮应先从完整工具文档系统覆盖参数知识，设计与当前题目不同的任务组合和场景，而不是复制开发答案；加入从独立来源取得的通用能力回放，或单独检验保留约束。先冻结新的数据与实验协议，再比较受控候选。不能把更多GPU本身视为解决数据覆盖问题的证据。

独立专家标签复核、终端语义验证、更广的开发覆盖、实际ABA配置搜索/数据生成、Linux GPU实验和最后单独冻结的官方评测都仍未完成。

## 可复算与成果位置

- 新训练数据：`data/benchkit/kali-doc-train-v1/train.jsonl`；清单SHA256 `a12e73d621a88a6d4c82f8e8e4fb5e3bdf5ce3491bfde8e0d9c383ffbe317cde`。
- 原始训练、adapter与后评测：`docs/verification/kali-doc-sft-v1-2026-10-22/`。adapter仅本机保留，portable源码包不携带模型tensor。
- 对照、逐题变化和决策：`comparison.json`。零模型调用复算：`python3 scripts/verify-kali-public-results.py`（公开证据评分复算；不重新训练或验证未发布的adapter tensor）。
- 数据检查：`scripts/prepare-kali-doc-training.py`；冻结：`freeze-kali-doc-experiment.py`（已有协议拒绝覆盖）；执行：`run-kali-doc-sft.py`。
- 原工作区37项测试通过；公开仓库另附10项提示、解码和边界测试。worker训练树独立导入、自校验和开发ID排除检查通过。
- 正式测试题未用于生成、训练或选参。作者确认题仅被边界审计器用于静态排除，没有模型推理或评分。本报告和选定证据现已整理为公开发布；新12题确认集、模型和adapter tensor、凭证及私人通信不在发布范围。

## Public reproduction scope

See [reproduction instructions](REPRODUCTION.md). The public verifier recomputes scores from saved predictions and verifies frozen input/evidence hashes. It does not independently repeat optimization, decode model tokens, verify unpublished tensors, or rerun the original 37-test private suite. Historical training/data-builder scripts are preserved as executed source; they require local protected data, pinned model/tokenizer caches and/or unpublished adapter files. They deliberately retain these guards. The train-only worker contract is preparation, not a completed CUDA or ABA experiment.
