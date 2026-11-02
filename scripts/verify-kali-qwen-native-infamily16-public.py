#!/usr/bin/env python3
"""Check public in-family diagnostic arithmetic, scope, and figure links."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-native-infamily16-2026-11-02"
REPORT = ROOT / "docs/KALI_QWEN_NATIVE_INFAMILY16_DIAGNOSTIC_ZH_2026-11-02.md"


def main():
    d = json.loads((OUT / "aggregate.json").read_text())
    assert d["status"] == "COMPLETE_ADAPTIVE_INFAMILY16_AND_POSTHOC_LINUX_AUDIT"
    assert d["rows"] == d["reference_safe_fixture_passed_before_outputs"] == 16
    assert d["tools"] == {"head": 4, "tail": 4, "wc": 4, "grep": 4}
    assert d["created_after_previous_SFT_result"] and d["fixtures_frozen_before_this_diagnostic_model_outputs"]
    assert d["frozen_strict_unchanged"] and d["posthoc_expanded_allowlist_after_outputs"]
    assert d["GPU_inference_optimizer_steps"] == d["official_TEST_rows"] == d["independent_gold_rows"] == 0
    assert d["GPU_inference_resources_cleaned"] and d["posthoc_expanded_safe_linux_execution_resources_cleaned"]
    assert d["posthoc_expanded_safe_linux_execution_GPU_count"] == 0
    assert d["posthoc_expanded_safe_linux_execution_rows"] == 48
    for arm, expected in (("base",16),("control",14),("treatment",13)):
        assert d["frozen_strict"][arm]["strict_correct"] == 12
        assert d["frozen_strict"][arm]["canonical_exact"] == 12
        assert d["frozen_strict"][arm]["truncated"] == 0
        assert d["posthoc_expanded_safe_linux_execution"][arm]["passed"] == expected
        assert d["posthoc_expanded_safe_linux_execution"][arm]["executed"] == 16
        assert d["frozen_strict"][arm]["by_tool"]["grep"]["strict"] == 0
    assert d["posthoc_behavior_paired_control_treatment"] == {"both_correct":12,"gained":1,"lost":2,"both_wrong":1}
    assert d["posthoc_failure_mechanisms"] == {"control_invalid_grep_options":2,"treatment_grep_word_boundary_output_mismatch":3}
    assert d["model_promotion"] is False
    assert d["decision"] == "KEEP_BASE_AND_DO_NOT_REUSE_NATIVE_ABA_BATCH_AS_IS"
    assert not any(k in d for k in ("candidate_b64","per_row_private","raw_predictions","messages","token","question","command"))
    body = REPORT.read_text()
    for phrase in ("12/16", "16/16", "14/16", "13/16", "事后", "不推广处理适配器", "官方 TEST"):
        assert phrase in body, phrase
    for relative in re.findall(r"\]\((\.\.[^)]+)\)", body):
        assert (REPORT.parent / relative).resolve().is_file(), relative
    assert (OUT / "strict-vs-fixture.png").is_file() and (OUT / "strict-vs-fixture.svg").is_file()
    print(json.dumps({"status":"PASS","frozen_strict":"12/16 each",
                      "posthoc_linux_fixture":[16,14,13],"official_TEST_rows":0}))


if __name__=="__main__":
    main()
