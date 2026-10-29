#!/usr/bin/env python3
"""Make a source-separated CyBashBench review queue; never certify or run commands."""

import collections
import hashlib
import json
import re
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/benchkit/external-cybashbench-candidates-2026-10-29"
SOURCE = OUT / "cybashbench_tasks.source.jsonl"
PIN = "178c0da1800f9c07311e1b8d6c61dd8104e7b4ae"
URL = f"https://raw.githubusercontent.com/lyptus-research/cyber-task-horizons-data/{PIN}/data/tasks/cybashbench/cybashbench_tasks.jsonl"
EXPECTED_SHA256 = "3ad067b036d8d28cfd8cef23b594c635c7b040ce8494fd5466f9a88184334935"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main():
    assert sha(SOURCE) == EXPECTED_SHA256
    source = [json.loads(line) for line in SOURCE.read_text().splitlines() if line]
    assert len(source) == len({r["task_id"] for r in source}) == 200
    selected = []
    categories = collections.Counter()
    tools = set()
    shell_controls = 0
    for row in source:
        m = row["dataset_task_metadata"]
        # Predeclared structural filter; no Qwen output or gold-matching score is used.
        if not (m["task_type"] == "nl2bash" and m["timing_source"] == "human_reviewed"
                and m["security_category"] in {"web", "forensics", "pwn", "reverse", "crypto"}):
            continue
        command = m["bash_command"]
        parts = shlex.split(command)
        assert parts and m["nl_description"].strip()
        tool = parts[0]
        controls = bool(re.search(r"[;&|`$<>\n\r]", command))
        shell_controls += controls
        categories[m["security_category"]] += 1
        tools.add(tool)
        selected.append({
            "id": "cybash:" + row["task_id"],
            "question": m["nl_description"],
            "gold_command": command,
            "tool": tool,
            "source_dataset": "CyBashBench_via_Lyptus_Research",
            "source_record_id": row["task_id"],
            "source_revision": PIN,
            "source_url": URL,
            "license_spdx": "CC-BY-4.0",
            "evidence_url": URL,
            "target_tool_version": "PENDING_VERSION_REVIEW",
            "review": {"verdict": "PENDING", "reviewer_type": None,
                       "reviewer_name": None, "reviewed_at_utc": None, "rationale": None},
            "publisher_task_type": m["task_type"],
            "publisher_security_category": m["security_category"],
            "publisher_timing_source": m["timing_source"],
            "publisher_timing_source_is_not_label_signoff": True,
            "shell_control_present_for_review": controls,
            "official_test": False,
        })
    selected.sort(key=lambda r: r["source_record_id"])
    assert len(selected) == 37
    # A first static gate found one repeated normalized command; preserve v0
    # separately and keep the first source ID before any model output exists.
    seen_commands = set()
    unique = []
    for row in selected:
        key = " ".join(re.findall(r"[a-z0-9_./:=-]+", row["gold_command"].casefold()))
        if key in seen_commands:
            continue
        seen_commands.add(key)
        unique.append(row)
    selected = unique
    categories = collections.Counter(r["publisher_security_category"] for r in selected)
    tools = {r["tool"] for r in selected}
    shell_controls = sum(r["shell_control_present_for_review"] for r in selected)
    assert len(selected) == 36 and len(tools) == 24
    path = OUT / "source-separated-review-candidates-private.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in selected))
    summary = {
        "status": "EXTERNAL_SOURCE_REVIEW_QUEUE_NOT_FROZEN_HOLDOUT",
        "source": "CyBashBench as distributed in Lyptus Research cyber-task-horizons-data",
        "source_url": URL,
        "source_revision": PIN,
        "source_sha256": sha(SOURCE),
        "source_rows": 200,
        "fixed_selection_rule": "task_type=nl2bash, timing_source=human_reviewed, security_category in web/forensics/pwn/reverse/crypto; then sort by source ID and keep first normalized command",
        "pre_dedup_rows": 37,
        "deduplicated_commands": 1,
        "candidate_rows": len(selected),
        "candidate_tools": len(tools),
        "category_counts": dict(sorted(categories.items())),
        "shell_control_review_flags": shell_controls,
        "candidate_sha256": sha(path),
        "official_TEST_rows": 0,
        "model_calls": 0,
        "human_label_signoffs": 0,
        "limitations": ["Publisher timing_source=human_reviewed describes timing provenance, not semantic command-label approval.",
                        "Publisher commands have not been executed or version-checked here.",
                        "Public source separation does not establish nonexposure during model pretraining.",
                        "Candidate queue is not a sealed holdout and must not be used for model selection yet."],
    }
    dump(OUT / "intake-summary-private.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "candidate_rows", "candidate_tools", "category_counts", "shell_control_review_flags", "model_calls")}, indent=2))


if __name__ == "__main__":
    main()
