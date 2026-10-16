#!/usr/bin/env python3
"""Bounded, harmless probe of NRP's Anthropic-compatible Messages endpoint.

Checks a streamed text answer, a forced add_numbers tool call, and a tool-result
follow-up. No tools are actually executed and no arbitrary model text is saved.
"""

from datetime import datetime, timezone
import argparse
import importlib.util
import json
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://ellm.nrp-nautilus.io/anthropic"
MAX_BODY = 2 * 1024 * 1024
TOTAL_SECONDS = 150


def credential_reader():
    spec = importlib.util.spec_from_file_location("nrp_probe_shared", ROOT / "scripts/probe-nrp-model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(opener, token, payload, deadline):
    timeout = min(45, deadline - time.monotonic())
    if timeout <= 0:
        raise RuntimeError("Total time budget exhausted")
    req = urllib.request.Request(
        BASE_URL + "/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if payload.get("stream") else "application/json",
        },
        method="POST",
    )
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read(MAX_BODY + 1)
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        # HTTP response bodies can contain input echoes or other sensitive data.
        raise RuntimeError(f"HTTP {exc.code}; response body omitted") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise RuntimeError("Network or timeout failure; details omitted") from None
    if len(body) > MAX_BODY:
        raise RuntimeError("Response exceeded 2 MiB limit")
    return body, content_type


def parse_stream(body):
    events = []
    text_parts = []
    try:
        for frame in body.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
            data_lines = [line[6:] for line in frame.splitlines() if line.startswith("data: ")]
            if not data_lines or data_lines == ["[DONE]"]:
                continue
            payload = json.loads("\n".join(data_lines))
            kind = payload.get("type")
            if kind == "error":
                raise RuntimeError("SSE error event; body omitted")
            if kind in {"message_start", "content_block_start", "content_block_delta", "content_block_stop", "message_delta", "message_stop"}:
                events.append(kind)
            delta = payload.get("delta")
            if kind == "content_block_delta" and isinstance(delta, dict) and delta.get("type") == "text_delta":
                text_parts.append(delta.get("text", ""))
    except (UnicodeError, ValueError, TypeError):
        raise RuntimeError("Invalid SSE response; body omitted") from None
    return "".join(text_parts), events


def message_content(body):
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        raise RuntimeError("Invalid JSON response; body omitted") from None
    if payload.get("type") != "message" or payload.get("role") != "assistant":
        raise RuntimeError("Expected an Anthropic assistant message")
    blocks = payload.get("content")
    if not isinstance(blocks, list):
        raise RuntimeError("Expected content blocks")
    return blocks, payload.get("stop_reason")


def run(model):
    token = credential_reader()()
    context = ssl.create_default_context()
    if sys.platform == "darwin" and ssl.get_default_verify_paths().cafile is None:
        system_ca = Path("/etc/ssl/cert.pem")
        if system_ca.is_file():
            context.load_verify_locations(cafile=str(system_ca))
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context))
    deadline = time.monotonic() + TOTAL_SECONDS
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": BASE_URL,
        "model": model,
        "generation_requests_max": 3,
        "max_tokens_per_request": [64, 128, 64],
        "task_execution": False,
        "training_performed": False,
        "stages": {},
        "passed": False,
    }
    requests_attempted = 0
    try:
        base = {"model": model, "max_tokens": 64}
        requests_attempted += 1
        body, content_type = post(opener, token, base | {
            "messages": [{"role": "user", "content": "What is 2 + 3? Reply with the numeral only."}],
            "stream": True,
        }, deadline)
        text, events = parse_stream(body)
        report["stages"]["streamed_text"] = {
            "passed": "text/event-stream" in content_type and text.strip() == "5" and
                      "message_start" in events and "message_stop" in events,
            "event_types": sorted(set(events)),
            "answer_is_5": text.strip() == "5",
        }
        tool = {"name": "add_numbers", "description": "Add two integers; no side effects.",
                "input_schema": {"type": "object", "properties": {
                    "a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"], "additionalProperties": False}}
        prompt = "Use add_numbers exactly once with a=7 and b=8."
        requests_attempted += 1
        body, _ = post(opener, token, {"model": model, "max_tokens": 128,
            "messages": [{"role": "user", "content": prompt}], "tools": [tool],
            "tool_choice": {"type": "tool", "name": "add_numbers"}, "stream": False}, deadline)
        blocks, reason = message_content(body)
        calls = [block for block in blocks if isinstance(block, dict) and block.get("type") == "tool_use"]
        if len(calls) != 1 or calls[0].get("name") != "add_numbers" or calls[0].get("input") != {"a": 7, "b": 8}:
            raise RuntimeError("Expected one exact add_numbers tool_use; no tool executed")
        call_id = calls[0].get("id")
        if not isinstance(call_id, str) or not 1 <= len(call_id) <= 256:
            raise RuntimeError("Missing valid tool_use ID")
        report["stages"]["tool_use"] = {"passed": reason == "tool_use", "stop_reason": reason}
        requests_attempted += 1
        body, _ = post(opener, token, {"model": model, "max_tokens": 64,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": [{"type": "tool_use", "id": call_id,
                    "name": "add_numbers", "input": {"a": 7, "b": 8}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id,
                    "content": "15"}, {"type": "text", "text": "Reply with the resulting numeral only."}]},
            ], "stream": False}, deadline)
        blocks, reason = message_content(body)
        text = "".join(block.get("text", "") for block in blocks
                       if isinstance(block, dict) and block.get("type") == "text")
        report["stages"]["tool_result_followup"] = {
            "passed": text.strip() == "15" and reason == "end_turn",
            "answer_is_15": text.strip() == "15", "stop_reason": reason,
        }
        report["passed"] = all(stage["passed"] for stage in report["stages"].values())
    except Exception as exc:
        # Keep network errors and model content out of durable reports.
        report["error"] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
    report["generation_requests_attempted"] = requests_attempted
    dest = ROOT / "docs/verification" / (
        "nrp-anthropic-probe-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(dest),
                      "stages": report["stages"], "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("qwen3-small", "qwen3"), default="qwen3-small")
    sys.exit(run(parser.parse_args().model))
