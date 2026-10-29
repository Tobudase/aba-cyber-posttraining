#!/usr/bin/env python3
"""Check arithmetic and disclosure gates in the published AI-review aggregate."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "results/kali-qwen-ai-review-2026-10-29/comparison.json"


def main():
    row = json.loads(PATH.read_text())
    assert row["status"] == "EXPLORATORY_EXPOSED_INTERNAL_DEV_COMPARISON_NOT_BLIND"
    assert row["baseline_responses_identical"] is True
    assert row["training_unique_rows"] == {"original512": 512, "receipt_screen401": 401, "ai_review505": 505}
    assert row["training_optimizer_steps"] == 512
    assert row["official_TEST_rows"] == row["independent_human_signoffs"] == 0
    assert row["automatic_model_promotion"] is False
    assert sum(row["review_counts"].values()) == 512
    assert row["review_counts"]["AI_QUARANTINE_SOURCE_CONFLICT"] == 7
    results = row["results"]
    assert {arm: results[arm]["baseline"]["strict_correct"] for arm in results} == {
        "original512": 29, "receipt_screen401": 29, "ai_review505": 29
    }
    assert {arm: results[arm]["post_sft"]["strict_correct"] for arm in results} == {
        "original512": 43, "receipt_screen401": 39, "ai_review505": 44
    }
    paired = row["paired_original_vs_ai_review_post_strict"]
    assert sum(paired.values()) == 128
    assert paired["both_correct"] + paired["original_only"] == 43
    assert paired["both_correct"] + paired["ai_review_only"] == 44
    assert results["original512"]["post_sft"]["exact_gold_command"] == 36
    assert results["ai_review505"]["post_sft"]["exact_gold_command"] == 36
    print("Published AI-review aggregate: arithmetic and disclosure checks passed")


if __name__ == "__main__":
    main()
