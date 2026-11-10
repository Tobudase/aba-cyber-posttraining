#!/usr/bin/env python3
"""Encode 638 publisher-verified KaliBench TRAIN rows for RedSage native SFT.

The rows are publisher silver labels. Commands remain inert data strings.
No DEV or official TEST rows are loaded as training examples.
"""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/benchkit/kali-screened/train.jsonl"
PUBLISHER = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
IDS = ROOT / "data/benchkit/kali-qwen-expanded-2026-10-30/selection-ids-private.json"
HOLDOUT = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10/references-private.json"
TOKENIZER = ROOT / ".tools/model-tokenizer/redsage-k-843e2e3096e7"
OUT = ROOT / "data/benchkit/kali-redsage-publisher-sft638-2026-11-10"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group(row):
    label = row["native_label"]
    return label["tool_name"], " ".join(label["ground_truth_command"].split())


def main():
    assert not OUT.exists(), "Never regenerate an encoded study in place"
    assert sha(PUBLISHER) == "93dc4ddff6d9df73bed4b9e92716470e7a73df513f5ca2f1b201c85f2329f909"
    source = {r["id"]: r for r in map(json.loads, SOURCE.read_text().splitlines())}
    publisher = {r["custom_id"]: r for r in map(json.loads, PUBLISHER.read_text().splitlines())}
    ids = json.loads(IDS.read_text())
    train_ids = ids["old_ai505_train"] + ids["added_train133"]
    assert len(train_ids) == len(set(train_ids)) == 638
    train = [source[i] for i in train_ids]
    holdout = json.loads(HOLDOUT.read_text())
    holdout_ids = {r["custom_id"] for r in holdout}
    assert len(holdout_ids) == 64 and not holdout_ids & set(train_ids)
    assert not holdout_ids & set(ids["fresh_dev64"])
    assert not {group(r) for r in train} & {
        (r["tool_name"], " ".join(r["ground_truth_command"].split())) for r in holdout}
    tok = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True,
                                          trust_remote_code=False, fix_mistral_regex=False)
    assert tok.eos_token_id == 151645 and tok.eos_token == "<|im_end|>"
    encoded = []
    for row in train:
        original = publisher[row["id"]]
        assert original["terminal_verification"]["label"] == "PASS_EXECUTED"
        assert original["model_verification"]["model_output"]["verdict"] == "ACCURATE"
        assert row["split"] == "train" and row["training_eligible"] is True
        assert row["official_test"] is False
        assert row["native_label"]["ground_truth_command"] == original["ground_truth_command"]
        assert row["target"] == "<output>\n" + original["ground_truth_command"] + "\n</output>"
        assert all(m["role"] in ("system", "user") for m in row["messages"])
        prompt = tok.apply_chat_template(row["messages"], tokenize=False,
                                         add_generation_prompt=True)
        assert prompt.endswith("<think>")
        completion = "\n</think>\n\n" + row["target"]
        prompt_ids = tok.encode(prompt, add_special_tokens=False)
        target_ids = tok.encode(completion, add_special_tokens=False)
        assert tok.eos_token_id not in target_ids and target_ids
        full = prompt_ids + target_ids + [tok.eos_token_id]
        assert len(full) <= 2048
        assert tok.decode(full, skip_special_tokens=False,
                          clean_up_tokenization_spaces=False) == prompt + completion + tok.eos_token
        encoded.append({"id": row["id"], "split": "train",
                        "training_eligible": True, "official_test": False,
                        "publisher_terminal_PASS_EXECUTED": True,
                        "publisher_model_ACCURATE": True,
                        "input_ids": full,
                        "labels": [-100] * len(prompt_ids) + target_ids + [tok.eos_token_id],
                        "prompt_tokens": len(prompt_ids),
                        "target_tokens": len(target_ids) + 1})
    OUT.mkdir(parents=True)
    path = OUT / "train-encoded-private.json"
    path.write_text(json.dumps(encoded, ensure_ascii=False, separators=(",", ":")) + "\n")
    report = {"status": "ENCODED_PUBLISHER_TRAIN638_FOR_REDSAGE_BEFORE_NEW_SFT",
              "rows": len(encoded), "tools": len({r["native_label"]["tool_name"] for r in train}),
              "holdout_rows_excluded": 64, "prior_internal_dev_rows_excluded": 64,
              "source_official_split": "train", "official_TEST_rows": 0,
              "optimizer_steps": 0, "model_outputs": 0,
              "publisher_silver_not_expert_gold": True,
              "same_native_empty_think_target_mode_as_C13": True,
              "supervised_tokens": sum(r["target_tokens"] for r in encoded),
              "max_sequence_tokens": max(len(r["input_ids"]) for r in encoded),
              "publisher_sha256": sha(PUBLISHER), "source_sha256": sha(SOURCE),
              "split_ids_sha256": sha(IDS), "holdout_references_sha256": sha(HOLDOUT),
              "tokenizer_json_sha256": sha(TOKENIZER / "tokenizer.json"),
              "encoded_sha256": sha(path),
              "note": "Encoded data is prepared only; it has not been used in GPU training."}
    (OUT / "freeze-manifest-private.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in (
        "status", "rows", "tools", "supervised_tokens",
        "max_sequence_tokens", "official_TEST_rows", "optimizer_steps")}, indent=2))


if __name__ == "__main__":
    main()
