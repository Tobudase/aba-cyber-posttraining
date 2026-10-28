#!/usr/bin/env python3
"""Prepare Qwen-native TRAIN labels only; no model execution or training."""

import ast
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/kali-qwen-second-base-prep.json"
MODEL = ROOT / ".tools/model-tokenizer/qwen3-8b-b968826d9c46"
OUT = ROOT / "docs/verification/kali-qwen3-8b-second-base-2026-10-28"
PROMPT_SOURCE = ROOT / ".tools/benchkit/kali/src/prompt.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_constants(source):
    wanted = {"SYSTEM_PROMPT_UNRESTRICTED_THINKING", "USER_PROMPT_UNRESTRICTED_THINKING_TEMPLATE"}
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    assert target.id not in found
                    found[target.id] = ast.literal_eval(node.value)
    assert set(found) == wanted and all(isinstance(value, str) for value in found.values())
    return found


def encode_one(tokenizer, row, constants, suffix, max_length):
    if (row.get("split") != "train" or row.get("official_test") is not False or
            row.get("training_eligible") is not True or
            row.get("TRAIN_fixture_execution_verified") is not True or
            row.get("TRAIN_explicit_constraints_verified") is not True):
        raise ValueError("Only prior verified TRAIN can be tokenized")
    query = row["query"]
    gold = row["gold_command"]
    if not query or not gold or any(marker in query for marker in ("<|im_", "<think>", "</think>")):
        raise ValueError("Unexpected prompt marker or empty input")
    messages = [
        {"role": "system", "content": constants["SYSTEM_PROMPT_UNRESTRICTED_THINKING"]},
        {"role": "user", "content": constants["USER_PROMPT_UNRESTRICTED_THINKING_TEMPLATE"].format(query=query)},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                            enable_thinking=False)
    if not prompt.endswith(suffix):
        raise ValueError("Unexpected Qwen-native nonthinking prefix")
    target = "<output>\n" + gold + "\n</output>"
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
    target_ids = tokenizer.encode(target, add_special_tokens=False)
    eos = tokenizer.eos_token_id
    if eos is None or not target_ids or eos in target_ids:
        raise ValueError("Target contains EOS or is empty")
    ids = prompt_ids + target_ids + [eos]
    if len(ids) > max_length:
        raise ValueError("No silent truncation")
    decoded = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    if decoded != prompt + target + tokenizer.eos_token:
        raise ValueError("Token concatenation changed text")
    labels = [-100] * len(prompt_ids) + target_ids + [eos]
    assert len(labels) == len(ids) and labels[:len(prompt_ids)] == [-100] * len(prompt_ids)
    return {
        "id": row["id"],
        "source_split": "TRAIN",
        "training_eligible": False,
        "release_gate": "INDEPENDENT_HUMAN_REVIEW_PENDING",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "input_ids": ids,
        "labels": labels,
        "prompt_tokens": len(prompt_ids),
        "target_tokens": len(target_ids) + 1,
    }


def main():
    config = json.loads(CONFIG.read_text())
    assert config["status"] == "TOKENIZER_PREP_ONLY_NO_TRAINING_AUTHORIZATION"
    assert config["model_id"] == "Qwen/Qwen3-8B"
    train = ROOT / config["train_source"]
    assert sha(train) == config["train_sha256"]
    assert sha(MODEL / "tokenizer.json") == config["tokenizer_sha256"]
    assert sha(PROMPT_SOURCE) == config["prompt_source_sha256"]
    rows = [json.loads(line) for line in train.read_text().splitlines()]
    assert len(rows) == config["train_rows_expected"] == 240
    assert len({row["id"] for row in rows}) == len(rows)
    constants = prompt_constants(PROMPT_SOURCE.read_text())
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False,
                                              fix_mistral_regex=False)
    encoded = [encode_one(tokenizer, row, constants, config["expected_prompt_suffix"],
                          config["max_sequence_tokens"]) for row in rows]
    assert all(len(row["input_ids"]) == len(row["labels"]) for row in encoded)
    assert all(row["training_eligible"] is False for row in encoded)
    assert all(row["labels"][row["prompt_tokens"]:] == row["input_ids"][row["prompt_tokens"]:]
               for row in encoded)
    OUT.mkdir(exist_ok=True)
    data_path = OUT / "encoded-train-prep-private.json"
    if data_path.exists():
        raise FileExistsError("Existing tokenized preparation is immutable; inspect before a new run")
    data_path.write_text(json.dumps(encoded, separators=(",", ":")) + "\n")
    audit = {
        "status": "PASS_QWEN_NATIVE_TRAIN_ENCODING_PREP_NOT_TRAINING_APPROVED",
        "model_id": config["model_id"],
        "revision": config["model_revision"],
        "prompt_mode": config["prompt_mode"],
        "TRAIN_rows": len(encoded),
        "TRAIN_source_sha256": sha(train),
        "config_sha256": sha(CONFIG),
        "encoded_private_sha256": sha(data_path),
        "prompt_tokens_min": min(row["prompt_tokens"] for row in encoded),
        "prompt_tokens_max": max(row["prompt_tokens"] for row in encoded),
        "target_tokens_total": sum(row["target_tokens"] for row in encoded),
        "target_tokens_max": max(row["target_tokens"] for row in encoded),
        "sequence_tokens_max": max(len(row["input_ids"]) for row in encoded),
        "masked_prompt_tokens_total": sum(row["prompt_tokens"] for row in encoded),
        "all_prompt_labels_masked": True,
        "all_target_and_EOS_labels_supervised": True,
        "all_decoded_roundtrips_exact": True,
        "rows_approved_for_training": 0,
        "independent_human_reviews": 0,
        "DEV_rows_opened": 0,
        "confirmation_rows_opened": 0,
        "official_TEST_rows_opened": 0,
        "model_calls": 0,
        "GPU_jobs": 0,
        "optimizer_steps": 0,
    }
    (OUT / "encoding-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({key: audit[key] for key in ("status", "TRAIN_rows", "prompt_tokens_max",
                                               "target_tokens_total", "sequence_tokens_max",
                                               "rows_approved_for_training", "model_calls")}, indent=2))


if __name__ == "__main__":
    main()
