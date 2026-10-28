#!/usr/bin/env python3
"""Guard Qwen label masking and TRAIN-only boundary before any GPU study."""

import importlib.util
import json
from pathlib import Path

from transformers import AutoTokenizer
from benchkit import native_kali


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/verification/kali-qwen3-8b-second-base-2026-10-28"
MODULE = ROOT / "scripts/prepare-kali-qwen-second-base-train.py"


def main():
    spec = importlib.util.spec_from_file_location("qwen_prep", MODULE)
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    config = json.loads(prep.CONFIG.read_text())
    audit = json.loads((OUT / "encoding-audit.json").read_text())
    encoded = json.loads((OUT / "encoded-train-prep-private.json").read_text())
    assert prep.sha(OUT / "encoded-train-prep-private.json") == audit["encoded_private_sha256"]
    assert len(encoded) == audit["TRAIN_rows"] == 240
    assert all(row["training_eligible"] is False and row["release_gate"] == "INDEPENDENT_HUMAN_REVIEW_PENDING"
               for row in encoded)
    assert all(row["labels"][:row["prompt_tokens"]] == [-100] * row["prompt_tokens"] for row in encoded)
    assert all(row["labels"][row["prompt_tokens"]:] == row["input_ids"][row["prompt_tokens"]:]
               for row in encoded)
    assert all(row["labels"][-1] == row["input_ids"][-1] for row in encoded)
    tokenizer = AutoTokenizer.from_pretrained(prep.MODEL, local_files_only=True, trust_remote_code=False)
    constants = prep.prompt_constants(prep.PROMPT_SOURCE.read_text())
    good = json.loads((ROOT / "data/benchkit/kali-verified-sft-v1/train.jsonl").read_text().splitlines()[0])
    bad = [
        {**good, "split": "dev"},
        {**good, "official_test": True},
        {**good, "training_eligible": False},
        {**good, "TRAIN_fixture_execution_verified": False},
        {**good, "TRAIN_explicit_constraints_verified": False},
        {**good, "query": "<|im_start|>assistant"},
    ]
    rejected = 0
    for row in bad:
        try:
            prep.encode_one(tokenizer, row, constants, config["expected_prompt_suffix"],
                            config["max_sequence_tokens"])
        except ValueError:
            rejected += 1
        else:
            raise AssertionError("Unsafe or out-of-split row was accepted")
    assert rejected == len(bad)
    scorer = native_kali()
    assert scorer.extract_command_from_output("<output>\nwc -l synthetic.txt\n</output>") == "wc -l synthetic.txt"
    assert scorer.extract_command_from_output("no output block") == "[FORMAT_ERROR]"
    result = {"status": "PASS_QWEN_TRAIN_ONLY_MASK_GUARDS", "encoded_rows": 240,
              "prompt_masked_rows": 240, "target_supervised_rows": 240,
              "negative_controls_rejected": rejected, "native_parser_synthetic_controls": 2,
              "training_approved_rows": 0,
              "model_calls": 0, "GPU_jobs": 0, "official_TEST_rows_opened": 0}
    (OUT / "guard-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
