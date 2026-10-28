#!/usr/bin/env python3
"""Verify public aggregate claims; optionally recheck private pilot files."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results/kali-qwen-official-executed-pilot-2026-10-28/summary.json"
SPLIT_CONFIG = ROOT / "configs/kali-qwen-official-executed-pilot-2026-10-28.json"
ENC_CONFIG = ROOT / "configs/kali-qwen-official-executed-encoding-2026-10-28.json"
SPLIT_DIR = "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28"
ENC_DIR = "docs/verification/kali-qwen-official-executed-pilot-2026-10-28"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def verify_private(root, summary):
    split_dir = root / SPLIT_DIR
    enc_dir = root / ENC_DIR
    manifest = load(split_dir / "manifest.json")
    receipt = load(enc_dir / "cpu-encoding-summary.json")
    assert digest(split_dir / "manifest.json") == summary["split_manifest_sha256"]
    assert manifest["file_sha256"]["pilot_train.jsonl"] == summary["pilot_train_sha256"]
    assert manifest["file_sha256"]["pilot_dev.jsonl"] == summary["pilot_dev_sha256"]
    assert manifest["pilot_terminal_labels"] == {"PASS_EXECUTED": 640}
    assert receipt["private_file_sha256"]["train_encoded_private.json"] == summary["private_train_encoded_sha256"]
    assert receipt["private_file_sha256"]["dev_inputs_private.json"] == summary["private_dev_inputs_sha256"]
    assert receipt["private_file_sha256"]["dev_reference_private.json"] == summary["private_dev_reference_sha256"]
    for name, expected in manifest["file_sha256"].items():
        assert digest(split_dir / name) == expected
    for name, expected in receipt["private_file_sha256"].items():
        assert digest(enc_dir / name) == expected
    train = load(enc_dir / "train_encoded_private.json")
    dev = load(enc_dir / "dev_inputs_private.json")
    refs = load(enc_dir / "dev_reference_private.json")
    assert len(train) == 512 and len(dev) == len(refs) == 128
    assert {x["id"] for x in train}.isdisjoint(x["id"] for x in dev)
    assert {x["id"] for x in dev} == {x["id"] for x in refs}
    assert all(set(x).isdisjoint({"target", "native_label", "ground_truth_command"}) for x in dev)
    for row in train:
        cut = row["prompt_tokens"]
        assert row["labels"][:cut] == [-100] * cut
        assert row["labels"][cut:] == row["input_ids"][cut:]
        assert row["labels"][-1] != -100 and len(row["input_ids"]) <= 2048
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, help="Root containing omitted raw/split/encoded files")
    args = parser.parse_args()
    summary = load(SUMMARY)
    split = load(SPLIT_CONFIG)
    encoding = load(ENC_CONFIG)
    assert digest(SPLIT_CONFIG) == summary["split_config_sha256"]
    assert digest(ENC_CONFIG) == summary["encoding_config_sha256"]
    assert summary["status"] == "PREPARED_CPU_ONLY_NO_MODEL_RUN"
    assert summary["model_id"] == split["model_id"] == encoding["model_id"]
    assert summary["model_revision"] == split["model_revision"] == encoding["model_revision"]
    assert (summary["pilot_train_rows"], summary["pilot_dev_rows"]) == (512, 128)
    assert summary["source_sha256"] == split["source_sha256"]
    assert summary["dev_gold_in_dev_inputs"] is False
    assert summary["all_train_prompt_labels_masked"] is True
    assert summary["all_train_target_and_EOS_supervised"] is True
    assert all(summary[key] == 0 for key in ("official_TEST_rows_opened", "commands_executed",
                                            "model_calls", "GPU_jobs", "optimizer_steps"))
    assert all(summary[key] is None for key in ("training_result", "development_score", "official_score"))
    result = {"public_aggregate": "PASS", "private_recheck": "NOT_REQUESTED"}
    if args.private_root:
        assert verify_private(args.private_root, summary)
        result["private_recheck"] = "PASS"
    print(json.dumps(result))


if __name__ == "__main__":
    main()
