#!/usr/bin/env python3
"""Score a frozen P09 operator control against P07 on exposed TRAIN-source DEV."""

import hashlib
import json
from pathlib import Path

from benchkit import native_kali, strict_option_values


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data/benchkit"
STUDY = BENCH / "kali-redsage-aba-publisher-v2-2026-11-10"
P07 = STUDY / "P07/gpu-attempt-a100"
P09 = STUDY / "P09"
RUN = P09 / "gpu-attempt-a100"
REF1 = BENCH / "kali-redsage-publisher-holdout-2026-11-10/references-private.json"
REF2 = BENCH / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"
LOCK = P09 / "scorer-lock-private.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def summarize(detail, ids):
    return {"rows": len(ids),
            "native_total_mean": sum(detail[i]["native_total"] for i in ids) / len(ids),
            "strict_correct": sum(detail[i]["strict"] for i in ids),
            "format_errors": sum(detail[i]["format_error"] for i in ids),
            "truncations": sum(detail[i]["truncated"] for i in ids)}


def main():
    assert not (RUN / "scores-private.json").exists()
    lock = read(LOCK)
    assert lock["status"] == "P09_SCORER_LOCK_BEFORE_CANDIDATE_OUTPUTS"
    assert lock["script_sha256"] == sha(Path(__file__))
    assert lock["protocol_sha256"] == sha(P09 / "protocol-private.json")
    assert lock["ref1_sha256"] == sha(REF1) and lock["ref2_sha256"] == sha(REF2)
    assert lock["p07_scores_sha256"] == sha(P07 / "scores-private.json")
    freeze, host, receipt = (read(P09 / "freeze-manifest-private.json"),
                             read(RUN / "host-run-private.json"),
                             read(RUN / "receipt-private.json"))
    assert freeze["status"] == "MIXED_SOURCE_SILVER_OPERATOR_PILOT_FROZEN_BEFORE_OUTPUTS"
    assert host["status"] == "COLLECTED" and host["remaining_owned_resources"] == 0
    assert not host["cleanup_errors"]
    assert receipt["status"] == "COMPLETE_ABA_CANDIDATE" and receipt["candidate_id"] == "P09"
    assert receipt["optimizer_steps"] == receipt["nonzero_gradient_steps"] == 749
    assert receipt["adapter_reload_max_logit_delta"] <= 1e-4
    assert receipt["official_TEST_rows"] == 0
    refs1, refs2 = read(REF1), read(REF2)
    refs = {r["custom_id"]: r for r in refs1 + refs2}
    assert len(refs) == 128
    panel = {"dev1": {r["custom_id"] for r in refs1},
             "dev2": {r["custom_id"] for r in refs2}, "combined": set(refs)}
    native = native_kali()
    arms = {"E0": read(RUN / "base-predictions-private.json"),
            "P07": read(P07 / "candidate-predictions-private.json"),
            "P09": read(RUN / "candidate-predictions-private.json")}
    assert all(len(rows) == 128 and {r["id"] for r in rows} == set(refs)
               for rows in arms.values())
    assert {r["id"]: r["response"] for r in arms["E0"]} == {
        r["id"]: r["response"] for r in read(P07 / "base-predictions-private.json")}
    detail = {}
    for arm, rows in arms.items():
        details = {}
        for row in rows:
            score = native.score_one(refs[row["id"]], row["response"])
            details[row["id"]] = {"native_total": score["total_score"],
                                  "strict": not row["truncated"] and strict_option_values(
                                      refs[row["id"]], row["response"], native),
                                  "format_error": bool(score["format_error"]),
                                  "truncated": bool(row["truncated"])}
        detail[arm] = details
    summary = {name: {arm: summarize(details, sorted(ids)) for arm, details in detail.items()}
               for name, ids in panel.items()}
    result = {"status": "P09_OPERATOR_MIXED_SILVER_EXPOSED_DEV_DIAGNOSTIC",
              "training_rows": 749, "publisher_verified_rows": 733,
              "source_silver_rows": 16, "source_silver_terminal_verified": False,
              "operator_control_not_ABA_selected": True,
              "official_TEST_rows": 0, "sealed_final64_used": False,
              "model_promotion_allowed": False, "summary": summary,
              "paired_P07_to_P09": {"gained": sum(not detail["P07"][i]["strict"] and detail["P09"][i]["strict"] for i in refs),
                                  "lost": sum(detail["P07"][i]["strict"] and not detail["P09"][i]["strict"] for i in refs)},
              "limitations": ["Source-silver examples target tools diagnosed on this exposed DEV.",
                              "Native total and strict correctness are descriptive here, not independent gains.",
                              "P09 is an operator pilot, not an ABA-selected checkpoint.",
                              "Official TEST and sealed final64 remain untouched."]}
    (RUN / "case-details-private.json").write_text(json.dumps(detail, indent=2) + "\n")
    (RUN / "scores-private.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "summary": summary,
                      "paired_P07_to_P09": result["paired_P07_to_P09"],
                      "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
