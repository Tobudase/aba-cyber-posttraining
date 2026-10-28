#!/usr/bin/env python3
"""Freeze PASS_EXECUTED official TRAIN pilot; never read TEST or execute commands."""

import collections
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/kali-qwen-official-executed-pilot-2026-10-28.json"
OUT = ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28"
RAW_TRAIN = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
RAW_TRAIN_SHA = "93dc4ddff6d9df73bed4b9e92716470e7a73df513f5ca2f1b201c85f2329f909"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rank(text):
    return hashlib.sha256(text.encode()).hexdigest()


def normalized_command(row):
    return " ".join(row["native_label"]["ground_truth_command"].split())


def tool(row):
    return row["native_label"]["tool_name"]


def main():
    cfg = json.loads(CONFIG.read_text())
    assert cfg["status"] == "FROZEN_BEFORE_QWEN_MODEL_OUTPUTS"
    source = ROOT / cfg["source_file"]
    assert digest(source) == cfg["source_sha256"]
    assert digest(RAW_TRAIN) == RAW_TRAIN_SHA
    publisher = {r["custom_id"]: r for r in map(json.loads, RAW_TRAIN.read_text().splitlines())}
    assert len(publisher) == 3504
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    assert len(rows) == cfg["source_rows"] == 3376
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["split"] == "train" and row["official_test"] is False
        assert row["training_eligible"] is True
        assert tuple(m["role"] for m in row["messages"]) == ("system", "user")
        assert row["target"] == "<output>\n" + row["native_label"]["ground_truth_command"] + "\n</output>"
        original = publisher[row["id"]]
        assert original["model_verification"]["model_output"]["verdict"] == "ACCURATE"
        assert original["terminal_verification"]["category"] == "pass_review"
        assert original["terminal_verification"]["ai_review_category"] == "ai_pass_review"
    rows = [row for row in rows if publisher[row["id"]]["terminal_verification"]["label"] ==
            cfg["required_publisher_terminal_label"]]
    assert len(rows) == cfg["filtered_rows_expected"] == 936

    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        grouped[tool(row)][normalized_command(row)].append(row)
    full_train, full_dev = [], []
    for name, commands in grouped.items():
        ordered = sorted(commands, key=lambda command: rank(cfg["split_seed"] + "\0" + name + "\0" + command))
        n_dev = min(max(1, round(len(ordered) * 0.15)), len(ordered) - 1) if len(ordered) > 1 else 0
        for idx, command in enumerate(ordered):
            (full_dev if idx < n_dev else full_train).extend(commands[command])
    assert len(full_train) + len(full_dev) == len(rows)
    assert not {r["id"] for r in full_train} & {r["id"] for r in full_dev}
    assert not {(tool(r), normalized_command(r)) for r in full_train} & {
        (tool(r), normalized_command(r)) for r in full_dev}
    assert {tool(r) for r in full_dev} <= {tool(r) for r in full_train}
    assert not {r["native_label"]["query"] for r in full_train} & {
        r["native_label"]["query"] for r in full_dev}

    pilot_key = lambda row: rank("executed-pilot\0" + row["id"])
    pilot_dev = sorted(full_dev, key=pilot_key)[:cfg["pilot_dev_rows"]]
    dev_tools = {tool(row) for row in pilot_dev}
    paired_train = [row for row in full_train if tool(row) in dev_tools]
    assert len(paired_train) <= cfg["pilot_train_rows"]
    paired_ids = {row["id"] for row in paired_train}
    remaining = sorted((row for row in full_train if row["id"] not in paired_ids), key=pilot_key)
    pilot_train = sorted(paired_train + remaining[:cfg["pilot_train_rows"] - len(paired_train)],
                         key=lambda row: row["id"])
    pilot_dev = sorted(pilot_dev, key=lambda row: row["id"])
    assert len(pilot_train) == 512 and len(pilot_dev) == 128
    assert {tool(row) for row in pilot_dev} <= {tool(row) for row in pilot_train}
    assert not {normalized_command(row) for row in pilot_train} & {normalized_command(row) for row in pilot_dev}

    def project(row, split):
        result = dict(row)
        result.update(split=split, training_eligible=(split == "train"), source_official_split="train",
                      quality=cfg["data_quality_name"])
        return result

    OUT.mkdir(exist_ok=False)
    paths = {}
    for name, subset, split in (("pilot_train.jsonl", pilot_train, "train"),
                                ("pilot_dev.jsonl", pilot_dev, "dev")):
        path = OUT / name
        path.write_text("".join(json.dumps(project(row, split), ensure_ascii=False, separators=(",", ":")) + "\n"
                                for row in subset))
        paths[name] = digest(path)
    ids = {"full_train": sorted(row["id"] for row in full_train),
           "full_dev": sorted(row["id"] for row in full_dev),
           "pilot_train": sorted(row["id"] for row in pilot_train),
           "pilot_dev": sorted(row["id"] for row in pilot_dev)}
    (OUT / "split-ids-private.json").write_text(json.dumps(ids, indent=2) + "\n")
    term_labels = collections.Counter(publisher[row["id"]]["terminal_verification"]["label"]
                                      for row in pilot_train + pilot_dev)
    manifest = {
        "status": "FROZEN_OFFICIAL_TRAIN_ONLY_PILOT_SPLIT",
        "source_sha256": cfg["source_sha256"],
        "raw_publisher_train_sha256": RAW_TRAIN_SHA,
        "config_sha256": digest(CONFIG),
        "source_rows": cfg["source_rows"],
        "filtered_rows": len(rows),
        "full_train_rows": len(full_train),
        "full_dev_rows": len(full_dev),
        "pilot_train_rows": len(pilot_train),
        "pilot_dev_rows": len(pilot_dev),
        "pilot_train_tools": len({tool(row) for row in pilot_train}),
        "pilot_dev_tools": len(dev_tools),
        "pilot_terminal_labels": dict(term_labels),
        "exact_query_overlap": 0,
        "normalized_tool_command_group_overlap": 0,
        "pilot_exact_command_overlap": 0,
        "publisher_model_verdict_accurate_rows": len(pilot_train) + len(pilot_dev),
        "publisher_terminal_pass_review_rows": len(pilot_train) + len(pilot_dev),
        "publisher_terminal_PASS_EXECUTED_rows": len(pilot_train) + len(pilot_dev),
        "independent_expert_gold_rows_claimed": 0,
        "official_TEST_rows_read": 0,
        "commands_executed": 0,
        "model_calls": 0,
        "file_sha256": paths,
        "split_ids_sha256": digest(OUT / "split-ids-private.json"),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: manifest[key] for key in ("status", "full_train_rows", "full_dev_rows",
                                               "pilot_train_rows", "pilot_dev_rows", "pilot_dev_tools",
                                               "pilot_terminal_labels", "official_TEST_rows_read")}, indent=2))


if __name__ == "__main__":
    main()
