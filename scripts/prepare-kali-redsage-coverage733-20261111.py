#!/usr/bin/env python3
"""Freeze a broad, publisher-verified TRAIN coverage control before P07 outputs.

Run with the pinned Transformers 4.57.6 tokenizer. The extra 95 records are
selected without consulting any model predictions or development scores.
"""

import datetime
import gzip
import hashlib
import json
import re
from pathlib import Path

from transformers import AutoTokenizer
from kali_publisher_sft_recipe import validate_recipe


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data/benchkit"
STUDY = BENCH / "kali-redsage-aba-publisher-v2-2026-11-10"
SOURCE = BENCH / "kali-screened/train.jsonl"
PUBLISHER = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
TOKENIZER = ROOT / ".tools/model-tokenizer/redsage-k-843e2e3096e7"
FINAL_INPUTS = BENCH / "kali-redsage-aba-final64-2026-11-10/inputs-private.json.gz"
WORKER = ROOT / "scripts/run-kali-redsage-aba-candidate-worker-v2-20261110.py"
RECIPE = ROOT / "scripts/kali_publisher_sft_recipe.py"
OUT = STUDY / "P07"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return gzip.compress(raw, mtime=0), hashlib.sha256(raw).hexdigest()


def normalized(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def command_key(row):
    label = row["native_label"]
    return label["tool_name"], normalized(label["ground_truth_command"])


def prompt_key(row):
    return normalized(" ".join(m["content"] for m in row["messages"] if m["role"] == "user"))


def main():
    assert not OUT.exists(), "Never replace a frozen P07 protocol"
    assert sha(PUBLISHER) == "93dc4ddff6d9df73bed4b9e92716470e7a73df513f5ca2f1b201c85f2329f909"
    p05_dir = STUDY / "P05"
    p05 = json.loads(gzip.decompress((p05_dir / "payload-private.json.gz").read_bytes()))
    old_protocol = json.loads((p05_dir / "protocol-private.json").read_text())
    old_rows = p05["train_rows"]
    assert len(old_rows) == len({r["id"] for r in old_rows}) == 638
    source = {r["id"]: r for r in map(json.loads, SOURCE.read_text().splitlines())}
    publisher = {r["custom_id"]: r for r in map(json.loads, PUBLISHER.read_text().splitlines())}
    verified = {i for i, row in publisher.items()
                if row["terminal_verification"]["label"] == "PASS_EXECUTED"
                and row["model_verification"]["model_output"]["verdict"] == "ACCURATE"}
    assert len(verified) == 954
    final = json.loads(gzip.decompress(FINAL_INPUTS.read_bytes()))["holdout"]
    assert len(final) == 64 and all(set(r) == {"id", "native_messages"} for r in final)
    old_ids = {r["id"] for r in old_rows}
    protected = {r["id"] for r in p05["dev1"] + p05["dev2"] + p05["anchors"] + final}
    assert not old_ids & protected
    protected_commands = {command_key(source[i]) for i in protected if i in source}
    protected_prompts = {prompt_key(source[i]) for i in protected if i in source}
    eligible = verified & set(source) - old_ids - protected
    selected = {}
    excluded_same_command = 0
    excluded_duplicate_new_command = 0
    for i in sorted(eligible):
        row = source[i]
        key = command_key(row)
        if key in protected_commands:
            excluded_same_command += 1
            continue
        assert prompt_key(row) not in protected_prompts
        if key in selected:
            excluded_duplicate_new_command += 1
            continue
        selected[key] = i
    new_ids = list(selected.values())
    assert len(eligible) == 106
    assert len(new_ids) == 95
    assert excluded_same_command == 8 and excluded_duplicate_new_command == 3
    assert not {prompt_key(source[i]) for i in old_ids} & {prompt_key(source[i]) for i in new_ids}
    assert len({prompt_key(source[i]) for i in old_ids | set(new_ids)}) == 733
    assert len({command_key(source[i]) for i in new_ids} & protected_commands) == 0
    tok = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True,
                                          trust_remote_code=False, fix_mistral_regex=False)
    assert tok.eos_token_id == 151645 and tok.eos_token == "<|im_end|>"
    existing = json.loads((BENCH / "kali-redsage-publisher-sft638-2026-11-10/train-encoded-private.json").read_text())
    assert {r["id"] for r in existing} == old_ids
    assert {r["id"]: r for r in existing} == {r["id"]: r for r in old_rows}
    for row in existing:
        src = source[row["id"]]
        prompt = tok.apply_chat_template(src["messages"], tokenize=False, add_generation_prompt=True)
        completion = "\n</think>\n\n" + src["target"]
        assert tok.encode(prompt, add_special_tokens=False) + tok.encode(completion, add_special_tokens=False) + [tok.eos_token_id] == row["input_ids"]
    encoded = []
    for i in new_ids:
        src, original = source[i], publisher[i]
        assert src["split"] == "train" and src["training_eligible"] is True and src["official_test"] is False
        assert src["native_label"]["ground_truth_command"] == original["ground_truth_command"]
        assert src["target"] == "<output>\n" + original["ground_truth_command"] + "\n</output>"
        prompt = tok.apply_chat_template(src["messages"], tokenize=False, add_generation_prompt=True)
        assert prompt.endswith("<think>")
        completion = "\n</think>\n\n" + src["target"]
        prompt_ids = tok.encode(prompt, add_special_tokens=False)
        target_ids = tok.encode(completion, add_special_tokens=False)
        ids = prompt_ids + target_ids + [tok.eos_token_id]
        assert len(ids) <= 2048 and tok.decode(ids, skip_special_tokens=False,
                                                 clean_up_tokenization_spaces=False) == prompt + completion + tok.eos_token
        encoded.append({"id": i, "split": "train", "training_eligible": True,
                        "official_test": False, "publisher_terminal_PASS_EXECUTED": True,
                        "publisher_model_ACCURATE": True, "input_ids": ids,
                        "labels": [-100] * len(prompt_ids) + target_ids + [tok.eos_token_id],
                        "prompt_tokens": len(prompt_ids), "target_tokens": len(target_ids) + 1})
    rows = old_rows + encoded
    assert len(rows) == len({r["id"] for r in rows}) == 733
    old_tools = {source[i]["native_label"]["tool_name"] for i in old_ids}
    new_tools = {source[i]["native_label"]["tool_name"] for i in new_ids}
    assert len(new_tools - old_tools) == 31
    payload_bytes, payload_sha = packed({"train_rows": rows, "dev1": p05["dev1"],
                                         "dev2": p05["dev2"], "anchors": p05["anchors"]})
    encoded_bytes = (json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    protocol = dict(old_protocol)
    optimizer = dict(old_protocol["optimizer"])
    optimizer["max_optimizer_steps"] = 733
    validate_recipe(optimizer, rows)
    protocol.update({"candidate_id": "P07", "candidate_recipe": {
        "rows": "publisher733_broad_coverage", "lr": 1e-5, "seed": 42},
        "training_rows": 733, "optimizer": optimizer,
        "pod_runtime_seconds": 3600, "queue_deadline_seconds": 7200,
        "payload_sha256": payload_sha,
        "payload_gzip_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "encoded_sha256": hashlib.sha256(encoded_bytes).hexdigest(),
        "worker_sha256": sha(WORKER), "recipe_sha256": sha(RECIPE),
        "prepared_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "official_TEST_rows": 0, "model_promotion_allowed": False,
        "scope": "Operator exploration: 638 matched publisher rows plus 95 new verified diverse TRAIN rows; exposed 128 TRAIN-source DEV; no TEST/final64 outputs"})
    OUT.mkdir(parents=True)
    (OUT / "payload-private.json.gz").write_bytes(payload_bytes)
    (OUT / "train-encoded-private.json").write_bytes(encoded_bytes)
    protocol_path = OUT / "protocol-private.json"
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    freeze = {"status": "BROAD_COVERAGE_CONTROL_FROZEN_BEFORE_OUTPUTS",
              "candidate_id": "P07", "old_training_rows": 638, "new_training_rows": 95,
              "training_rows": 733, "old_training_tools": len(old_tools),
              "new_tool_types": len(new_tools - old_tools),
              "dev_rows": 128, "final64_used": False, "official_TEST_rows": 0,
              "publisher_silver_not_expert_gold": True,
              "selection_rule": "All remaining screened publisher PASS_EXECUTED/ACCURATE TRAIN, excluding protected IDs and protected tool+command groups; one lexicographically first ID per new tool+command group",
              "eligible_before_group_exclusion": len(eligible),
              "excluded_protected_command_group": excluded_same_command,
              "excluded_duplicate_new_command_group": excluded_duplicate_new_command,
              "source_sha256": sha(SOURCE), "publisher_sha256": sha(PUBLISHER),
              "tokenizer_json_sha256": sha(TOKENIZER / "tokenizer.json"),
              "old_payload_sha256": sha(p05_dir / "payload-private.json.gz"),
              "final_inputs_sha256": sha(FINAL_INPUTS),
              "dev1_references_sha256": sha(BENCH / "kali-redsage-publisher-holdout-2026-11-10/references-private.json"),
              "dev2_references_sha256": sha(BENCH / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"),
              "protocol_sha256": sha(protocol_path), "payload_gzip_sha256": sha(OUT / "payload-private.json.gz")}
    (OUT / "freeze-manifest-private.json").write_text(json.dumps(freeze, indent=2) + "\n")
    print(json.dumps({k: freeze[k] for k in ("status", "training_rows", "new_training_rows",
                                                 "new_tool_types", "dev_rows", "official_TEST_rows", "final64_used")}))


if __name__ == "__main__":
    main()
