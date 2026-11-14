# 追加数据与重放对照：实际结果

Operator append-versus-replay diagnosis on exposed DEV;not native ABA or independent validation.

| 组别 | 状态 | strict/128 | native×100 | 格式错误 | 截断 | 保留门槛 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| A15 | COLLECTED | 55 | 77.354 | 0 | 0 | False |
| A16 | COLLECTED | 52 | 74.936 | 0 | 0 | False |
| A17 | COLLECTED | 52 | 75.583 | 0 | 0 | False |
| A18 | FAILED | — | — | — | — | — |

这是保留原始数据后的新增内容与原数据重放对照，两个种子只提供方向诊断，不证明稳定增益。与旧733步结果跨实验比较还混入更新次数和数据顺序变化，不能单独称作删除旧数据的因果效应。所有128题已暴露；没有独立确认或官方成绩，不晋升模型。

[完整汇总](summary.json) · [冻结设计](DESIGN_ZH.md)
