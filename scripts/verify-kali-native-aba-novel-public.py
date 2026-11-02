#!/usr/bin/env python3
"""Check disclosure boundaries and arithmetic of the native ABA aggregate."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/kali-native-aba-novel-2026-11-02/aggregate.json"
REPORT = ROOT / "docs/KALI_NATIVE_ABA_NOVEL_DATA_PILOT_ZH_2026-11-02.md"


def main():
    d = json.loads(DATA.read_text())
    assert d["status"] == "POSTHOC_TRAIN_FIXTURE_AUDIT"
    assert d["native_run_status"] == "NATIVE_ABA_COMPLETED" and d["native_ABA_exit_code"] == 0
    assert d["candidate_rows"] == d["unique_ids"] == d["unique_questions"] == d["unique_commands"] == 16
    assert d["tools"] == {"grep": 4, "head": 4, "tail": 4, "wc": 4}
    assert d["frozen_primary"]["accepted"] == 14 and d["frozen_primary"]["rows"] == 16
    assert d["frozen_primary"]["score"] == 14 / 16
    assert d["posthoc_two_fixture_passed"] == 16 and d["posthoc_not_primary"] is True
    assert d["posthoc_reasons"] == {"pass": 16}
    assert d["official_TEST_rows"] == d["independent_gold_rows"] == d["model_optimizer_steps"] == d["gpu_count"] == 0
    assert d["ephemeral_vmi_deleted"] is True and d["structural_families"] == 4
    assert d["decision"] == "HOLD_FOR_REVIEW_AND_INDEPENDENT_EVALUATION"
    assert len(d["candidate_sha256"]) == len(d["task_manifest_sha256"]) == 64
    assert not any(k in d for k in ("candidate_b64", "per_row_private", "run_log_tail", "token", "question", "command"))
    body = REPORT.read_text()
    for phrase in ("14/16", "16/16", "事后", "原生 ABA", "官方", "暂不把这 16 条投入正式 SFT"):
        assert phrase in body
    for relative in re.findall(r"\]\((\.\.[^)]+)\)", body):
        assert (REPORT.parent / relative).resolve().is_file(), relative
    print(json.dumps({"status": "PASS", "frozen": "14/16", "posthoc": "16/16",
                      "official_TEST_rows": 0, "model_optimizer_steps": 0}))


if __name__ == "__main__":
    main()
