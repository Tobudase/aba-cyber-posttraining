#!/usr/bin/env python3
"""Check released aggregate evidence; private candidate bodies are not reproduced."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-external-utility-intake-2026-10-28"


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    assert manifest["schema"] == "kali.external-utility-intake.public.v1"
    for name, digest in manifest["file_sha256"].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    s = json.loads((OUT / "summary.json").read_text())
    assert s["status"] == "EXTERNAL_SOURCE_UTILITY_CANDIDATES_REVIEW_PENDING"
    assert s["source_rows"] == 8669
    assert sum(s["rejected_by_first_reason"].values()) + s["syntactic_eligible_rows"] == s["source_rows"]
    assert s["selected_rows"] == sum(s["selected_family_counts"].values()) == 23
    assert s["automatic_flagged_rows"] == 15 and s["potentially_unbounded_rows"] == 2
    assert s["exact_prior_prompt_overlap"] == s["exact_prior_command_overlap"] == 0
    assert s["independent_human_reviews"] == s["training_eligible_count"] == s["blind_test_eligible_count"] == 0
    assert s["commands_executed"] == s["model_calls"] == s["official_TEST_calls"] == s["new_training_steps"] == 0
    assert s["source_separated_but_blind"] is False
    assert s["native_ABA_generation_complete"] is False and s["formal_default"] == "original_base"
    print(json.dumps({"status": "PASS_PUBLIC_EXTERNAL_UTILITY_INTAKE_AGGREGATES", "selected_rows": 23,
                      "training_eligible": 0, "private_rows_reproduced": False}))


if __name__ == "__main__":
    main()
