#!/usr/bin/env python3
"""Compare frozen publisher SFT638 with base and C13 on the same TRAIN holdout."""

import hashlib
import json
from pathlib import Path

from benchkit import native_kali, strict_option_values


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-publisher-sft638-2026-11-10"
HOLDOUT = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
RUN = DATA / "gpu-attempt-a100-v3"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(a, b):
    assert set(a) == set(b)
    return {"both_correct": sum(a[k] and b[k] for k in a),
            "gained": sum(not a[k] and b[k] for k in a),
            "lost": sum(a[k] and not b[k] for k in a),
            "both_incorrect": sum(not a[k] and not b[k] for k in a)}


def main():
    assert not (RUN / "scores-private.json").exists(), "Do not overwrite frozen score"
    lock = json.loads((DATA / "scorer-lock-a100-v3-private.json").read_text())
    protocol = json.loads((DATA / "protocol-a100-v3-private.json").read_text())
    assert lock["status"] == "SFT638_SCORER_LOCK_BEFORE_TRAINING"
    assert lock["scorer_sha256"] == sha(Path(__file__))
    assert lock["training_protocol_sha256"] == sha(DATA / "protocol-a100-v3-private.json")
    assert lock["holdout_protocol_sha256"] == protocol["holdout_protocol_sha256"]
    assert lock["holdout_protocol_sha256"] == sha(HOLDOUT / "protocol-a100-v5-private.json")
    assert protocol["status"] == "FROZEN_REDSAGE_PUBLISHER_SFT638_BEFORE_TRAINING"
    assert protocol["official_TEST_rows"] == 0
    first_run = HOLDOUT / "gpu-attempt5"
    first_host = json.loads((first_run / "host-run-private.json").read_text())
    second_host = json.loads((RUN / "host-run-private.json").read_text())
    receipt = json.loads((RUN / "receipt-private.json").read_text())
    assert first_host["status"] == second_host["status"] == "COLLECTED"
    assert first_host["remaining_owned_resources"] == second_host["remaining_owned_resources"] == 0
    assert not first_host["cleanup_errors"] and not second_host["cleanup_errors"]
    assert receipt["status"] == "COMPLETE_PUBLISHER_SFT638"
    assert receipt["protocol_sha256"] == sha(DATA / "protocol-a100-v3-private.json")
    assert receipt["optimizer_steps"] == receipt["nonzero_gradient_steps"] == 638
    assert receipt["official_TEST_rows"] == 0
    previous_anchors = json.loads((first_run / "anchor-audit-private.json").read_text())
    current_anchors = json.loads((RUN / "base-anchor-audit-private.json").read_text())
    previous_base = {row["id"]: row["actual_sha256"] for row in previous_anchors
                     if row["arm"] == "base"}
    current_base = {row["id"]: row["actual_sha256"] for row in current_anchors}
    assert len(previous_base) == len(current_base) == 4
    anchor_exact_repeat_matches = sum(previous_base[k] == current_base[k] for k in previous_base)
    refs = json.loads((HOLDOUT / "references-private.json").read_text())
    reference = {r["custom_id"]: r for r in refs}
    assert len(reference) == 64
    previous = json.loads((first_run / "case-details-private.json").read_text())
    assert set(previous) == {"base", "sft"}
    assert set(previous["base"]) == set(previous["sft"]) == set(reference)
    predictions = json.loads((RUN / "sft-predictions-private.json").read_text())
    assert len(predictions) == len({r["id"] for r in predictions}) == 64
    assert {r["id"] for r in predictions} == set(reference)
    native = native_kali()
    details = {}
    for row in predictions:
        result = native.score_one(reference[row["id"]], row["response"])
        details[row["id"]] = {
            "total_score": result["total_score"],
            "exact_match": bool(result["exact_match"]) and not row["truncated"],
            "strict_option_value_correct": (not row["truncated"] and
                strict_option_values(reference[row["id"]], row["response"], native)),
            "format_error": bool(result["format_error"]),
            "truncated": bool(row["truncated"]),
        }
    seen = set(lock["seen_ids"])
    assert len(seen) == 56 and seen <= set(reference)
    strata = {"all64": set(reference), "train_seen56": seen,
              "train_unseen8": set(reference) - seen}
    arms = {"base": previous["base"], "C13_synthetic240": previous["sft"],
            "publisher_sft638": details}
    summary = {}
    for name, ids in strata.items():
        summary[name] = {"rows": len(ids), "arms": {}, "paired": {}}
        for arm, data in arms.items():
            summary[name]["arms"][arm] = {
                "strict_correct": sum(data[i]["strict_option_value_correct"] for i in ids),
                "native_exact_correct": sum(data[i]["exact_match"] for i in ids),
                "native_total_mean": sum(data[i]["total_score"] for i in ids) / len(ids),
                "format_errors": sum(data[i]["format_error"] for i in ids),
                "truncations": sum(data[i]["truncated"] for i in ids),
            }
        for comparator in ("base", "C13_synthetic240"):
            summary[name]["paired"][comparator + "_vs_publisher_sft638"] = paired(
                {i: bool(arms[comparator][i]["strict_option_value_correct"]) for i in ids},
                {i: bool(details[i]["strict_option_value_correct"]) for i in ids})
    output = {"status": "SCORED_REDSAGE_PUBLISHER_SFT638_INTERNAL_HOLDOUT",
              "source_official_split": "train", "rows": 64,
              "optimizer_steps": 638, "official_TEST_rows": 0,
              "human_expert_signoffs": 0, "model_promotion_allowed": False,
              "generated_commands_executed": False,
              "baseline_anchor_exact_repeat_matches": anchor_exact_repeat_matches,
              "baseline_anchor_count": 4,
              "baseline_gpu_model_match": first_host.get("GPU") == second_host.get("GPU"),
              "strata": summary,
              "limitations": ["Same publisher TRAIN source supplies SFT labels and internal holdout.",
                              "The holdout was selected after earlier C13 DEV observations.",
                              "Publisher silver labels are not independent expert gold.",
                              "This is not an official KaliBench TEST or leaderboard result."]}
    (RUN / "case-details-private.json").write_text(json.dumps(details, indent=2) + "\n")
    (RUN / "scores-private.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "all64": summary["all64"],
                      "official_TEST_rows": 0, "model_promotion_allowed": False}))


if __name__ == "__main__":
    main()
