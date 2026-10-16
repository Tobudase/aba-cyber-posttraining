#!/usr/bin/env python3
"""One bounded Claude Agent SDK tool round-trip through NRP's Anthropic route.

The only exposed tool adds 7+8, has no side effects, and rejects other input.
Read the NRP token from stdin, never from argv or source. This script is meant
for an isolated Linux test environment with claude-agent-sdk==0.2.148.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)

MODEL = "qwen3-small"
BASE_URL = "https://ellm.nrp-nautilus.io/anthropic"
TOOL_NAME = "mcp__calc__add_numbers"


@tool("add_numbers", "Add two integers from -1000 to 1000; no other action.", {"a": int, "b": int})
async def add_numbers(args):
    report["tool_invocations"] += 1
    if (not isinstance(args, dict) or set(args) != {"a", "b"}
            or any(type(args[k]) is not int or not -1000 <= args[k] <= 1000 for k in args)
            or args != {"a": 7, "b": 8}):
        report["invalid_tool_input"] = True
        return {"content": [{"type": "text", "text": "Invalid arguments"}], "isError": True}
    report["valid_tool_input"] = True
    return {"content": [{"type": "text", "text": "15"}]}


report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "endpoint": BASE_URL,
    "model": MODEL,
    "sdk_version_pinned": "0.2.148",
    "max_turns": 3,
    "allowed_tool": TOOL_NAME,
    "tool_invocations": 0,
    "valid_tool_input": False,
    "invalid_tool_input": False,
    "assistant_tool_block_seen": False,
    "assistant_final_answer_is_15": False,
    "result_message_seen": False,
    "result_is_error": None,
    "passed": False,
    "training_performed": False,
    "benchmark_tasks_used": 0,
}


async def run():
    server = create_sdk_mcp_server(name="calc", version="1.0.0", tools=[add_numbers])
    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt="This is a calculator-only compatibility check. Use the available add_numbers tool exactly once. Do not use any other tool. After its result, reply with 15 only.",
        cwd=str(Path.cwd()),
        tools=[],
        allowed_tools=[TOOL_NAME],
        mcp_servers={"calc": server},
        strict_mcp_config=True,
        setting_sources=[],
        permission_mode="bypassPermissions",
        max_turns=3,
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query("Call add_numbers with a=7 and b=8, then answer with the sum only.")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock) and block.name == TOOL_NAME:
                        report["assistant_tool_block_seen"] = True
                    if isinstance(block, TextBlock) and block.text.strip() == "15":
                        report["assistant_final_answer_is_15"] = True
            elif isinstance(message, ResultMessage):
                report["result_message_seen"] = True
                report["result_is_error"] = bool(message.is_error)


def main():
    token = sys.stdin.readline(16385).strip()
    if not token or len(token) > 16384 or any(char.isspace() for char in token):
        report["error_type"] = "MissingOrInvalidStdinToken"
    else:
        os.environ.update({
            "ANTHROPIC_BASE_URL": BASE_URL,
            "ANTHROPIC_AUTH_TOKEN": token,
            "ANTHROPIC_MODEL": MODEL,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
            "CLAUDE_CODE_SUBAGENT_MODEL": MODEL,
            "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "ENABLE_TOOL_SEARCH": "false",
        })
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            asyncio.run(asyncio.wait_for(run(), timeout=120))
        except Exception as exc:
            report["error_type"] = type(exc).__name__
        finally:
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
            token = ""
    report["passed"] = bool(
        report["tool_invocations"] == 1 and report["valid_tool_input"]
        and not report["invalid_tool_input"]
        and report["assistant_tool_block_seen"]
        and report["assistant_final_answer_is_15"]
        and report["result_message_seen"]
        and report["result_is_error"] is False
    )
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
