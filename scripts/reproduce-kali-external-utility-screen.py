#!/usr/bin/env python3
"""Reproduce aggregate syntax screening from the pinned public source; execute nothing."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import shlex


ROOT = Path(__file__).resolve().parents[1]


def clean(text):
    return " ".join(text.split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_json", type=Path, help="Downloaded pinned linuxcommands.json")
    args = parser.parse_args()
    protocol = json.loads((ROOT / "configs/kali-external-utility-selection-2026-10-28.json").read_text())
    rules = protocol["selection"]
    source_bytes = args.source_json.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == protocol["source_sha256"]
    source = json.loads(source_bytes)
    eligible = []
    rejected = collections.Counter()
    for index, row in enumerate(source):
        question = clean(row["input"])
        raw_command = row["output"]
        command = clean(raw_command)
        if not question or not command or len(question) > rules["max_input_chars"] or len(command) > rules["max_output_chars"]:
            rejected["length_or_empty"] += 1
            continue
        if any(char in raw_command for char in rules["forbidden_command_characters"]):
            rejected["shell_character"] += 1
            continue
        try:
            argv = shlex.split(command)
        except ValueError:
            rejected["shlex"] += 1
            continue
        if not argv or argv[0] not in rules["approved_first_token"]:
            rejected["family"] += 1
            continue
        if rules["forbidden_absolute_or_home_paths"] and any(arg.startswith(("/", "~")) for arg in argv):
            rejected["absolute_or_home_path"] += 1
            continue
        if any(re.search(r"[A-Za-z]+://", arg) for arg in argv):
            rejected["url"] += 1
            continue
        if any(arg.lower() in rules["forbidden_command_words"] or "-exec" in arg.lower() or "-delete" in arg.lower() for arg in argv):
            rejected["forbidden_word"] += 1
            continue
        pair_hash = hashlib.sha256((question + "\0" + command).encode()).hexdigest()
        eligible.append((pair_hash, index, argv[0], command))

    selected = []
    seen_commands = set()
    per_family = collections.Counter()
    for item in sorted(eligible):
        _, _, family, command = item
        if command in seen_commands or per_family[family] >= rules["max_per_first_token"]:
            continue
        selected.append(item)
        seen_commands.add(command)
        per_family[family] += 1
        if len(selected) == rules["max_total"]:
            break

    result = {
        "source_rows": len(source),
        "syntactic_eligible_rows": len(eligible),
        "rejected_by_first_reason": dict(rejected),
        "selected_rows": len(selected),
        "selected_family_counts": dict(per_family),
    }
    published = json.loads((ROOT / "results/kali-external-utility-intake-2026-10-28/summary.json").read_text())
    assert all(result[key] == published[key] for key in result)
    print(json.dumps({"status": "PASS_SOURCE_SCREEN_REPRODUCTION", **result}, indent=2))


if __name__ == "__main__":
    main()
