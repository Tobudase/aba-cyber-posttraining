#!/usr/bin/env python3
"""Verify released aggregate arithmetic; private predictions are deliberately absent."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/kali-qwen-confirmation-2026-10-28/summary.json"
TRIAGE = ROOT / "results/kali-qwen-confirmation-2026-10-28/mechanical-triage.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    r = json.loads(RESULT.read_text())
    assert r["status"] == "CONFIRMED_UNQUERIED_INTERNAL_DEV_AGGREGATE"
    assert r["model_id"] == "Qwen/Qwen3-8B"
    assert r["prior_train_rows"] == 512 and r["prior_dev_rows"] == 128
    assert r["primary_rows"] == 87 and r["all_unqueried_rows"] == 93
    assert r["primary_gold_command_embedded_in_prompt"] == 0
    assert r["primary_normalized_group_overlap_with_train_or_prior_dev"] == 0
    assert r["primary_rows_with_tool_absent_from_train"] == 22
    assert r["optimizer_steps_this_run"] == r["official_TEST_rows_opened"] == 0
    assert not any(r[k] for k in ("ABA_search_executed", "independent_external_validation",
                                  "automatic_model_promotion"))
    assert sha(ROOT / "configs/kali-qwen-confirmation-93-2026-10-28.json") == r["public_config_sha256"]
    assert sha(ROOT / "scripts/run-kali-qwen-confirmation-worker.py") == r["public_worker_sha256"]
    assert r["private_GPU_receipt_sha256"] and r["private_score_receipt_sha256"]
    sets = r["sets"]
    assert set(sets) == {"primary87", "all93", "primary_tool_absent_from_train22",
                         "all93_without_prompt_embedded_gold92"}
    for name, d in sets.items():
        n = d["rows"]
        for metric, key in (("strict", "strict_correct_count"),
                            ("exact_command", "exact_command_count")):
            t = d["paired"][metric]
            assert sum(t.values()) == n
            assert d["baseline"][key] == t["both_correct"] + t["lost"]
            assert d["post_sft"][key] == t["both_correct"] + t["gained"]
        for phase in ("baseline", "post_sft"):
            p = d[phase]
            assert 0 <= p["strict_correct_count"] <= n
            assert 0 <= p["exact_command_count"] <= n
            assert p["complete_output_blocks"] + p["truncated_rows"] == n
            assert abs(p["format_error"] - 100 * p["truncated_rows"] / n) < 1e-9
    primary = sets["primary87"]
    unseen = sets["primary_tool_absent_from_train22"]
    assert (primary["rows"], primary["baseline"]["strict_correct_count"],
            primary["post_sft"]["strict_correct_count"]) == (87, 18, 26)
    assert (unseen["rows"], unseen["baseline"]["strict_correct_count"],
            unseen["post_sft"]["strict_correct_count"]) == (22, 5, 5)
    assert primary["paired"]["strict"] == {"both_correct": 17, "gained": 9,
                                           "lost": 1, "both_wrong": 60}
    assert r["post_sft_primary_truncated_all_both_wrong"] is True
    audit = json.loads(TRIAGE.read_text())
    assert audit["status"] == "MECHANICAL_TRIAGE_ONLY_HUMAN_REVIEW_PENDING"
    assert audit["case_counts"] == {"gained": 9, "lost": 1, "both_wrong_truncated": 3}
    assert audit["gains_with_tool_present_in_train512"] == 8
    assert audit["gains_with_tool_absent_from_train512"] == 1
    assert audit["gains_exact_gold_command"] == 7
    assert audit["gains_strict_correct_but_not_exact_gold_string"] == 2
    assert audit["losses_with_tool_absent_from_train512"] == 1
    assert audit["truncated_at_cap_without_closed_output_and_with_repeated_fivegram"] == 3
    assert audit["source_prediction_sha256"] == {
        "baseline": r["private_baseline_predictions_sha256"],
        "post_sft": r["private_post_predictions_sha256"]}
    assert audit["individual_case_content_released"] is False
    assert audit["independent_human_semantic_reviews"] == 0
    lengths = audit["token_lengths_all93"]
    assert lengths["baseline"]["median"] == lengths["post_sft"]["median"] == 20
    assert lengths["baseline"]["max"] == 69
    assert lengths["post_sft"]["max"] == 512
    assert lengths["baseline"]["at_512_token_cap"] == 0
    assert lengths["post_sft"]["at_512_token_cap"] == 3
    print(json.dumps({"status": "PUBLIC_AGGREGATE_ARITHMETIC_PASS",
                      "primary_strict": "18/87 -> 26/87", "unseen_tool_strict": "5/22 -> 5/22",
                      "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
