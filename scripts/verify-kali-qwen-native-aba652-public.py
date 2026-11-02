#!/usr/bin/env python3
"""Verify public matched-SFT arithmetic and disclosure limits."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-native-aba652-2026-11-02"
REPORT = ROOT / "docs/KALI_QWEN_NATIVE_ABA652_RESULT_ZH_2026-11-02.md"


def main():
    d = json.loads((OUT / "aggregate.json").read_text())
    assert d["status"] == "COMPLETE_NATIVE_ABA_DATA_MATCHED_QWEN_SFT_ENGINEERING"
    assert d["native_ABA_controller_executed"] is True
    assert d["native_ABA_candidate_rows"] == 16 and d["frozen_fixture_accepted_into_SFT"] == 14
    assert d["posthoc_sensitive_rows_excluded"] == 2
    assert d["common_publisher_TRAIN_rows"] == 638
    assert d["control_extra_publisher_TRAIN_repeats"] == d["treatment_extra_native_ABA_rows"] == 14
    assert d["optimizer_steps_each_arm"] == 652 and d["optimizer_steps_total"] == 1304
    assert d["length_match"]["sum_input_token_control"] == 5551
    assert d["length_match"]["sum_input_token_treatment"] == 5552
    assert d["length_match"]["sum_supervised_target_tokens_control"] == d["length_match"]["sum_supervised_target_tokens_treatment"] == 211
    assert d["validation16_historically_exposed"] is True and d["independent_gold_rows"] == d["official_TEST_rows"] == 0
    assert d["owned_GPU_resources_cleaned"] is True and d["model_promotion"] is False
    expected = {"validation16": (8, 8, 8, 0, 0), "old_dev64": (None, 21, 22, 1, 0),
                "utility_primary36": (None, 18, 18, 0, 0), "utility_all108": (None, 66, 66, 0, 0)}
    for name, (base, control, treatment, gained, lost) in expected.items():
        x = d["sets"][name]
        if base is not None:
            assert x["base"]["strict_correct"] == base
        assert x["control"]["strict_correct"] == control and x["treatment"]["strict_correct"] == treatment
        assert x["paired_control_treatment"]["gained"] == gained and x["paired_control_treatment"]["lost"] == lost
        assert sum(x["paired_control_treatment"].values()) == x["control"]["rows"]
    assert d["sets"]["validation16"]["control"]["truncated"] == d["sets"]["validation16"]["treatment"]["truncated"] == 2
    assert d["sets"]["utility_all108"]["control"]["truncated"] == d["sets"]["utility_all108"]["treatment"]["truncated"] == 6
    assert d["gate_checks"]["validation_gain_at_least2"] is False and d["exploratory_gate_passed"] is False
    assert all(d["gate_checks"][k] for k in ("old_dev_loss_at_most2", "no_extra_truncation", "official_TEST_untouched"))
    assert not any(k in d for k in ("raw_predictions", "input_ids", "labels", "messages", "token", "question", "command"))
    body = REPORT.read_text()
    for phrase in ("14 条", "652", "8/16", "21/64", "22/64", "66/108", "门槛失败", "官方 TEST"):
        assert phrase in body, phrase
    for relative in re.findall(r"\]\((\.\.[^)]+)\)", body):
        assert (REPORT.parent / relative).resolve().is_file(), relative
    assert (OUT / "strict-accuracy.png").is_file() and (OUT / "strict-accuracy.svg").is_file()
    print(json.dumps({"status": "PASS", "primary": "8/16 vs 8/16", "domain": "21/64 vs 22/64",
                      "utility": "66/108 vs 66/108", "official_TEST_rows": 0, "model_promotion": False}))


if __name__ == "__main__":
    main()
