#!/usr/bin/env python3
"""Freeze previously unqueried official-TRAIN internal DEV rows before model outputs."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/kali-qwen-confirmation-93-2026-10-28.json"
OUT = ROOT / "data/benchkit/kali-qwen-confirmation-2026-10-28"
TOKENIZER = ROOT / ".tools/model-tokenizer/qwen3-8b-b968826d9c46"
PUBLISHER = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
PUBLISHER_SHA = "93dc4ddff6d9df73bed4b9e92716470e7a73df513f5ca2f1b201c85f2329f909"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group(row):
    return (row["native_label"]["tool_name"], " ".join(row["native_label"]["ground_truth_command"].split()))


def main():
    cfg = json.loads(CONFIG.read_text())
    assert cfg["status"] == "FROZEN_BEFORE_93_MODEL_OUTPUTS"
    assert cfg["official_TEST_rows"] == cfg["train_rows_for_gradient"] == 0
    assert sha(TOKENIZER / "tokenizer.json") == cfg["tokenizer_sha256"]
    source_path = ROOT / cfg["source_file"]
    assert sha(source_path) == cfg["source_sha256"]
    assert sha(PUBLISHER) == PUBLISHER_SHA
    publisher = {r["custom_id"]: r for r in map(json.loads, PUBLISHER.read_text().splitlines())}
    assert len(publisher) == 3504
    source = {r["id"]: r for r in map(json.loads, source_path.read_text().splitlines())}
    assert len(source) == 3376
    manifest_path = ROOT / cfg["prior_split_manifest"]
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "FROZEN_OFFICIAL_TRAIN_ONLY_PILOT_SPLIT"
    assert manifest["raw_publisher_train_sha256"] == PUBLISHER_SHA
    ids_path = ROOT / cfg["prior_split_ids"]
    assert sha(ids_path) == manifest["split_ids_sha256"]
    ids = json.loads(ids_path.read_text())
    prior_path = ROOT / cfg["prior_pilot_dev"]
    assert sha(prior_path) == manifest["file_sha256"]["pilot_dev.jsonl"]
    prior = [json.loads(x) for x in prior_path.read_text().splitlines()]
    train_path = prior_path.with_name("pilot_train.jsonl")
    assert sha(train_path) == manifest["file_sha256"]["pilot_train.jsonl"]
    train = [json.loads(x) for x in train_path.read_text().splitlines()]
    assert len(prior) == 128 and len(train) == 512
    assert {x["id"] for x in prior} == set(ids["pilot_dev"])
    assert {x["id"] for x in train} == set(ids["pilot_train"])
    remaining_ids = sorted(set(ids["full_dev"]) - set(ids["pilot_dev"]))
    assert len(remaining_ids) == cfg["all_unqueried_rows"] == 93
    assert set(remaining_ids).isdisjoint(ids["pilot_train"])
    remaining = [source[i] for i in remaining_ids]
    prior_groups = {group(row) for row in prior}
    train_groups = {group(row) for row in train}
    primary_ids = [row["id"] for row in remaining if group(row) not in prior_groups]
    secondary_ids = [row["id"] for row in remaining if group(row) in prior_groups]
    assert len(primary_ids) == cfg["primary_rows"] == 87
    assert len(secondary_ids) == cfg["supplementary_rows_sharing_command_group_with_prior_dev"] == 6
    assert not {group(source[i]) for i in primary_ids} & prior_groups
    assert not {group(row) for row in remaining} & train_groups
    assert not {row["native_label"]["query"] for row in remaining} & {
        r["native_label"]["query"] for r in train + prior}
    assert not {source[i]["native_label"]["ground_truth_command"] for i in primary_ids} & {
        r["native_label"]["ground_truth_command"] for r in train + prior}
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True, trust_remote_code=False,
                                              fix_mistral_regex=False)
    dev_inputs = []
    gold_embedded = []
    train_tools = {r["native_label"]["tool_name"] for r in train}
    for row in remaining:
        assert row["split"] == "train" and row["training_eligible"] is True and row["official_test"] is False
        assert row["target"] == "<output>\n" + row["native_label"]["ground_truth_command"] + "\n</output>"
        original = publisher[row["id"]]
        assert original["model_verification"]["model_output"]["verdict"] == "ACCURATE"
        assert original["terminal_verification"]["category"] == "pass_review"
        assert original["terminal_verification"]["label"] == "PASS_EXECUTED"
        assert tuple(m["role"] for m in row["messages"]) == ("system", "user")
        prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False,
                                                add_generation_prompt=True, enable_thinking=False)
        assert prompt.endswith("<think>\n\n</think>\n\n")
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        assert tokenizer.decode(prompt_ids, skip_special_tokens=False,
                                clean_up_tokenization_spaces=False) == prompt
        assert len(prompt_ids) <= 2048
        dev_inputs.append({"id": row["id"], "messages": row["messages"],
                           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                           "input_ids_sha256": hashlib.sha256(json.dumps(prompt_ids, separators=(",", ":")).encode()).hexdigest(),
                           "prompt_tokens": len(prompt_ids), "official_test": False})
        if row["native_label"]["ground_truth_command"] in "\n".join(m["content"] for m in row["messages"]):
            gold_embedded.append(row["id"])
    assert len(gold_embedded) == cfg["all93_gold_command_embedded_in_prompt"] == 1
    assert set(gold_embedded).isdisjoint(primary_ids)
    assert cfg["primary_gold_command_embedded_in_prompt"] == 0
    assert all(set(x).isdisjoint({"native_label", "target", "ground_truth_command"}) for x in dev_inputs)
    OUT.mkdir(exist_ok=False)
    full_path = OUT / "dev93-private.jsonl"
    full_path.write_text("".join(json.dumps(dict(row, split="dev", training_eligible=False,
                                                  source_official_split="train"), ensure_ascii=False) + "\n"
                                 for row in remaining))
    inputs_path = OUT / "dev-inputs-private.json"
    inputs_path.write_text(json.dumps(dev_inputs, ensure_ascii=False, separators=(",", ":")) + "\n")
    ids_out = OUT / "selection-ids-private.json"
    ids_out.write_text(json.dumps({"all93": remaining_ids, "primary87": primary_ids,
                                   "shared_prior_dev_command_group6": secondary_ids,
                                   "prompt_embeds_gold1": gold_embedded}, indent=2) + "\n")
    report = {
        "status": "FROZEN_93_INPUTS_BEFORE_MODEL_OUTPUTS",
        "config_sha256": sha(CONFIG), "prior_split_manifest_sha256": sha(manifest_path),
        "prior_split_ids_sha256": sha(ids_path), "source_sha256": sha(source_path),
        "raw_publisher_train_sha256": PUBLISHER_SHA,
        "all_unqueried_rows": len(remaining), "primary_rows": len(primary_ids),
        "supplementary_shared_command_rows": len(secondary_ids),
        "primary_tools": len({source[i]["native_label"]["tool_name"] for i in primary_ids}),
        "primary_rows_with_tool_absent_from_train512": sum(source[i]["native_label"]["tool_name"] not in train_tools
                                                           for i in primary_ids),
        "primary_gold_command_embedded_in_prompt": 0,
        "all93_gold_command_embedded_in_prompt": len(gold_embedded),
        "normalized_group_overlap_primary_vs_train_or_prior_dev": 0,
        "official_TEST_rows_opened": 0, "model_calls": 0, "optimizer_steps": 0,
        "file_sha256": {"dev93-private.jsonl": sha(full_path),
                        "dev-inputs-private.json": sha(inputs_path),
                        "selection-ids-private.json": sha(ids_out)},
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "all_unqueried_rows", "primary_rows",
                                             "supplementary_shared_command_rows", "primary_tools",
                                             "primary_rows_with_tool_absent_from_train512",
                                             "official_TEST_rows_opened")}))


if __name__ == "__main__":
    main()
