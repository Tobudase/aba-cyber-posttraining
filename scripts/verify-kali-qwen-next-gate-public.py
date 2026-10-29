#!/usr/bin/env python3
"""Check only the published review/intake aggregate, without private rows."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "results/kali-qwen-next-gate-2026-10-29/summary.json"


def main():
    value = json.loads(PATH.read_text())
    assert value["status"] == "PREPARATION_ONLY_NO_HOLDOUT_ADMISSION"
    review = value["review_packet"]
    assert review["priority_cases"] == 10 and review["followup_cases"] == 42
    assert review["total_cases"] == 52 and review["independent_human_signoffs"] == 0
    ext = value["external_candidate"]
    assert ext["source_rows"] == 200
    assert ext["selected_before_command_dedup"] - ext["duplicate_commands_removed"] == ext["candidate_rows"] == 36
    assert sum(ext["category_counts"].values()) == 36 and ext["candidate_tools"] == 24
    assert ext["gate_status"] == "NOT_ADMITTED"
    assert ext["exact_or_near_prior_overlap_detected"] == 0
    assert ext["gate_issue_counts"] == {"independent_review_missing": 36, "tool_version_unverified": 36}
    assert ext["human_label_signoffs"] == ext["target_tool_versions_verified"] == 0
    assert value["kali_official_TEST_rows"] == value["new_model_calls"] == value["new_optimizer_steps"] == value["new_GPU_jobs"] == 0
    print("Qwen next-gate public aggregate: arithmetic and disclosure checks passed")


if __name__ == "__main__":
    main()
