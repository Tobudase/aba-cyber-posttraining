#!/usr/bin/env python3
"""Freeze a publisher-TRAIN internal holdout before RedSage model outputs.

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
OUT = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
SOURCE_SHA = "93dc4ddff6d9df73bed4b9e92716470e7a73df513f5ca2f1b201c85f2329f909"
SEED = "redsage-publisher-train-internal-holdout-v1-2026-11-10"


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
    used = [source[i] for i in train_ids | old_dev_ids]
    used_groups = {group(r) for r in used}
    used_commands = {r["native_label"]["ground_truth_command"].strip() for r in used}
    used_queries = {r["native_label"]["query"] for r in used}
    train_tools = {source[i]["native_label"]["tool_name"] for i in train_ids}
    pool = []
    for row in source.values():
        if row["id"] in train_ids | old_dev_ids:
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
    assert len(pool) == 226
    # Eight tool-unseen rows are diagnostic; the other 56 estimate transfer to
    # publisher tools represented in the prospective 638-row training set.
    seen = sorted((r for r in pool if r["native_label"]["tool_name"] in train_tools), key=rank)
    unseen = sorted((r for r in pool if r["native_label"]["tool_name"] not in train_tools), key=rank)
    assert len(seen) == 214 and len(unseen) == 12
    selected = []
    for rows, limit in ((seen, 56), (unseen, 8)):
        for row in rows:
            if group(row) not in {group(r) for r in selected}:
                selected.append(row)
            if len(selected) == (56 if limit == 56 else 64):
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
        "status": "FROZEN_BEFORE_REDSAGE_PUBLISHER_HOLDOUT_OUTPUTS",
        "source_official_split": "train", "official_TEST_rows": 0,
        "publisher_sha256": sha(PUBLISHER), "screened_source_sha256": sha(SOURCE),
        "prior_split_sha256": sha(PRIOR), "seed": SEED,
        "prospective_training_ids": 638, "prior_internal_dev_ids_excluded": 64,
        "pool_after_filters": len(pool), "holdout_rows": len(selected),
        "train_seen_tool_rows": 56, "train_unseen_tool_rows": 8,
        "train_dev_id_overlap": 0, "train_dev_group_overlap": 0,
        "prior_dev_id_overlap": 0, "dev_gold_in_worker_payload": False,
        "publisher_silver_not_expert_gold": True,
        "source_separated": False, "model_promotion_allowed": False,
        "training_rows_executed": 0, "model_outputs": 0,
        "inputs_uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "inputs_gzip_sha256": sha(OUT / "inputs-private.json.gz"),
        "references_sha256": sha(OUT / "references-private.json"),
        "scoring_plan": "native KaliBench score_one, strict_option_values secondary, paired base vs C13; no command execution",
        "limitation": "Publisher TRAIN internal holdout, adaptively chosen after C13 DEV results; no independent expert signoff and no official leaderboard result.",
    }
    write(OUT / "freeze-manifest-private.json", manifest)
    print(json.dumps({k: manifest[k] for k in (
        "status", "prospective_training_ids", "holdout_rows", "train_seen_tool_rows",
        "train_unseen_tool_rows", "official_TEST_rows", "dev_gold_in_worker_payload")}, indent=2))


if __name__ == "__main__":
    main()
