#!/usr/bin/env python3
"""Offline, synthetic tokenizer and tool-template checks for the Feyospace candidate."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs/feyospace-v1.1.candidate.lock.json"


def main():
    from transformers import AutoTokenizer

    lock = json.loads(LOCK.read_text())
    if lock["model_id"] != "feyospace/feyospace-v1.1-small":
        raise RuntimeError("Unexpected candidate lock")
    cache = ROOT / lock["local_metadata_dir"]
    for name, expected in lock["files"].items():
        raw = (cache / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise RuntimeError("Metadata checksum mismatch: " + name)
    tokenizer = AutoTokenizer.from_pretrained(cache, local_files_only=True, trust_remote_code=False)
    user = [{"role": "user", "content": "Reply with OK."}]
    complete = user + [{"role": "assistant", "content": "OK"}]
    prefix = tokenizer.apply_chat_template(user, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full = tokenizer.apply_chat_template(complete, tokenize=False, add_generation_prompt=False, enable_thinking=False)
    if not full.startswith(prefix):
        raise RuntimeError("Assistant turn is not a prefix-preserving continuation")
    prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if full_ids[:len(prefix_ids)] != prefix_ids or len(full_ids) <= len(prefix_ids):
        raise RuntimeError("Assistant token boundary could not be isolated")
    tool = {"type": "function", "function": {"name": "add_numbers", "description": "Add integers.",
            "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                           "required": ["a", "b"]}}}
    messages = [user[0], {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {
        "name": "add_numbers", "arguments": {"a": 2, "b": 3}}}]},
        {"role": "tool", "content": '{"sum":5}'}, {"role": "assistant", "content": "5"}]
    rendered = tokenizer.apply_chat_template(messages, tools=[tool], tokenize=False,
                                             add_generation_prompt=False, enable_thinking=False)
    if "<function=add_numbers>" not in rendered or "<tool_response>" not in rendered:
        raise RuntimeError("Synthetic tool exchange did not serialize as expected")
    report = {
        "status": "PASSED_OFFLINE_METADATA_ONLY",
        "model_id": lock["model_id"], "revision": lock["revision"],
        "verified_file_count": len(lock["files"]), "tokenizer_class": type(tokenizer).__name__,
        "vocab_size": len(tokenizer), "assistant_prefix_tokens": len(prefix_ids),
        "assistant_completion_tokens": len(full_ids) - len(prefix_ids),
        "synthetic_tool_round_trip_serialized": True,
        "weights_loaded": False, "gpu_used": False, "official_benchmark_tasks_used": 0,
        "training_executed": False,
        "license_verified_for_posttraining": lock["license_verified_for_posttraining"],
    }
    dest = ROOT / "docs/verification/feyospace-preparation.json"
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
