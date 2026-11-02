#!/usr/bin/env python3
"""Cross-check external26 aggregate claims without any private questions or outputs."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-external26-ai-diagnostic-2026-11-02"


def main():
    d = json.loads((OUT / "aggregate.json").read_text())
    assert d["status"] == "SCORED_EXTERNAL26_AI_ONLY_DIAGNOSTIC_NOT_GOLD"
    assert d["rows"] == 26 and d["tools"] == 20
    assert d["official_TEST_rows"] == d["optimizer_steps"] == d["human_expert_signoffs"] == 0
    assert d["no_commands_executed"] and not d["formal_gate_satisfied"] and not d["model_promotion"]
    for name, n, expected in (
        ("all26", 26, {"base": (9, 26, 26), "control": (7, 25, 24), "treatment": (8, 26, 24)}),
        ("safe_fixture_evidence_true", 8, {"base": (2, 8, 8), "control": (1, 8, 8), "treatment": (1, 8, 8)}),
        ("safe_fixture_evidence_false", 18, {"base": (7, 18, 18), "control": (6, 17, 16), "treatment": (7, 18, 16)}),
    ):
        s = d["strata"][name]
        assert s["rows"] == n
        for arm, (exact, format_ok, first_tool) in expected.items():
            a = s["arms"][arm]
            assert a["reference_command_shlex_token_exact"] == exact
            assert a["closed_output_envelope_no_extra_text"] == format_ok
            assert a["reference_first_executable_match"] == first_tool
    pair = d["strata"]["all26"]["paired"]["control_vs_treatment"]["reference_command_shlex_token_exact"]
    assert pair == {"both": 7, "gained": 1, "lost": 0, "neither": 18}
    pair = d["strata"]["all26"]["paired"]["base_vs_treatment"]["reference_command_shlex_token_exact"]
    assert pair == {"both": 7, "gained": 1, "lost": 2, "neither": 16}
    for ext in ("png", "svg"):
        assert (OUT / f"external26.{ext}").stat().st_size > 1_000
    print(json.dumps({"status": "PASS", "token_exact_base_control_treatment": [9, 7, 8],
                      "official_TEST_rows": 0, "model_promotion": False}))


if __name__ == "__main__":
    main()
