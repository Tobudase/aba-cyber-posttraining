# 文档驱动训练任务接口：已打包，实际ABA尚未接通

当前可调用的数据入口是`scripts/prepare-kali-doc-training.py`，训练任务模板在`kali_doc_training_tasks.py`。它们保留工具文档行号与SHA256、来源辅助语义说明、标签结构以及开发集排除证据。输出为`data/benchkit/kali-doc-train-v1/train.jsonl`和`manifest.json`；训练集108行、55个相关模板、25工具，质量为AI复核来源银标。

## 本机已实现的工作流

1. 数据边界审计和源文档检查；开发题的命令、query和选项/位置参数结构不进入新训练，四个保留确认工具包不进入训练。
2. `freeze-kali-doc-experiment.py`在训练前写入一次性协议，包含数据/基线哈希、优化设置、预算和选择规则；已有协议拒绝覆盖。
3. `run-kali-doc-sft.py --phase train`只加载TRAIN正文，执行固定108步LoRA，提交真实adapter及参数变化、损失、保存重载证据。
4. `--phase evaluate --adapter ...`在另一个进程加载adapter，仅查询两个search开发集，核对与E0完全相同的提示哈希。模型输入没有工具帮助文档或参考答案。
5. `analyze-kali-doc-sft.py`零模型调用复算配对结果、检查真实训练与数据完整性、依据预先规则给出保留基线或仅作为初步候选的判断。

这是一轮固定手工SFT。没有让真正ABA做数据生成、训练配置搜索或提交作业，不称ABA结果。来源辅助审查也不称独立专家验证。

## Linux训练worker包

`scripts/package-kali-doc-worker.py`已经生成并自检`artifacts/kali-doc-worker-v1.tar.gz`。包含108条TRAIN、固定模型元数据、现有CUDA训练/CPU缓存脚本、依赖候选、Dockerfile和任务合同。没有开发题、确认题、官方测试题、模型权重或凭证；作者开发题ID扫描结果为0。合同副本：`configs/benchkit/kali-doc-worker-contract.v1.json`。

合同规定CPU预取权重后才调度GPU，实际初次作业只用1张卡，并设时限、记录利用率。不能用基础镜像digest冒充已经构建并验证的训练镜像。当前没有提交GPU作业。

## 评测接口合同

训练worker未来向独立evaluator提交：`candidate_id`、adapter结果目录与训练收据哈希。evaluator返回汇总的领域/retention原生指标、参数值诊断、覆盖率、错误及成本，不返回开发题正文或逐题目标。官方测试永远不用于候选选择。

文件接口和CLI已准备，但实际ABA中的worker挂载隔离、Linux作业提交、结果路径授权以及私有evaluator回调仍需端到端验证。`search_enabled=false`保留，不能仅凭声明就当作已经安全隔离。

## 迁移边界

本机MLX使用affine4/group64、最后4层q/v、rank8、scale2；现有CUDA脚本使用NF4、PEFT rank16/alpha32、所有q/v层。两者不是等价配方。GPU恢复后应先冻结新的GPU协议、建立匹配GPU E0，并验证20步有限smoke，再运行领域实验。Mac成绩不能直接当作CUDA或排行榜复现，Mac adapter也不应直接交给PEFT脚本使用。

公开仓库提供代码和合同；本机worker归档未上传。完整构建需原工作区的受保护数据和审计缓存，实际Linux CUDA和ABA调度尚待验证。
