# P09 冻结后 Linux 工具核验补记

P09 已按 [预先冻结协议](KALI_P09_MIXED_SILVER_PREP_ZH_2026-11-11.md)提交，以下检查**发生在数据和训练协议冻结后**，没有修改训练载荷、标签或评分规则。隔离的 Nautilus 研究 VM 已在检查后停止。

VM 中安装了 `lsblk`、`lsmem`、`hardlink`、`more`；这四个工具的实际 `--help` 均包含新数据使用的选项。每个操作类选择一个代表性命令执行：`lsblk --pairs --exclude 8`、`lsblk --perms --width 100`、`lsmem --pairs --split STATE`、两个 `hardlink --dry-run` 变体，以及两个 `more` 显示变体，均返回退出码 0。`hardlink` 与 `more` 使用临时目录和文件；检查前后的文件内容、inode 和链接数相同。

这只验证 **7 个操作类的代表性实例**及其选项在该 VM 上可运行，没有逐字执行 14 条相关训练题，也没有核实每个自然语言问题的唯一正确答案。`virtualenv` 未安装，因此其 2 条训练题仍只有固定帮助文本和原生评分器回显检查。P09 的 16 条仍标记为 source-silver，未获得发布方或独立专家金标；本补记不把操作员训练变成 ABA 选择，也不构成独立模型评测。
