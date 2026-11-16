# 原始 Qwen3-8B 原生 ABA 对照：复核入口

完整结果、两张结果图及限制见 [结果报告](../results/kali-qwen-native-aba-2026-11-15/RESULT_ZH.md)，机器可读记录见 [summary.json](../results/kali-qwen-native-aba-2026-11-15/summary.json)。这是内部开发与组合保留集实验，官方 TEST 未使用。

## 这轮实际比较什么

- 原始 Qwen/Qwen3-8B，固定修订 `b968826d9c46dd6066d109eabc6255188de91218`。
- 已完成的固定 SFT256，适配器 SHA256 `9bce6a5511642b4f45762ed7ee7032aa52d96db233a8c4008e5700fddaf91c93`；这轮复用权重并重新评测，没有算作新训练。
- 原生 ABA 选择两种不同学习率，A1=`1e-5`、A2=`3e-5`；各从原始权重新训练128步，共256步及31,100个目标token，和固定SFT的总目标token曝光量一致。两次初始化与一次4epoch训练并不等于端到端算力严格匹配。
- 当前所有评测和ABA训练使用单张A10、顺序运行。固定SFT在上轮RTX3090上训练；本轮并非四种模型同一训练硬件的因果消融。

新DEV46覆盖9工具、26组；旧64题同时报告原生部分分、严格匹配、历史13道与本次E0的14道答对题保留。新题组效用仅计有限验收器确认通过，UNKNOWN保持未决，不解释成语义错误。全部三份适配器都有一条截断；A1虽通过旧题保持门槛，仍未通过整体准入。原生树选中A1（惩罚分−102），主机保留原始Qwen；惩罚分高于另一份不合格模型不构成性能改善。

完整四模型保留集范围在读取任何保留题之前锁定：384题、197组、8工具，各模型一次；不根据结果再选模型。保留集共享作者、生成器和基本技能，PyInstaller和clang-format合计约80.2%，不能当作外部专家测试或全KaliBench榜单。额外32条已曝光DEV响应仅用于guard开启/关闭诊断。

## 代码入口

|用途|入口|
|---|---|
|冻结扩展数据、协议|`scripts/prepare_kali_qwen_aba_validation_20261115.py`|
|旧题保持与选择分|`scripts/kali_qwen_aba_grade_20261115.py`|
|单卡真实训练/推理后端|`scripts/kali_qwen_aba_worker_20261115.py`、`kali_qwen_aba_jobs_20261115.py`|
|实际原生ABA任务/驱动|`scripts/build_kali_qwen_native_20261115.py`、`run_kali_qwen_native_20261115.py`|
|原生Worker校验后GPU派发|`scripts/kali_qwen_native_bridge_20261115.py`|
|冻结V8验收|`scripts/kali_qwen_validation_behavior_v8_20261115.py`|
|选型后完整配置V9复核|`scripts/kali_qwen_supplement_behavior_v9_20261115.py`、`kali_qwen_full_style_oracle_20261115.py`|
|保留集先验证、后评测|`scripts/kali_qwen_confirmation_20261115.py`|
|权重恢复/结果复算|`scripts/export_kali_qwen_aba_20261115.py`、`finalize_kali_qwen_aba_20261115.py`|
|确认报告与第二张图|`scripts/add_kali_qwen_confirmation_report_20261115.py`|

框架固定到 `aibuildai-inc/aibuildai-llm-posttrain-agent@c8bd734cafd5a7cd609efb5f561594bde4107d5b`，保留其原生验证、审查和沙箱。已有一处已记录的零参数Composite调用兼容修复；没有关闭守卫。原生运行ID `d3606cecd35a4bc69aac42bd321cbf85`，两候选都有原生Worker活跃时的派发记录、实际更新、完整权重恢复与重载相同输出证据。没有把手工训练循环或缓存权重标成新ABA训练。

## 本地复核与重现条件

脚本需要私有冻结输入、原始GPU回执、真实journal及适配器。公开仓库保留代码和聚合证据，不重新分发发布方训练行、开发/保留题目与标签、完整模型输出、令牌或模型权重。缺少这些私有输入时，不能声称仅克隆仓库就能复算全部分数。 `kali_data_release_20261114.py`与`kali_functional_data_20261115.py`公开副本仅提取验收运行函数，函数AST与实际执行版一致，但省略受保护任务生成器，整个模块字节哈希不同；历史CPU源码哈希复核仍须这两份原私有模块。两份补齐的旧验收依赖保持原字节。详见[依赖审计](../results/kali-qwen-native-aba-2026-11-15/dependency-audit.json)。公开验收函数、输入哈希与依赖版本可供新的版本化研究参考；它们不能重建私有保留集。

在保留了原工作区的主机，可先运行纯CPU回归检查：

```bash
python3 -m unittest discover -s tests -p 'test_kali_qwen*.py'
```

测试覆盖保持门槛、UNKNOWN计分、截断、组宏平均、危险路径/协议拒绝、多合格节点保留、完整clang配置，以及下一版客户端等待截止边界，共16项。测试不调用模型、不提交GPU。

有私有运行材料时，`finalize_kali_qwen_aba_20261115.py`会重新计算本轮全部开发分数，核对256条实际更新、相同数据/模型/模块哈希、旧固定训练曝光量、两适配器导出SHA、重载输出、原生Finalizer四文件一致与VM清理，之后才生成主图。`add_kali_qwen_confirmation_report_20261115.py`再补充V9复核、保留集和解码诊断，并再次要求选型SHA不变。

运行驱动会创建自己的有限寿命CPU VM和普通批处理Job，只能用于新的、明确分离的研究目录。不要对已有的活动研究再次启动驱动。`--resume-pre-native`仅用于原生任务尚未创建时重新连接安装VM；真实原生搜索启动后不能用它重开研究。安装脚本中的磁盘格式化仅适用于驱动新建VM的临时空盘，不应在已有服务器独立运行。

## 执行勘误及下一版修复

冻结Task README残留RTX3090字样，真实资源修订和CUDA回执都是A10。该文本勘误另行披露，没有回填已经冻结和验收的任务文件。

当前研究实际使用v1客户端。它在等待截止附近可能因剩余1秒的RPC超时抛异常，原生Worker通过再次查询恢复，没有重复提交训练。保留v1字节供当前运行复核；另附 `kali_qwen_aba_client_v2_20261115.py`，使零秒查询使用正常30秒RPC，并在截止时返回已观察到的IN_PROGRESS，而不虚构完成。四项边界回归检查通过。v2尚未替换本次冻结Task，也没有据此重跑模型；下一版任务封装应明确选用它。
