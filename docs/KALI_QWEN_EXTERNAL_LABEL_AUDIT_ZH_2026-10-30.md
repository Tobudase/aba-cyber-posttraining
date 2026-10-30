# 外部候选题参考答案审计（2026-10-30）

## 结论

对先前固定的 36 道 CyBashBench 来源候选题做了逐题 **AI 静态审核**。发现 5 道题的参考命令与题目字面要求明确不匹配，6 道还依赖未说明的环境或解释；其余 25 道仅属“看起来可行”，尚未通过目标版本运行和独立语义审核。仅排除这 5 道题就只剩 **31 道**，低于事先规定的 32 道最低规模。对这 31 道运行原有准入检查，结果仍为 **`NOT_ADMITTED`**，共 63 项阻断：31 项工具版本未核实、31 项独立审核缺失、1 项题量不足。

因此，**这批 36 道题不能按原计划作为冻结的外部验证集**。这个结论针对这次选出的子集，不等于评价整个 CyBashBench。检查过程中没有根据模型预测挑题，也没有运行题目命令或调用模型。既有 Qwen/RedSage 模型选择不变。

## 发现的五种问题

| 公开来源记录 | 问题 | 核对依据 |
| --- | --- | --- |
| `crypto/nl2bash_061` | 题目要 32 个字符；参考做法生成 32 **字节**再编码成 Base64，结果是 44 个字符。 | [OpenSSL rand 手册](https://docs.openssl.org/master/man1/openssl-rand/)；本地标准库长度检查 |
| `forensics/nl2bash_064` | 参考正则会把 `999.999.999.999` 当作 IPv4 地址，无法可靠筛出有效 IP。 | 本地合成字符串正则检查 |
| `forensics/nl2bash_081` | 统计的 tcpdump 字段通常包含端口号，不能直接当作源 IP 计数。 | [tcpdump 官方手册](https://github.com/the-tcpdump-group/tcpdump/blob/master/tcpdump.1.in) |
| `pwn/nl2bash_114` | 题目未给出 core dump 中的模式值；参考命令却使用固定值，无法由此求出该 dump 的偏移。 | [Kali Metasploit 工具帮助](https://www.kali.org/tools/metasploit-framework/) |
| `web/nl2bash_106` | 题目要求漏洞扫描，而 DIRB 是内容扫描器；其文档明确说明它不是漏洞扫描器。 | [Kali DIRB 手册](https://www.kali.org/tools/dirb/) |

## 实验边界与后续

逐题记录和原始题目保存在私人研究目录；公开仓库只放汇总与可公开核对的理由。[机器可读汇总](../results/kali-qwen-external-ai-audit-2026-10-30/summary.json)带有候选文件、审核记录和筛后文件的 SHA-256，可防止后续混淆版本。此次 **人工独立签核 0、工具版本核验 0、模型调用 0、GPU 任务 0、官方 TEST 访问 0**。AI 判断不能冒充独立专家审核。

下一步应寻找质量更稳的独立来源，或建立锁定工具版本、可离线验证的案例集，先冻结题目与评分规则再读取模型输出。外部 shell 命令题集即便通过审核，也只能作为次要迁移/保持能力检查，不能替代 KaliBench 的主领域验证。
