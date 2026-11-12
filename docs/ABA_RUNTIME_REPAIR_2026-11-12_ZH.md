# 原生 ABA 运行通路：已验证环节与剩余步骤

**当前尚未完成一次新的原生 ABA → GPU → 评分 → 交付全流程。** 新增 64 条训练银标已另行冻结并公开。本页记录运行环境和连接问题的实际修复；已完成的检查不能代替完整运行结果。[状态汇总](../results/aba-runtime-repair-2026-11-12/status.json)。

已通过的环节：

- 固定 ABA 源码 `c8bd734cafd5a7cd609efb5f561594bde4107d5b` 在临时 Linux VM 中安装，并使用真实 Conda 环境启动原生沙箱。普通 venv 虽能运行 CLI 和安装检查，但不能满足该版本运行阶段的 Conda 根目录要求。
- NRP 模型适配器在 VM 内部监听 loopback，原生 Setup 已完成真实模型工具调用和基线门槛检查。此前 SSH 反向端口转发失败，因此改用 VM 内部适配器；没有关闭沙箱。
- 在固定源码中复现：`CompleteWorker.run(self)` 不接收业务请求，而 NBTreeSearch 给它传入了字符串。提供[单行补丁](../patches/aba-c8bd734-zero-request-worker.patch)，删除该字符串参数；候选输入仍由其已有构造参数传递。源码 SHA 和原生参数契约检查已通过；错误的字符串请求仍会被原生验证拒绝。未改变评分、沙箱或数据权限。复核脚本为 [check-aba-zero-request-contract-20261112.py](../scripts/check-aba-zero-request-contract-20261112.py)，需在安装好的 ABA Conda 环境中传入 `--aba-root`。
- 一个**独立、未由原生 ABA 发起**的短时 GPU Job 在 RTX 2080 Ti 上完成 32 次真实 CUDA 更新：人工八词模型训练 NLL 为 **2.07944 → 1.45626**，重载差为 0，本机用回收权重复算吻合。Job/ConfigMap 已清理。[独立 GPU 回执](../results/aba-runtime-repair-2026-11-12/separate-gpu-smoke.json) · [训练代码](../scripts/aba-tiny-cuda-worker-20261112.py)。这不是 8B LLM 后训练结果。
- 临时 VM 中的 64 MiB 非稀疏随机文件已回收到本机，SHA256 一致；完成的临时 VM 均清理。这个检查不代表已验证多 GiB 模型断点恢复。

原生重测中，Setup 曾做多余的 sanity training 而触发时间上限；后续禁止 Setup 训练并给出固定基线模板，Setup 与真实基线验证器已通过。V6 随后在 Designer 的四分钟上限处失败，尚未提交 GPU Job。V7 保持一个候选、固定 CUDA 配方和相同评分/保护规则，增加控制器角色的有限预算；其结果仍待验证。过程中另一次部署脚本的换行转义错误也已修正，并在本机执行实际补丁载荷后再部署。

集成测试采用不含集群凭据的 VM 本地文件请求桥接：只有原生 Setup 门槛通过、Worker 已启动，外部桥接才可提交一次固定 GPU Job。每个 Job 限时结束并清理；模型回传后仍由原生评分器和 Finalizer 处理。最终验收还需证明：同一次原生运行触发真实 CUDA 更新、评分与本机复算一致、交付文件与 GPU 模型对应，以及所有资源清理成功。

原生测试使用自编八词合成任务，不使用 KaliBench 官方 TEST 或封存 final64 模型输出。它用于验证工程通路；正式 8B 新数据 SFT 和 ABA 比较尚未开始，E0 仍是 LLM 的默认模型。
