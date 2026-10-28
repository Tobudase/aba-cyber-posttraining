#!/usr/bin/env python3
"""Static, read-only audit of a frozen KaliBench TRAIN-only Qwen pilot.

The private outputs contain dataset IDs, questions, and gold commands. Publish
only the aggregate JSON. This program never executes a benchmark command,
queries a model, or reads the official TEST split.
"""

import argparse
import collections
import hashlib
import json
import shlex
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def normalized(text):
    return " ".join(text.split())


def normalized_query(row):
    return normalized(row["native_label"]["query"]).casefold()


def command_key(row):
    return row["native_label"]["tool_name"], normalized(row["native_label"]["ground_truth_command"])


def stable_rank(identifier):
    return hashlib.sha256(("train512-static-review-v1\0" + identifier).encode()).hexdigest()


def has_unquoted_shell_control(text):
    """Flag shell control/redirection characters outside simple quotes only."""
    quote = None
    escaped = False
    for char in text:
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif char == quote:
            quote = None
        elif char in ("'", '"') and quote is None:
            quote = char
        elif quote is None and char in ";|<>&":
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-summary", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    data = root / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28"
    train_path = data / "pilot_train.jsonl"
    dev_path = data / "pilot_dev.jsonl"
    manifest_path = data / "manifest.json"
    raw_path = root / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
    selection_path = root / "data/benchkit/kali-qwen-confirmation-2026-10-28/selection-ids-private.json"
    confirm_path = root / "data/benchkit/kali-qwen-confirmation-2026-10-28/dev93-private.jsonl"

    manifest = json.loads(manifest_path.read_text())
    assert sha(train_path) == manifest["file_sha256"]["pilot_train.jsonl"]
    assert sha(dev_path) == manifest["file_sha256"]["pilot_dev.jsonl"]
    assert sha(raw_path) == manifest["raw_publisher_train_sha256"]
    train, dev = load_jsonl(train_path), load_jsonl(dev_path)
    raw = {r["custom_id"]: r for r in load_jsonl(raw_path)}
    selection = json.loads(selection_path.read_text())
    primary_ids = set(selection["primary87"])
    primary = [r for r in load_jsonl(confirm_path) if r["id"] in primary_ids]
    assert len(train) == 512 and len(dev) == 128 and len(primary) == 87
    assert len(raw) == 3504
    assert len({r["id"] for r in train + dev + primary}) == 727
    assert all(r["source_official_split"] == "train" and not r["official_test"] for r in train + dev + primary)

    tools = collections.Counter(r["native_label"]["tool_name"] for r in train)
    command_groups = collections.Counter(command_key(r) for r in train)
    queries = collections.Counter(normalized_query(r) for r in train)
    flags = collections.Counter()
    review = []
    for row in train:
        identifier = row["id"]
        label = row["native_label"]
        gold = label["ground_truth_command"]
        query = label["query"]
        source = raw[identifier]
        assert row["split"] == "train" and row["training_eligible"] is True
        assert [m["role"] for m in row["messages"]] == ["system", "user"]
        assert row["target"] == "<output>\n" + gold + "\n</output>"
        assert row["quality"] == "PUBLISHER_MODEL_VERIFIED_AND_TERMINAL_EXECUTED_SUCCESSFULLY_NOT_EXPERT_GOLD"
        assert label["tool_name"] == source["tool_name"]
        assert query == source["query"] and gold == source["ground_truth_command"]
        assert label["optional_args"] == source["optional_args"]
        assert label["positional_args"] == source["positional_args"]
        assert source["model_verification"]["model_output"]["verdict"] == "ACCURATE"
        assert source["terminal_verification"]["category"] == "pass_review"
        assert source["terminal_verification"]["ai_review_category"] == "ai_pass_review"
        assert source["terminal_verification"]["label"] == "PASS_EXECUTED"

        cues = []
        if gold.casefold() in query.casefold():
            cues.append("gold_command_verbatim_substring_in_query")
        if command_groups[command_key(row)] > 1:
            cues.append("repeated_tool_command_group_within_train")
        if queries[normalized_query(row)] > 1:
            cues.append("repeated_normalized_query_within_train")
        if has_unquoted_shell_control(gold):
            cues.append("unquoted_shell_control_or_redirection_review")
        try:
            shlex.split(gold)
        except ValueError:
            cues.append("posix_shlex_parse_error_review")
        if len(gold) >= 120:
            cues.append("long_gold_command_at_least_120_chars")
        if tools[label["tool_name"]] == 1:
            cues.append("tool_has_single_train_example")
        flags.update(cues)
        review.append({
            "id": identifier,
            "tool": label["tool_name"],
            "question": query,
            "gold_command": gold,
            "source_official_split": "train",
            "review_cues": cues,
            "reviewer": None,
            "reviewed_at": None,
            "semantic_verdict": "PENDING_INDEPENDENT_HUMAN_REVIEW",
            "tool_version_checked": None,
            "documentation_or_fixture_evidence": None,
            "corrected_command_if_needed": None,
            "notes": None,
        })

    def overlap(other):
        return {
            "normalized_query": len(set(map(normalized_query, train)) & set(map(normalized_query, other))),
            "normalized_tool_command_group": len(set(map(command_key, train)) & set(map(command_key, other))),
            "tools_absent_from_train": sum(r["native_label"]["tool_name"] not in tools for r in other),
        }

    high_cues = {
        "gold_command_verbatim_substring_in_query",
        "repeated_tool_command_group_within_train",
        "repeated_normalized_query_within_train",
        "unquoted_shell_control_or_redirection_review",
        "posix_shlex_parse_error_review",
        "long_gold_command_at_least_120_chars",
    }
    review.sort(key=lambda r: (-sum(c in high_cues for c in r["review_cues"]),
                               -len(r["review_cues"]), stable_rank(r["id"])))
    priority = [r["id"] for r in review[:64]]
    deterministic_sample = [r["id"] for r in sorted(review, key=lambda r: stable_rank(r["id"]))[:32]]
    private = {
        "status": "STATIC_AUDIT_COMPLETE_INDEPENDENT_HUMAN_REVIEW_PENDING",
        "source_hashes": {"train512": sha(train_path), "dev128": sha(dev_path),
                          "publisher_train3504": sha(raw_path), "manifest": sha(manifest_path),
                          "confirmation93": sha(confirm_path), "primary_selection": sha(selection_path)},
        "method": "Read-only structural/provenance/lexical checks; cues are not semantic error findings.",
        "priority64_ids": priority,
        "deterministic_sample32_ids": deterministic_sample,
        "review_queue_all512": review,
    }
    public = {
        "status": private["status"],
        "source_sha256": {"train512": sha(train_path), "dev128": sha(dev_path),
                          "publisher_train3504": sha(raw_path)},
        "scope": "KaliBench official TRAIN only; no official TEST, command execution, model call, or new training",
        "row_counts": {"train": 512, "pilot_dev": 128, "confirmation_primary": 87},
        "provenance": {"publisher_model_accurate": 512, "publisher_terminal_PASS_EXECUTED": 512,
                       "independently_human_verified": 0},
        "structure": {"tools": len(tools), "tools_with_one_train_row": sum(v == 1 for v in tools.values()),
                      "unique_normalized_queries": len(queries),
                      "unique_normalized_tool_command_groups": len(command_groups),
                      "repeated_tool_command_groups": sum(v > 1 for v in command_groups.values()),
                      "rows_in_repeated_tool_command_groups": sum(v for v in command_groups.values() if v > 1),
                      "target_format_mismatches": 0},
        "lexical_review_cues": dict(sorted(flags.items())),
        "cross_split_overlap": {"pilot_dev128": overlap(dev), "confirmation_primary87": overlap(primary)},
        "review_plan": {"priority_queue_rows": 64, "deterministic_sample_rows": 32,
                        "human_verdicts_recorded": 0,
                        "interpretation": "Every TRAIN row is queued privately; priority/sample lists are review aids, not certified labels."},
        "limitations": [
            "Substring, shell-character and shlex flags are heuristics; they do not prove a bad label or command behavior.",
            "Publisher execution and AI review do not replace independent semantic review with tool-version evidence.",
            "DEV and confirmation rows share the publisher source family; neither is an independent-source test.",
            "The 87-row confirmation has already been queried and remains a development diagnostic.",
        ],
    }
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_summary.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, ensure_ascii=False, indent=2) + "\n")
    args.public_summary.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(public, indent=2))


if __name__ == "__main__":
    main()
