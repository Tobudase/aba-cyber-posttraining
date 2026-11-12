# KaliBench P10：训练标签核查后取消作业

P09 的 749 步 source-silver 扩充试验一直未获得 A100 调度，队列超时后失败：没有 GPU 训练、模型输出或分数。为排除 P09 同时增加数据和步数的混杂，P10 预先冻结了更严格的对照：从 P07 的 733 条发布方已验证 TRAIN 记录中替换 14 条，加入 14 条 AI 编写的 source-silver 题；总记录数、更新步数和监督目标 token 总数均与 P07 相同。P10 是**操作员设计的机制对照**，不是 ABA 自动选中的模型。已暴露的 TRAIN 来源 DEV128 只计划用于诊断；官方 TEST 和封存 final64 均未查询。

P10 的单 A100、普通优先级、有时限 Job 提交后仍处于 `Pending`，尚未分配节点。我同时在独立的短时 CPU Job 中，用临时目录和允许的无副作用命令逐条核查 14 条标签，并确认测试文件未改变。结果仅 **8/14 在该 Linux 镜像返回 0**：`lsblk` 4/4、`lsmem` 2/2、`hardlink --exclude` 2/2；`hardlink --cache-size` 2/2 被报告为不认识的选项，`more --exit-on-eof` 4/4 也被报告为不认识的选项。第二次诊断复现同样结果，两个 CPU Job 的资源均已清理。

[util-linux 的当前 hardlink 手册](https://github.com/util-linux/util-linux/blob/master/misc-utils/hardlink.1.adoc)和[当前 more 手册](https://man7.org/linux/man-pages/man1/more.1.html)列出了相应选项。因此此发现说明**本次运行镜像与文档／先前代表性 VM 检查存在版本差异**，不能证明所有 Linux 版本都不接受这些命令。但它已经使“14 条均通过目标运行环境核查”的数据准入条件不成立；逐条退出成功也不能证明自然语言题目的唯一正确答案。

我在 GPU 调度前取消 P10，删除 Job 与输入对象。最后一次 Pod 检查为未调度，训练步数和模型输出均为 **0**；个人残留 Job/Pod/ConfigMap/Secret 为 **0**，A100 quota 使用量恢复到 **0**。P10 没有训练结果，也不能和 P07/P08 比较模型分数或宣称新数据收益。原始 E0 模型仍为正式默认，官方 TEST 使用 0 条。

**下一道门槛：** 先锁定目标工具版本，在同一环境对新训练标签逐条执行并核对任务语义；未通过者隔离。其后再冻结真实 ABA 候选与同预算对照，交由原生 ABA Worker 提交、评分和选择，并用封存确认集检验。不能把本次取消记作 ABA 后训练成功。

[去标识化核查汇总](../results/kali-p10-label-qa-2026-11-11/summary.json)。公开文件不含训练题文本、模型输出或访问凭证。
