# hardlink dry-run 验收器 v6 修复与统一复核

已在util-linux 2.37.2 Linux环境完成修复验证，并统一复核1,536条保存输出。没有新模型调用或训练；CPU作业和专用NetworkPolicy已清理。

原判定只要求退出成功、文件未改变。v6进一步要求实际dry-run输出明确的dry-run模式及预期链接数量，并在另一份临时环境中将同一argv仅移除显式 `-n` / `--dry-run`，检查它提出的真实链接分组。其余工具、选项、值和目标路径不作纠正。原始运行必须不修改任何文件；shadow执行只用于验收，不代表模型实际进行了真实链接。

验收的六项Linux回归控制均通过：长/短dry-run正例；拒绝过滤全部文件、错误目标文件、错误basename限制和真实修改命令。五项本机单元测试覆盖空预览、错误计数、修改文件、错误模式、保持错误参数及错误分组。预期有重复文件的fixture不能再以空输出返回成功。

参考：util-linux固定版本[hardlink.c](https://github.com/util-linux/util-linux/blob/v2.37.2/misc-utils/hardlink.c)。当前规则适用于固定版本和这些fixture，不声称支持所有hardlink实现或所有组合。

历史主实验E0、F22、R/RK/RKstrong的八组输出在v5→v6之间没有逐题改判。这个修复补强了验收条件，没有人为改出更好的分数。更早F24的v3/v4历史分数继续保留；新版有限选项接纳规则不同，跨版本计数不能仅归因于dry-run修复。

[核验汇总](summary.json) · [独立验收模块](../../scripts/kali_hardlink_oracle_v6_20261115.py) · [单元测试](../../tests/test_kali_hardlink_oracle_v6_20261115.py)

```bash
python3 -m unittest discover -s tests -p test_kali_hardlink_oracle_v6_20261115.py
```

下一项两模型SFT对照已准备：原始RedSage-K-SFT-GRPO与原始Qwen3-8B，各256次更新，同一批新TRAIN128+旧TRAIN128、同样样本顺序。RedSage沿用已声明的BPE格式干预，Qwen使用官方非思考模板；所以是模型与各自训练配方的比较，不能将全部差异归因于权重本身。没有加载F22作为候选起点。官方TEST与此前final64不重新查询；本轮只用已暴露开发面板，不进行模型晋升。

本次发布时两模型训练尚未开始：控制器等待另一个会话已有GPU任务结束，防止重复占用资源。[冻结协议及状态](../kali-two-model-sft-2026-11-15/status.json)。最终结果只能在实际训练、评分、权重导出与核验后补充。
