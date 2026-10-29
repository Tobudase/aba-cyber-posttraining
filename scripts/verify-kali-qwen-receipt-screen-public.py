#!/usr/bin/env python3
"""Verify public arithmetic for the TRAIN-receipt screen and SFT ablation."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/kali-qwen-receipt-screen-2026-10-29"


def read(name):
    return json.loads((BASE / name).read_text())


def main():
    screen = read("summary.json")
    coverage = read("coverage-impact.json")
    compare = read("comparison.json")
    counts = screen["counts"]
    assert counts["source_train_rows"] == 512
    assert counts["no_lexical_failure_cue"] + counts["held_for_effect_review"] == 512
    assert counts["independent_human_effect_verdicts"] == 0
    assert screen["candidate_encoded_checks"]["rows"] == counts["no_lexical_failure_cue"]
    assert screen["candidate_encoded_checks"]["scheduled_optimizer_exposures"] == 512
    assert screen["candidate_encoded_checks"]["twice_exposed_rows"] == 111
    assert coverage["train_tools"]["original512"] - coverage["train_tools"]["screened401"] == coverage["train_tools"]["lost_entirely"] == 43
    assert coverage["train_tools"]["held_rows_from_lost_tools"] == 91
    assert coverage["dev_rows_with_tool_absent_from_screened401"] == {"pilot_dev128": 20, "confirmation_primary87": 33}
    for arm in ("original512", "receipt_screen512_steps"):
        assert coverage["scheduled_exposure_tokens"][arm]["optimizer_steps"] == 512
    assert coverage["scheduled_exposure_tokens"]["original512"]["unique_examples"] == 512
    assert coverage["scheduled_exposure_tokens"]["receipt_screen512_steps"]["unique_examples"] == 401
    assert compare["baseline_responses_identical"] is True
    results = compare["results"]
    assert results["original512"]["baseline"]["strict_correct"] == 29
    assert results["receipt_screen401"]["baseline"]["strict_correct"] == 29
    assert results["original512"]["post_sft"]["strict_correct"] == 43
    assert results["receipt_screen401"]["post_sft"]["strict_correct"] == 39
    assert results["original512"]["post_sft"]["exact_gold_command"] == 36
    assert results["receipt_screen401"]["post_sft"]["exact_gold_command"] == 32
    assert results["original512"]["post_sft"]["truncated"] == 0
    assert results["receipt_screen401"]["post_sft"]["truncated"] == 1
    pair = compare["paired_post_strict"]
    assert pair == {"both_correct": 38, "both_wrong": 84, "original_only": 5, "screened_only": 1}
    strata = compare["by_screened_tool_coverage"]
    assert sum(v["rows"] for v in strata.values()) == 128
    assert sum(v["original_post_correct"] for v in strata.values()) == 43
    assert sum(v["screened_post_correct"] for v in strata.values()) == 39
    assert compare["official_TEST_rows"] == screen["official_TEST_rows"] == coverage["official_TEST_rows"] == 0
    print(json.dumps({"status": "PUBLIC_AGGREGATE_ARITHMETIC_PASS", "original_post": "43/128",
                      "screened_post": "39/128", "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
