# Kali 结果复核：计算与抽样复现通过，语义验证仍有边界

2026-10-22 14:55 PDT左右完成，本机Apple M2 Pro；没有占用Nautilus、运行新训练或查询保留确认题/官方TEST。

## 实际执行

1. 重新定位固定文档、重建全部108条输入提示，逐条比对提示哈希和token长度；检查工具名确实由query明确给出，不是额外隐藏工具选择提示。文档辅助输入中没有逐字出现本次编写的参考命令。
2. 将全部108条保存的原始token再次解码，比对响应、EOS计数与截断状态；直接调用固定原生评分器逐条复算，各指标与旧收据一致。这里使用的是同一官方评分实现，不是另一个独立语义判官。
3. 检查原生组失败前保存的24条与恢复后的前24条对象逐项一致，没有借恢复重写结果。
4. 从已暴露开发题中按“原本成功、文档带来改善、仍失败、流式空格差异”分层，以固定哈希排序选8题；生成前冻结计划。每题重放三组，共24次新生成。24/24 token、文本及原生/参数诊断分数与旧记录相同，没有截断。
5. 验证重放期间原始收据、指标、协议和预测文件的哈希均未改变。峰值Metal约5.32GB，整个核验约84秒，模型进程结束。

| 原36道开发题，未改分 | 原生前缀 | 对齐前缀 | 对齐前缀＋帮助文档 |
| --- | ---: | ---: | ---: |
| Native Exact /参数诊断匹配 | 4/36 | 6/36 | 25/36 |
| Native Total | 67.54 | 73.41 | 93.87 |

完整证据：`verification/kali-domain-reverification-2026-10-22/result.json`、`plan-before-replay.json`、`replays.jsonl`。工具为`scripts/verify-kali-domain-results.py`。原108条生成没有整体重跑；新生成仅8题×3组。分层基于已知结果，目的在于诊断复现，不是一个新的随机测试集。

## 来源交叉检查与一个评分边界

另读取并记录了YARA、Wireshark及GNU的主要文档，以及Debian维护的net-tools2.10源码，未执行其中命令：

- [YARA手册](https://yara.readthedocs.io/en/stable/commandline.html)支持规则文件先于待扫描目标的参数顺序，因此本次把二者交换的预测有实际语义问题。
- [Editcap手册](https://www.wireshark.org/docs/man-pages/editcap.html)支持`-r`保留指定包范围、`-s`设快照长度；[Mergecap手册](https://www.wireshark.org/docs/man-pages/mergecap.html)支持`-a`按输入次序连接而不是默认时间排序。这些与所抽查参考意图一致。
- [net-tools2.10源码](https://salsa.debian.org/debian/net-tools/-/blob/upstream/2.10/netstat.c)的长选项表包含`programs`，`program`只有这一项前缀匹配，解析器调用`getopt_long`。[GNU解析器文档](https://sourceware.org/glibc/manual/latest/html_node/Getopt-Long-Options.html)允许唯一长选项缩写。因此，源码静态证据支持该环境语义下`--program`可等价于`--programs`，不应仅因拼写不同就认定模型命令错误。

该条尚未在固定Kali容器中实测，单列`verification/kali-netstat-abbreviation-review-2026-10-22.json`。原生25/36保留，未改scorer、gold或原始预测；不把来源静态推断悄悄计入官方匹配分数。抓取来源与哈希见`verification/kali-domain-primary-semantic-sources-2026-10-22.json`。

## 可以与不可以下的结论

目前可以确认：所保存分数计算一致，抽样24次可逐token复现；在这些已暴露银标开发题上，补充工具文档与较高规范匹配率相伴。这支持下一步构造与开发题隔离的文档驱动训练数据。

仍不能确认：所有48题语义标签都正确、所有未匹配输出都语义错误、同样效果能泛化到全KaliBench、或已找到失败的唯一原因。没有新增训练，因此也没有证明后训练或ABA收益。扩大独立任务覆盖、复核标签及固定Linux环境验证，比继续反复跑相同开发题更有价值。
