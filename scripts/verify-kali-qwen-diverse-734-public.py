#!/usr/bin/env python3
"""Cross-check aggregate 734-step claims without private data or model outputs."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/kali-qwen-diverse-734-2026-11-01"
QUALITY = ROOT / "results/kali-qwen-data-quality-2026-11-01/summary.json"


def main():
    score = json.loads((RESULT / "comparison.json").read_text())
    audit = json.loads((RESULT / "semantic-audit.json").read_text())
    quality = json.loads(QUALITY.read_text())
    assert score["status"] == "SCORED_MATCHED_734_INTERNAL_ONLY_V2_EXPLORATORY"
    assert score["optimizer_steps_each_arm"] == 734
    assert score["official_TEST_rows"] == 0 and score["model_promotion"] is False
    assert score["exploratory_gate_passed"] and all(score["gate_checks"].values())
    expected = {"domain_old_dev64": (64, 22, 22, 2, 1),
                "utility_primary36": (36, 18, 24, 2, 0),
                "utility_secondary72": (72, 54, 63, 0, 0),
                "utility_all108": (108, 72, 87, 2, 0)}
    for key, (n, control, treatment, trunc_control, trunc_treatment) in expected.items():
        value = score["sets"][key]
        assert value["control"]["rows"] == value["treatment"]["rows"] == n
        assert value["control"]["strict_correct"] == control
        assert value["treatment"]["strict_correct"] == treatment
        assert value["control"]["truncated"] == trunc_control
        assert value["treatment"]["truncated"] == trunc_treatment
        pair = value["paired_strict"]
        assert sum(pair.values()) == n
        assert pair["both_correct"] + pair["lost"] == control
        assert pair["both_correct"] + pair["gained"] == treatment
    assert audit["status"] == "OFFLINE_SYNTHETIC_SEMANTIC_AUDIT_COMPLETE"
    assert audit["rows"] == 18 and audit["reference_commands_fixture_passed"] == 18
    assert audit["generated_commands_run"] == 33
    assert audit["GPU_count"] == audit["official_KaliBench_TEST_rows"] == audit["owned_cluster_resources_remaining"] == 0
    assert audit["model_promotion"] is False
    families = audit["families"]
    assert set(families) == {"log-count", "log-line-numbers", "offline-tls"}
    for family, (c_strict, t_strict, c_fixture, t_fixture) in {
        "log-count": (0, 6, 1, 6),
        "log-line-numbers": (0, 6, 0, 6),
        "offline-tls": (0, 3, 0, 3),
    }.items():
        f = families[family]
        assert f["rows"] == 6
        assert f["control"]["strict_correct"] == c_strict
        assert f["treatment"]["strict_correct"] == t_strict
        assert f["control"]["fixture_stdout_match"] == c_fixture
        assert f["treatment"]["fixture_stdout_match"] == t_fixture
    assert sum(families[f]["treatment"]["strict_correct"] - families[f]["control"]["strict_correct"] for f in families) == 15
    assert quality["status"] == "EXPLORATORY_734_COMPLETED_GATE_PASSED_NO_PROMOTION"
    assert quality["human_expert_signoffs"] == 0 and quality["official_test_rows"] == 0
    assert quality["completed_gpu_comparison"]["model_promotion"] is False
    for extension in ("png", "svg"):
        assert (RESULT / f"control-treatment.{extension}").stat().st_size > 1_000
    print(json.dumps({"status": "PASS", "utility_primary36": "18->24",
                      "domain_old_dev64": "22->22", "official_TEST_rows": 0,
                      "model_promotion": False}))


if __name__ == "__main__":
    main()
