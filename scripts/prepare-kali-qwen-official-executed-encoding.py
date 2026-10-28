#!/usr/bin/env python3
"""Encode publisher-verified TRAIN and DEV inputs for Qwen; never open official TEST."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/kali-qwen-official-executed-encoding-2026-10-28.json"
TOKENIZER = ROOT / ".tools/model-tokenizer/qwen3-8b-b968826d9c46"
OUT = ROOT / "docs/verification/kali-qwen-official-executed-pilot-2026-10-28"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_ids(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def main():
    config = json.loads(CONFIG.read_text())
    assert config["status"] == "FROZEN_BEFORE_QWEN_MODEL_OUTPUTS"
    assert sha(TOKENIZER / "tokenizer.json") == config["tokenizer_sha256"]
    split_manifest = ROOT / config["split_manifest"]
    split = json.loads(split_manifest.read_text())
    assert split["status"] == "FROZEN_OFFICIAL_TRAIN_ONLY_PILOT_SPLIT"
    assert split["pilot_terminal_labels"] == {"PASS_EXECUTED": 640}
    source_dir = split_manifest.parent
    train_path = source_dir / "pilot_train.jsonl"
    dev_path = source_dir / "pilot_dev.jsonl"
    assert sha(train_path) == split["file_sha256"]["pilot_train.jsonl"]
    assert sha(dev_path) == split["file_sha256"]["pilot_dev.jsonl"]
    train = [json.loads(line) for line in train_path.read_text().splitlines()]
    dev = [json.loads(line) for line in dev_path.read_text().splitlines()]
    assert len(train) == 512 and len(dev) == 128
    assert {row["id"] for row in train}.isdisjoint(row["id"] for row in dev)
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True,
                                                trust_remote_code=False, fix_mistral_regex=False)
    suffix = config["expected_prompt_suffix"]
    eos = tokenizer.eos_token_id
    assert eos is not None and tokenizer.eos_token
    encoded_train = []
    dev_inputs = []
    dev_reference = []
    for row in train + dev:
        is_train = row["split"] == "train"
        assert row["split"] in ("train", "dev")
        assert row["training_eligible"] is is_train and row["official_test"] is False
        assert row["source_official_split"] == "train"
        assert row["quality"] == "PUBLISHER_MODEL_VERIFIED_AND_TERMINAL_EXECUTED_SUCCESSFULLY_NOT_EXPERT_GOLD"
        assert tuple(message["role"] for message in row["messages"]) == ("system", "user")
        prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False,
                                                add_generation_prompt=True, enable_thinking=False)
        assert prompt.endswith(suffix)
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        assert tokenizer.decode(prompt_ids, skip_special_tokens=False,
                                clean_up_tokenization_spaces=False) == prompt
        if is_train:
            target = row["target"]
            assert target == "<output>\n" + row["native_label"]["ground_truth_command"] + "\n</output>"
            target_ids = tokenizer.encode(target, add_special_tokens=False)
            assert target_ids and eos not in target_ids
            full_ids = prompt_ids + target_ids + [eos]
            assert len(full_ids) <= config["max_train_sequence_tokens"]
            assert tokenizer.decode(full_ids, skip_special_tokens=False,
                                    clean_up_tokenization_spaces=False) == prompt + target + tokenizer.eos_token
            labels = [-100] * len(prompt_ids) + target_ids + [eos]
            assert len(labels) == len(full_ids)
            encoded_train.append({"id": row["id"], "input_ids": full_ids, "labels": labels,
                                  "prompt_tokens": len(prompt_ids), "target_tokens": len(target_ids) + 1,
                                  "publisher_verified_silver": True, "official_test": False,
                                  "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
        else:
            dev_inputs.append({"id": row["id"], "messages": row["messages"],
                               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                               "input_ids_sha256": hash_ids(prompt_ids), "prompt_tokens": len(prompt_ids),
                               "official_test": False})
            dev_reference.append({"id": row["id"], "native_label": row["native_label"],
                                  "target": row["target"], "official_test": False})
    assert len(encoded_train) == 512 and len(dev_inputs) == len(dev_reference) == 128
    assert {r["id"] for r in encoded_train}.isdisjoint(r["id"] for r in dev_inputs)
    OUT.mkdir(exist_ok=False)
    files = {"train_encoded_private.json": encoded_train,
             "dev_inputs_private.json": dev_inputs,
             "dev_reference_private.json": dev_reference}
    paths = {}
    for name, obj in files.items():
        path = OUT / name
        path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n")
        paths[name] = sha(path)
    summary = {
        "status": "PASS_QWEN_OFFICIAL_EXECUTED_PILOT_CPU_ENCODING",
        "source_quality": "publisher model ACCURATE plus terminal PASS_EXECUTED; not independent expert gold",
        "model_id": config["model_id"],
        "model_revision": config["model_revision"],
        "split_manifest_sha256": sha(split_manifest),
        "encoding_config_sha256": sha(CONFIG),
        "train_rows": len(encoded_train),
        "dev_rows": len(dev_inputs),
        "train_prompt_tokens_min": min(r["prompt_tokens"] for r in encoded_train),
        "train_prompt_tokens_max": max(r["prompt_tokens"] for r in encoded_train),
        "train_supervised_target_tokens": sum(r["target_tokens"] for r in encoded_train),
        "train_sequence_tokens_max": max(len(r["input_ids"]) for r in encoded_train),
        "dev_prompt_tokens_max": max(r["prompt_tokens"] for r in dev_inputs),
        "all_train_prompt_labels_masked": True,
        "all_train_target_and_EOS_supervised": True,
        "all_train_decoded_roundtrips": True,
        "dev_gold_in_dev_inputs": False,
        "dev_gradient_rows": 0,
        "official_TEST_rows_opened": 0,
        "commands_executed": 0,
        "model_calls": 0,
        "GPU_jobs": 0,
        "optimizer_steps": 0,
        "private_file_sha256": paths,
    }
    (OUT / "cpu-encoding-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("status", "train_rows", "dev_rows",
                                                   "train_sequence_tokens_max", "dev_gold_in_dev_inputs",
                                                   "official_TEST_rows_opened")}, indent=2))


if __name__ == "__main__":
    main()
