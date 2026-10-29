#!/usr/bin/env python3
"""Quantify coverage lost by a TRAIN-only receipt screen; no model calls."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def tool(row):
    return row["native_label"]["tool_name"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    old_path = root / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_train.jsonl"
    new_path = root / "data/benchkit/kali-qwen-receipt-screen-2026-10-29/receipt_clear_train_private.jsonl"
    dev_path = old_path.parent / "pilot_dev.jsonl"
    primary_path = root / "data/benchkit/kali-qwen-confirmation-2026-10-28/dev93-private.jsonl"
    selection_path = primary_path.parent / "selection-ids-private.json"
    old, new, dev = rows(old_path), rows(new_path), rows(dev_path)
    old_encoded_path = root / "docs/verification/kali-qwen-official-executed-pilot-2026-10-28/train_encoded_private.json"
    new_encoded_path = new_path.parent / "receipt_clear_512step_schedule_encoded_private.json"
    old_encoded = json.loads(old_encoded_path.read_text())
    new_encoded = json.loads(new_encoded_path.read_text())
    primary_ids = set(json.loads(selection_path.read_text())["primary87"])
    primary = [r for r in rows(primary_path) if r["id"] in primary_ids]
    assert len(old) == 512 and len(new) == 401 and len(dev) == 128 and len(primary) == 87
    assert len(old_encoded) == len(new_encoded) == 512
    assert len({r["id"] for r in old_encoded}) == 512
    assert len({r["id"] for r in new_encoded}) == 401
    assert {r["id"] for r in new} <= {r["id"] for r in old}
    old_tools, new_tools = set(map(tool, old)), set(map(tool, new))
    assert new_tools <= old_tools
    result = {
        "status": "STATIC_COVERAGE_IMPACT_NOT_MODEL_PERFORMANCE",
        "source_sha256": {"old_train512": sha(old_path), "screened_train401": sha(new_path),
                          "old_encoded512": sha(old_encoded_path), "new_schedule_encoded512": sha(new_encoded_path),
                          "pilot_dev128": sha(dev_path), "confirmation93": sha(primary_path),
                          "primary_selection": sha(selection_path)},
        "train_tools": {"original512": len(old_tools), "screened401": len(new_tools),
                        "lost_entirely": len(old_tools - new_tools),
                        "held_rows_from_lost_tools": sum(tool(r) in old_tools - new_tools for r in old)},
        "dev_rows_with_tool_absent_from_screened401": {"pilot_dev128": sum(tool(r) not in new_tools for r in dev),
                                                       "confirmation_primary87": sum(tool(r) not in new_tools for r in primary)},
        "scheduled_exposure_tokens": {
            label: {"optimizer_steps": len(records), "unique_examples": len({r["id"] for r in records}),
                    "prompt_tokens": sum(r["prompt_tokens"] for r in records),
                    "supervised_target_tokens": sum(r["target_tokens"] for r in records),
                    "total_input_tokens": sum(len(r["input_ids"]) for r in records)}
            for label, records in (("original512", old_encoded), ("receipt_screen512_steps", new_encoded))},
        "interpretation_limit": "This filter changes tool coverage and unique-row exposure, so any SFT comparison is not an isolated test of semantic label quality.",
        "model_calls": 0, "optimizer_steps": 0, "official_TEST_rows": 0,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
