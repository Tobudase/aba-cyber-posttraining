# 技术报告索引

[中文项目导览](README.md) · [按研究问题查结果](../results/README.md) · [按时间查实验](../EXPERIMENT_LOG.md)

本页列出 docs 目录里的独立报告。最新教师实验的报告与逐次评分放在同一结果目录，可直接阅读[教师轨迹研究](../results/teacher-transfer-2026-11-23/RESULT_ZH.md)。同一实验的中英文版本各自保留。

<details>
<summary>导航、复算与状态快照（3）</summary>

- [Project status on November 2, 2026](STATUS.md)
- [October 2026 reproduction notes](REPRODUCTION_OCTOBER.md)
- [Reproduce the published scores](REPRODUCTION.md)

</details>

<details>
<summary>11 月 12 日起 · ABA 对照与评分复核（8）</summary>

- [原始 Qwen3-8B 原生 ABA 对照：复核入口](KALI_QWEN_NATIVE_ABA_2026-11-15_ZH.md)
- [KaliBench 开发实验与合理性审查（2026-11-15）](KALI_EXPERIMENT_REVIEW_2026-11-15_ZH.md)
- [新数据、固定 SFT 与原生 ABA 的 8B 比较](KALI_VERIFIED64_8B_STUDY_2026-11-12_ZH.md)
- [8B验证数据与受限原生ABA：完整实验结果](KALI_VERIFIED64_8B_RESULT_2026-11-12_ZH.md)
- [KaliBench：剩余训练数据覆盖核查](KALI_PUBLISHER_REMAINDER_AUDIT_2026-11-12_ZH.md)
- [KaliBench P10：训练标签的进一步核验](KALI_P10_SEMANTIC_QA_2026-11-12_ZH.md)
- [KaliBench：可执行核验的新增训练数据](KALI_BEHAVIOR_TRAIN_2026-11-12_ZH.md)
- [原生 ABA → GPU → 评分 → 交付：合成任务验收通过](ABA_RUNTIME_REPAIR_2026-11-12_ZH.md)

</details>

<details>
<summary>11 月 1–11 日 · 候选模型、复现和数据审核（35）</summary>

- [KaliBench 反复退化：选项写法、解析规则与监督覆盖的验证](KALI_SFT_SYNTAX_ROOT_CAUSE_ZH_2026-11-11.md)
- [KaliBench P10：训练标签核查后取消作业](KALI_P10_LABEL_QA_ABORT_ZH_2026-11-11.md)
- [KaliBench P09：定向 source-silver 数据的受控训练准备](KALI_P09_MIXED_SILVER_PREP_ZH_2026-11-11.md)
- [P09 冻结后 Linux 工具核验补记](KALI_P09_LINUX_TOOL_CHECK_ZH_2026-11-11.md)
- [KaliBench P08：P07 同配置复现的结果](KALI_P08_EXACT_REPLICA_RESULT_ZH_2026-11-11.md)
- [P08：P07 同数据同配置复现，运行前记录](KALI_P08_EXACT_REPLICA_PREP_ZH_2026-11-11.md)
- [KaliBench P07：扩大已验证 TRAIN 覆盖后的探索性结果](KALI_P07_COVERAGE_RESULT_ZH_2026-11-11.md)
- [P07 数据覆盖对照：运行前冻结记录](KALI_P07_COVERAGE_CONTROL_PREP_ZH_2026-11-11.md)
- [KaliBench 原生 ABA P05：训练完成，开发集门槛未通过（2026-11-11）](KALI_ABA_PUBLISHER_P05_2026-11-11_ZH.md)
- [KaliBench P06：换预设 seed 后仍未通过开发集门槛](KALI_ABA_P06_SEED_CONTROL_ZH_2026-11-11.md)
- [KaliBench P05 退化诊断：哪些原因已证实，哪些仍是假设](KALI_ABA_P05_CAUSE_AUDIT_ZH_2026-11-11.md)
- [ABA controller environment recovery — November 11, 2026](ABA_CONTROLLER_RECOVERY_2026-11-11.md)
- [RedSage-K：638 条发布方 TRAIN SFT 结果](KALI_REDSAGE_PUBLISHER_SFT638_RESULT_ZH_2026-11-10.md)
- [RedSage-K：KaliBench 发布方 TRAIN 内部留出结果](KALI_REDSAGE_PUBLISHER_HOLDOUT_RESULT_ZH_2026-11-10.md)
- [RedSage-K：KaliBench 发布方 TRAIN 内部留出实验准备](KALI_REDSAGE_PUBLISHER_HOLDOUT_PREP_ZH_2026-11-10.md)
- [RedSage-K：第二组发布方 TRAIN 内部确认结果](KALI_REDSAGE_PUBLISHER_CONFIRM64_RESULT_ZH_2026-11-10.md)
- [KaliBench P02 输出退化排查（2026-11-10）](KALI_P02_COLLAPSE_CAUSE_AUDIT_ZH_2026-11-10.md)
- [KaliBench P02：Agent 提交的后训练候选及失败门控](KALI_ABA_PUBLISHER_P02_2026-11-10_ZH.md)
- [KaliBench 出版方 TRAIN：P01 候选失败记录](KALI_ABA_PUBLISHER_P01_2026-11-10_ZH.md)
- [C13 逐题变化审计（2026-11-10）](KALI_ABA_C13_PAIRED_AUDIT_ZH_2026-11-10.md)
- [KaliBench 原生 ABA 重试：接口恢复，候选等待 GPU 超时](KALI_NATIVE_ABA_ASYNC_ATTEMPT_2026-11-09_ZH.md)
- [KaliBench ABA 多候选搜索：两配方试跑与控制器阻塞](KALI_ABA_SEARCH_SMOKE_2026-11-09_ZH.md)
- [KaliBench ABA 后续：复核时限与 GPU 调度](KALI_ABA_RESOURCE_AND_REVIEW_FOLLOWUP_2026-11-09_ZH.md)
- [KaliBench C13 后训练与开发集评分（2026-11-09）](KALI_ABA_C13_RESULT_ZH_2026-11-09.md)
- [原生 ABA 数据的同家族新文件名诊断：严格评分与 Linux 实际行为（2026-11-02）](KALI_QWEN_NATIVE_INFAMILY16_DIAGNOSTIC_ZH_2026-11-02.md)
- [原生 ABA 新任务数据 → Qwen3-8B SFT 对照：完整工程循环（2026-11-02）](KALI_QWEN_NATIVE_ABA652_RESULT_ZH_2026-11-02.md)
- [Qwen3-8B：外部来源 26 题命令诊断（2026-11-02）](KALI_QWEN_EXTERNAL26_AI_DIAGNOSTIC_ZH_2026-11-02.md)
- [Qwen3-8B：托管模型改写训练数据的 680 步对照试验（2026-11-02）](KALI_QWEN_AGENT_DATA680_ZH_2026-11-02.md)
- [KaliBench 训练侧：原生 ABA 生成新操作任务的小规模试验（2026-11-02）](KALI_NATIVE_ABA_NOVEL_DATA_PILOT_ZH_2026-11-02.md)
- [KaliBench ABA 训练失效排查与下一轮准入（2026-11-02）](KALI_ABA_RECOVERY_AUDIT_ZH_2026-11-02.md)
- [KaliBench 训练工具覆盖与外部数据来源核查（2026-11-01）](KALI_TRAIN_COVERAGE_AND_SOURCE_SURVEY_ZH_2026-11-01.md)
- [KaliBench Qwen3-8B：734 步等步数数据试验结果（2026-11-01）](KALI_QWEN_DIVERSE_734_RESULT_ZH_2026-11-01.md)
- [KaliBench Qwen3-8B：训练数据质量与 734 步剂量试验（2026-11-01）](KALI_QWEN_DATA_QUALITY_DOSE_ZH_2026-11-01.md)
- [KaliBench 外部候选题逐题复核进展（2026-11-01）](KALI_EXTERNAL_CYBASH_REVIEW_V3_ZH_2026-11-01.md)
- [CyBashBench：AI 辅助检验分支（2026-11-01）](KALI_CYBASH_AI_ONLY_DIAGNOSTIC_ZH_2026-11-01.md)

</details>

<details>
<summary>10 月 27–31 日 · Qwen 基线、开发集与旧能力保持（23）</summary>

- [Qwen3-8B 扩展 SFT 后的通用命令能力检查](KALI_QWEN_UTILITY_RETENTION_ZH_2026-10-31.md)
- [Qwen3-8B 定向回放数据的 650 步对照实验](KALI_QWEN_TARGETED_REPLAY_650_ZH_2026-10-31.md)
- [KaliBench 后训练：外部验证集下一步准备（2026-10-31）](KALI_EXTERNAL_VALIDATION_GATE_ZH_2026-10-31.md)
- [KaliBench 外部验证候选：32 题复核清单（仍未获准）](KALI_EXTERNAL_REVIEW_V2_ZH_2026-10-31.md)
- [外部候选题参考答案审计（2026-10-30）](KALI_QWEN_EXTERNAL_LABEL_AUDIT_ZH_2026-10-30.md)
- [Qwen3-8B 扩展训练：数据已冻结，GPU 尚未分配（2026-10-30）](KALI_QWEN_EXPANDED_TRAIN_PREP_ZH_2026-10-30.md)
- [Qwen3-8B 扩展 SFT：A40 完成，内部 DEV64 小幅提升](KALI_QWEN_EXPANDED_A40_RESULT_ZH_2026-10-30.md)
- [KaliBench Qwen3-8B：训练数据回执复核与探索性筛选（2026-10-29）](KALI_QWEN_RECEIPT_SCREEN_ZH_2026-10-29.md)
- [KaliBench Qwen：下一轮数据复核与外部验证准入准备（2026-10-29）](KALI_QWEN_NEXT_GATE_ZH_2026-10-29.md)
- [KaliBench Qwen3-8B：AI 资料复核与有限 SFT 验证（2026-10-29）](KALI_QWEN_AI_REVIEW_ZH_2026-10-29.md)
- [KaliBench 新任务质量门槛复核（2026-10-28 Pacific）](KALI_TASK_QUALITY_GATE_ZH_2026-10-28.md)
- [KaliBench：面向薄弱操作的下一批数据候选（2026-10-28 Pacific）](KALI_TARGETED_INTAKE_ZH_2026-10-28.md)
- [KaliBench 是否换第二款模型复跑（2026-10-28）](KALI_SECOND_BASE_DECISION_ZH_2026-10-28.md)
- [KaliBench Qwen3-8B：未查询内部开发题复测（2026-10-28）](KALI_QWEN_UNQUERIED_CONFIRMATION_ZH_2026-10-28.md)
- [KaliBench Qwen3-8B：512 条 SFT 训练数据静态审计（2026-10-28）](KALI_QWEN_TRAIN512_DATA_AUDIT_ZH_2026-10-28.md)
- [Qwen3-8B 第二底座：TRAIN 编码与审核准备（2026-10-28）](KALI_QWEN_SECOND_BASE_PREP_ZH_2026-10-28.md)
- [KaliBench 官方 TRAIN：Qwen3-8B 高置信度试点（2026-10-28）](KALI_QWEN_OFFICIAL_TRAIN_PILOT_ZH_2026-10-28.md)
- [KaliBench 官方 TRAIN 内部开发试点：Qwen3-8B SFT 结果（2026-10-28）](KALI_QWEN_OFFICIAL_SFT_RESULT_ZH_2026-10-28.md)
- [KaliBench Qwen3-8B 下一轮实验协议草案（待数据与人工复核）](KALI_QWEN_NEXT_EXPERIMENT_PROTOCOL_DRAFT_ZH_2026-10-28.md)
- [KaliBench 下一批任务：NRP 模型候选生成与初审（2026-10-28 Pacific）](KALI_MODEL_PROPOSAL_PILOT_ZH_2026-10-28.md)
- [KaliBench：外部来源通用命令保持题候选审核（2026-10-28）](KALI_EXTERNAL_UTILITY_INTAKE_ZH_2026-10-28.md)
- [KaliBench 确认评测事后审计与下一轮数据方案（2026-10-27 Pacific）](KALI_POSTHOC_AUDIT_AND_NEXT_DATA_ZH_2026-10-27.md)
- [KaliBench 下一批数据：离线任务验收试点（2026-10-27 Pacific）](KALI_NEXT_DATA_PILOT_ZH_2026-10-27.md)

</details>

<details>
<summary>10 月 26 日及以前 · 训练试点与输出格式（26）</summary>

- [SFT分步执行：训练题诊断、数据验证与门槛（2026-10-26）](KALI_SFT_PROGRESS_ZH_2026-10-26.md)
- [Stepwise SFT progress — 2026-10-26](KALI_SFT_PROGRESS_2026-10-26.md)
- [KaliBench 当前结果图解（截至 2026-10-26）](KALI_RESULTS_FIGURES_ZH_2026-10-26.md)
- [关键前缀诊断与修复对照（2026-10-26后续）](KALI_PREFIX_FOLLOWUP_ZH_2026-10-26.md)
- [关键前缀训练对照的实际结果（2026-10-26）](KALI_PREFIX_CONTROL_RESULT_ZH_2026-10-26.md)
- [训练与推理精度对照（2026-10-26）](KALI_MATCHED_PRECISION_ZH_2026-10-26.md)
- [固定 SFT adapter 的确认评测（2026-10-26 Pacific）](KALI_BF16_CONFIRMATION_ZH_2026-10-26.md)
- [240 条数据的 BF16 SFT 开发实验（2026-10-26）](KALI_BF16_240_SFT_ZH_2026-10-26.md)
- [新种子复现与新迁移检查（2026-10-25）](KALI_SEED43_REPLICATION_ZH_2026-10-25.md)
- [Paired seed replication and frozen transfer check — October25,2026](KALI_SEED43_REPLICATION_2026-10-25.md)
- [原生推理协议与42步ABA试验（2026-10-25）](KALI_NATIVE_FAMILY_PILOT_ZH_2026-10-25.md)
- [Native-protocol KaliBench pilot — October 25, 2026](KALI_NATIVE_FAMILY_PILOT_2026-10-25.md)
- [KaliBench：无收益诊断与修正，2026-10-25](KALI_LEARNING_DIAGNOSIS_ZH_2026-10-25.md)
- [Kali learning diagnostic and corrections — 2026-10-25](KALI_LEARNING_DIAGNOSIS_2026-10-25.md)
- [根因验证与修复候选（2026-10-25）](KALI_CAUSAL_FINDINGS_ZH_2026-10-25.md)
- [KaliBench causal investigation and recovery — October 25, 2026](KALI_CAUSAL_FINDINGS_2026-10-25.md)
- [V3：工具相关回放数据对照结果](KALI_REPLAY_V3_RESULT_2026-10-24.md)
- [V3 public numerical release — 2026-10-24](KALI_REPLAY_V3_PUBLICATION_2026-10-24.md)
- [October 24: completed KaliBench CUDA / native ABA experiment](KALI_CUDA_PUBLICATION_2026-10-24.md)
- [KaliBench 8B 后训练工程验证结果](KALIBENCH_CUDA_POSTTRAIN_REPORT_2026-10-24.md)
- [Team update draft — not sent](KALI_TEAM_UPDATE_DRAFT_2026-10-23.md)
- [Resource validation — October 23, 2026](KALI_RESOURCE_VALIDATION_2026-10-23.md)
- [KaliBench second-round ablation and Linux validation — October 23, 2026](KALI_REPLAY_ABLATION_REPORT_2026-10-23.md)
- [文档驱动数据与固定后训练对照：已完成，保留原基线](KALI_DOC_SFT_REPORT_2026-10-23.md)
- [CUDA baseline and native ABA preparation — October 23, 2026](KALI_CUDA_ABA_PREPARATION_2026-10-23.md)
- [Kali 结果复核：计算与抽样复现通过，语义验证仍有边界](KALI_RESULT_RECHECK_2026-10-22.md)

</details>

<details>
<summary>早期基准、数据来源与运行环境（10）</summary>

- [SEC-bench patch × Gemma 4 31B: alternative pair under review](SEC_BENCH_ALTERNATIVE.md)
- [KaliBench: real local 8B baseline / continued-SFT cycle](KALI_MLX_PILOT.md)
- [文档驱动训练任务接口：已打包，实际ABA尚未接通](KALI_DOC_ABA_INTERFACE.md)
- [Feyospace-v1.1-small candidate preparation (2026-10-16)](FEYOSPACE_MODEL_PREPARATION.md)
- [Feyospace-v1.1-small full-weight engineering check](FEYOSPACE_GPU_VALIDATION.md)
- [External training data review (2026-10-16)](EXTERNAL_DATA_REVIEW.md)
- [CyberForge 85 条可映射候选：上游源代码许可初筛](CYBERFORGE_UPSTREAM_LICENSE_REVIEW.md)
- [CTI-RCM preparation and evidence](CTI_RCM_PROGRESS.md)
- [AthenaBench / KaliBench preparation — October 21, 2026](ATHENA_KALI_PROGRESS.md)
- [ABA 控制模型 × NRP `/anthropic` 接口：实测与下一道门槛](ABA_NRP_COMPAT.md)

</details>
