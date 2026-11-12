# KaliBench P10：训练标签的进一步核验

在此前 16 条自编 source-silver TRAIN 候选中，已有 14 条接受过一次限时 Linux 执行检查。本轮用固定镜像再运行一个普通优先级、**无 GPU** 的短时 CPU Job，记录工具版本，并对 `hardlink` 排除规则增加了安全的重复文件夹具。检查后 Job 与 ConfigMap 均已删除；没有训练模型、查询 DEV/final64 或使用官方 TEST。

目标镜像里的 `lsblk`、`lsmem`、`hardlink`、`more` 属于 util-linux **2.37.2**；`virtualenv` 不存在。`hardlink --dry-run --exclude` 的两条候选在含重复文件、`.bak` 和 `.tmp` 文件的临时目录中返回 0。增加 `--verbose` 观察输出时，被排除的文件没有出现在拟链接列表，其他重复文件被列出，检查前后的文件内容、inode 和链接数一致。这两条被归为**本地运行环境夹具验证的银标**，仅可用于探索性训练；它们同属一个题型，远不足以独立支持一次有意义的 GPU 对照实验。[去标识化统计](../results/kali-p10-semantic-qa-2026-11-12/summary.json)。

其余 **14/16 继续隔离**：两条 `lsblk --exclude` 的题意没有说明该选项只过滤顶层设备，存在范围歧义；四条 `lsblk`/`lsmem` 虽符合手册且运行成功，但现有设备或内存拓扑未证明所要求的显示与分组行为；四条命令的选项被固定版本拒绝；两条 `more` 同时有选项版本和题意错配；两条 `virtualenv` 未在目标镜像中执行。运行成功本身不等于语义正确，发布方的 `PASS_EXECUTED` 也只证明退出码为 0。

下一步的数据准入条件是：锁定工具版本，给每条标签记录手册依据、执行结果和可判定的行为夹具；对无法做行为测试的系统状态类命令保留限制说明。新数据须覆盖多个工具和独立意图组，不复制已暴露 DEV 的题目或答案。达到足够多样性后，才冻结等预算 SFT 对照及原生 ABA 候选；当前 E0 默认决定和此前所有评分均未改变。

手册依据：[lsblk](https://man7.org/linux/man-pages/man8/lsblk.8.html)、[lsmem](https://man7.org/linux/man-pages/man1/lsmem.1.html)、[hardlink](https://github.com/util-linux/util-linux/blob/master/misc-utils/hardlink.1.adoc)、[more](https://man7.org/linux/man-pages/man1/more.1.html)、[virtualenv](https://virtualenv.pypa.io/en/stable/reference/cli.html)。其中部分在线手册描述更新版本的行为，因此不能替代固定镜像上的实测。
