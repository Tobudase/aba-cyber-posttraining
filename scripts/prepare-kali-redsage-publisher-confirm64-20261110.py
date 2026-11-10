#!/usr/bin/env python3
"""Freeze a second publisher-TRAIN panel before RedSage confirmation outputs.

Dataset shell commands are inert labels; this script never executes them.
"""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from benchkit import kali_prompts


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/benchkit/kali-screened/train.jsonl"
PUBLISHER = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
PRIOR = ROOT / "data/benchkit/kali-qwen-expanded-2026-10-30/selection-ids-private.json"
FIRST = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
OUT = ROOT / "data/benchkit/kali-redsage-publisher-confirm64-2026-11-10"
SOURCE_SHA = "93dc4ddff6d9df73bed4b9e92716470e7a73df513f5ca2f1b201c85f2329f909"
SEED = "redsage-publisher-train-unqueried-confirm-v1-2026-11-10"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def group(row):
    label = row["native_label"]
    return label["tool_name"], " ".join(label["ground_truth_command"].split())


def rank(row):
    return digest(SEED + "\0" + row["id"])


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main():
    assert not OUT.exists(), "The holdout is immutable; never regenerate in place"
    assert sha(PUBLISHER) == SOURCE_SHA
    source = {r["id"]: r for r in map(json.loads, SOURCE.read_text().splitlines())}
    publisher = {r["custom_id"]: r for r in map(json.loads, PUBLISHER.read_text().splitlines())}
    prior = json.loads(PRIOR.read_text())
    assert len(source) == 3376 and len(publisher) == 3504
    assert {k: len(v) for k, v in prior.items()} == {
        "old_ai505_train": 505, "added_train133": 133, "fresh_dev64": 64}
    train_ids = set(prior["old_ai505_train"] + prior["added_train133"])
    old_dev_ids = set(prior["fresh_dev64"])
    assert len(train_ids) == 638 and not train_ids & old_dev_ids
    first_ids = {r["custom_id"] for r in json.loads((FIRST / "references-private.json").read_text())}
    assert len(first_ids) == 64 and not first_ids & (train_ids | old_dev_ids)
    used = [source[i] for i in train_ids | old_dev_ids | first_ids]
    used_groups = {group(r) for r in used}
    used_commands = {r["native_label"]["ground_truth_command"].strip() for r in used}
    used_queries = {r["native_label"]["query"] for r in used}
    train_tools = {source[i]["native_label"]["tool_name"] for i in train_ids}
    pool = []
    for row in source.values():
        if row["id"] in train_ids | old_dev_ids | first_ids:
            continue
        label = row["native_label"]
        original = publisher[row["id"]]
        if original["terminal_verification"]["label"] != "PASS_EXECUTED":
            continue
        if original["model_verification"]["model_output"]["verdict"] != "ACCURATE":
            continue
        if label["ground_truth_command"] in label["query"]:
            continue
        if group(row) in used_groups or label["ground_truth_command"].strip() in used_commands:
            continue
        if label["query"] in used_queries:
            continue
        assert row["split"] == "train" and row["official_test"] is False
        pool.append(row)
    assert len(pool) == 160
    # All four remaining tool-unseen rows are included as a small diagnostic.
    seen = sorted((r for r in pool if r["native_label"]["tool_name"] in train_tools), key=rank)
    unseen = sorted((r for r in pool if r["native_label"]["tool_name"] not in train_tools), key=rank)
    assert len(seen) == 156 and len(unseen) == 4
    selected = []
    for rows, limit in ((seen, 60), (unseen, 4)):
        for row in rows:
            if group(row) not in {group(r) for r in selected}:
                selected.append(row)
            if len(selected) == (60 if limit == 60 else 64):
                break
    assert len(selected) == 64 and len({group(r) for r in selected}) == 64
    selected.sort(key=lambda r: r["id"])
    native, labels = kali_prompts([publisher[r["id"]] for r in selected])
    assert set(native) == {r["id"] for r in selected} == set(labels)
    for row in selected:
        assert native[row["id"]] == row["messages"]
        assert labels[row["id"]]["ground_truth_command"] == row["native_label"]["ground_truth_command"]
    inputs = [{"id": r["id"], "native_messages": native[r["id"]]}
              for r in selected]
    references = [dict(publisher[r["id"]], source_official_split="train",
                       training_eligible=False) for r in selected]
    assert all(set(r) == {"id", "native_messages"} for r in inputs)
    assert all("ground_truth_command" not in json.dumps(r) for r in inputs)
    OUT.mkdir(parents=True)
    raw = json.dumps({"holdout": inputs}, ensure_ascii=False, separators=(",", ":")).encode()
    (OUT / "inputs-private.json.gz").write_bytes(gzip.compress(raw))
    write(OUT / "references-private.json", references)
    manifest = {
        "status": "FROZEN_BEFORE_REDSAGE_PUBLISHER_CONFIRM64_OUTPUTS",
        "source_official_split": "train", "official_TEST_rows": 0,
        "publisher_sha256": sha(PUBLISHER), "screened_source_sha256": sha(SOURCE),
        "prior_split_sha256": sha(PRIOR),
        "first_holdout_references_sha256": sha(FIRST / "references-private.json"),
        "seed": SEED,
        "prospective_training_ids": 638, "prior_internal_dev_ids_excluded": 64,
        "pool_after_filters": len(pool), "holdout_rows": len(selected),
        "train_seen_tool_rows": 60, "train_unseen_tool_rows": 4,
        "train_dev_id_overlap": 0, "train_dev_group_overlap": 0,
        "prior_dev_id_overlap": 0, "dev_gold_in_worker_payload": False,
        "first_holdout_id_and_group_overlap": 0,
        "publisher_silver_not_expert_gold": True,
        "source_separated": False, "model_promotion_allowed": False,
        "training_rows_executed": 0, "model_outputs": 0,
        "inputs_uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "inputs_gzip_sha256": sha(OUT / "inputs-private.json.gz"),
        "references_sha256": sha(OUT / "references-private.json"),
        "scoring_plan": "native KaliBench score_one, strict_option_values secondary, paired base vs publisher SFT638; no command execution",
        "limitation": "Publisher TRAIN confirmation selected after first holdout results, with fixed seed and no model queries on selected rows; no independent expert signoff or official leaderboard result.",
    }
    write(OUT / "freeze-manifest-private.json", manifest)
    print(json.dumps({k: manifest[k] for k in (
        "status", "prospective_training_ids", "holdout_rows", "train_seen_tool_rows",
        "train_unseen_tool_rows", "official_TEST_rows", "dev_gold_in_worker_payload")}, indent=2))


if __name__ == "__main__":
    main()
