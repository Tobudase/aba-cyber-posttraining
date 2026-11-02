#!/usr/bin/env python3
"""Verify published aggregate arithmetic and report claims without private data."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/kali-qwen-agent-data680-2026-11-02"
REPORT = ROOT / "docs/KALI_QWEN_AGENT_DATA680_ZH_2026-11-02.md"


def main():
    d = json.loads((RESULT / "aggregate.json").read_text())
    assert d["status"] == "SCORED_AGENT_DATA_MATCHED_SFT_EXPLORATORY"
    assert d["agent_proposals_admitted"] == 42
    assert d["base_train_rows_common"] == 638
    assert d["optimizer_steps_each_arm"] == 680
    assert d["official_TEST_rows"] == 0
    assert d["native_ABA_controller_executed"] is False
    assert d["model_promotion"] is False
    expected = {"validation16": (8, 10, 10), "old_dev64": (None, 22, 22),
                "utility_primary36": (None, 18, 18), "utility_all108": (None, 72, 72)}
    for name, (base, control, treatment) in expected.items():
        rows = d["sets"][name]
        if base is not None:
            assert rows["base"]["strict_correct"] == base
        assert rows["control"]["strict_correct"] == control
        assert rows["treatment"]["strict_correct"] == treatment
        assert rows["paired_control_treatment"]["gained"] == 0
        assert rows["paired_control_treatment"]["lost"] == 0
        assert sum(rows["paired_control_treatment"].values()) == rows["control"]["rows"]
    assert d["sets"]["utility_all108"]["control"]["truncated"] == 6
    assert d["sets"]["utility_all108"]["treatment"]["truncated"] == 1
    assert d["sets"]["validation16"]["treatment"]["truncated"] == 1
    assert d["gate_checks"]["validation_gain_at_least2"] is False
    assert d["exploratory_gate_passed"] is False
    posthoc = json.loads((RESULT / "semantic-posthoc.json").read_text())
    assert posthoc["status"] == "POSTHOC_SAFE_FIXTURE_DIAGNOSTIC_NOT_PREDECLARED_SCORE"
    assert posthoc["rows"] == 12 and posthoc["commands_executed"] == 11
    assert posthoc["fixture_pass_total"] == 9 and posthoc["official_TEST_rows"] == posthoc["GPU_count"] == 0
    assert posthoc["arms"]["control"]["safe_fixture_pass"] == 4
    assert posthoc["arms"]["treatment"]["safe_fixture_pass"] == 5
    assert posthoc["original_strict_gate_unchanged"] is True and posthoc["model_promotion"] is False
    assert REPORT.is_file() and (RESULT / "strict-counts.png").is_file()
    assert (RESULT / "strict-counts.svg").is_file()
    report = REPORT.read_text()
    for phrase in ("42 条", "10/16", "22/64", "72/108", "4/6", "5/6", "不是 ABA 原生控制器", "LINSTOR"):
        assert phrase in report, phrase
    for raw in re.findall(r"\]\((\.\.[^)]+)\)", report):
        assert (REPORT.parent / raw).resolve().is_file(), raw
    print(json.dumps({"status": "PASS", "strict_base_control_treatment_validation": [8, 10, 10],
                      "official_TEST_rows": 0, "model_promotion": False}))


if __name__ == "__main__":
    main()
