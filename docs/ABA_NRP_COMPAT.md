# ABA 控制模型 × NRP `/anthropic` 接口：实测与下一道门槛

2026-10-16。这里测试的是 **Agent 控制模型接口**，不是待后训练的 Feyospace、Gemma 或 Qwen 权重，也不是 CyberGym/SEC-bench 成绩。

## 新发现

[NRP 官方 Client Configurations](https://nrp.ai/documentation/userdocs/ai/llm-managed/client-configs/) 明确提供 `https://ellm.nrp-nautilus.io/anthropic` 作为 Claude Code 的 Anthropic-compatible 入口；其配置示例使用 `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN` 与具体模型 ID。[ABA 官方 README](https://github.com/aibuildai-inc/aibuildai-llm-posttrain-agent) 要求非 Claude 控制模型接入 Anthropic-compatible endpoint，锁定源码的 `startup/model_endpoint.py` 会将 `AIBUILDAI_BASE_URL` 和 `AIBUILDAI_API_KEY` 映射给 Claude Code。此前仅根据 NRP OpenAI-compatible `/v1` 文档作出的“必须写协议转换器”判断已过时；应首先测试现成 `/anthropic` 入口。

## 有界实测

用本机已有私密 NRP token，`scripts/probe-nrp-anthropic.py` 分别测试 `qwen3-small` 与 `qwen3`。每个模型最多三条无害请求：流式回答 `2+3`、强制调用只用于表示加法的 `add_numbers(7,8)`、回传结果 `15`。脚本不执行工具，不记录任意模型正文，不把 token 写进报告；每次输出上限分别为 64、128、64 token。

| 阶段 | qwen3-small | qwen3 |
| --- | --- | --- |
| Anthropic SSE 流式普通文本 | 通过；有 `message_start`、`content_block_delta`、`message_stop`，结果为 5 | 同左 |
| `tool_use` 内容块与参数 | 有且正确 | 有且正确 |
| 工具调用时的 `stop_reason` | **`end_turn`，预期 `tool_use`** | **`end_turn`，预期 `tool_use`** |
| `tool_result` 回传后数值回答 | 通过，结果为 15 | 同左 |

两份精简实测报告分别是 `docs/verification/nrp-anthropic-qwen3-small.json` 与 `docs/verification/nrp-anthropic-qwen3.json`。首次受沙箱网络限制的失败记录仅表示本机权限边界，不是 NRP 端点故障。

**结论：HTTP/流式/工具内容块基本连通，但不能标记 ABA 端到端兼容。** [Anthropic 工具调用规范](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use)把客户端工具调用的结束原因定义为 `tool_use`；[vLLM 当前映射说明](https://docs.vllm.ai/en/latest/api/vllm/entrypoints/anthropic/serving/)也特别处理强制命名工具导致的 `finish_reason=stop` 情况。实测 `end_turn` 可能令 Claude Code/SDK 认为本轮结束，不执行工具；也可能仍由客户端依据内容块执行。当前没有运行 ABA 的 SDK 真实工具回路，不能替客户端推断。NRP 文档也提醒部分模型不一定能顺利经该兼容接口运行。

## ABA 侧具体约束

- 锁定源码允许 `AIBUILDAI_BASE_URL=https://ellm.nrp-nautilus.io/anthropic`，凭证可从 `AIBUILDAI_API_KEY` 注入。**不要**提交真实 key 到 YAML、Git、交接包或命令行参数。
- `llm.default.model` 可先尝试 `qwen3-small`；该裸 ID 在当前 ABA 的模型族规则中落入兜底分支，但自定义 base URL 仍可路由。其定价/上下文元数据未在 ABA 自带 catalog 中确认。暂不启用 `llm.auto.allowed_models`：该配置会拒绝 catalog 未知模型。
- 非 Anthropic 官方主机上的 `WebSearch`/`WebFetch` 在 ABA 源码中被禁用；若工作流需要检索，需用有范围限制的 MCP/本地资料途径。
- 真实 ABA 运行还要求 Linux x86_64、systemd 用户会话、bwrap/cgroup、PostgreSQL 构建和可用数据/评分任务。此前 VM 基础环境 smoke 不能代替完整 ABA run。

下一步在隔离的 Linux 环境中做一个**仅限本地无害加法工具**的 Claude Agent SDK 往返测试：确认 CLI 看见 `tool_use` 后真的调用工具，且能接收结果。若通过，再做最小 ABA 安装/配置/预算受限启动；若失败，改用其它已验证兼容的控制端或具体修复 stop-marker 映射。不要以这个接口检查触发领域数据采集、自动执行安全任务或官方评测。
