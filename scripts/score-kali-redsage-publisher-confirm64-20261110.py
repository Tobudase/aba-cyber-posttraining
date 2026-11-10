#!/usr/bin/env python3
"""Score paired RedSage predictions on publisher TRAIN internal holdout.

Generated shell commands are parsed as inert text and never executed.
"""

import hashlib
import json
from pathlib import Path

from benchkit import native_kali, strict_option_values


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-publisher-confirm64-2026-11-10"
RUN = DATA / "gpu-attempt1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(a, b):
    assert set(a) == set(b)
    return {"both_correct": sum(a[k] and b[k] for k in a),
            "gained": sum(not a[k] and b[k] for k in a),
            "lost": sum(a[k] and not b[k] for k in a),
            "both_incorrect": sum(not a[k] and not b[k] for k in a)}


def main():
    assert not (RUN / "scores-private.json").exists(), "Immutable scored result"
    protocol = json.loads((DATA / "protocol-private.json").read_text())
    freeze = json.loads((DATA / "freeze-manifest-private.json").read_text())
    lock = json.loads((DATA / "scorer-lock-private.json").read_text())
    host = json.loads((RUN / "host-run-private.json").read_text())
    receipt = json.loads((RUN / "receipt-private.json").read_text())
    assert sha(Path(__file__)) == lock["scorer_sha256"]
    assert sha(DATA / "protocol-private.json") == lock["protocol_sha256"]
    assert sha(DATA / "freeze-manifest-private.json") == protocol["freeze_sha256"]
    assert sha(DATA / "references-private.json") == protocol["references_sha256"]
    assert freeze["status"] == "FROZEN_BEFORE_REDSAGE_PUBLISHER_CONFIRM64_OUTPUTS"
    assert protocol["status"] == "FROZEN_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64_BEFORE_OUTPUTS"
    assert host["status"] == "COLLECTED" and not host["cleanup_errors"]
    assert host["remaining_owned_resources"] == 0
    assert receipt["status"] == "COMPLETE_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64"
    assert receipt["historical_anchors_compared"] == 8
    audit = json.loads((RUN / "anchor-audit-private.json").read_text())
    assert len(audit) == 8
    assert all(sha_expected == hashlib.sha256(a["response"].encode()).hexdigest()
               for a in audit for sha_expected in [a["actual_sha256"]])
    assert receipt["official_TEST_rows"] == receipt["optimizer_steps"] == 0
    assert receipt["source_rows"] == 64
    refs = json.loads((DATA / "references-private.json").read_text())
    assert len(refs) == len({r["custom_id"] for r in refs}) == 64
    reference = {r["custom_id"]: r for r in refs}
    native = native_kali()
    details = {}
    metrics = {}
    for arm in ("base", "sft"):
        rows = json.loads((RUN / (arm + "-predictions-private.json")).read_text())
        assert len(rows) == len({r["id"] for r in rows}) == 64
        assert {r["id"] for r in rows} == set(reference)
        assert all(r["arm"] == arm for r in rows)
        details[arm] = {}
        for row in rows:
            result = native.score_one(reference[row["id"]], row["response"])
            strict = (not row["truncated"] and
                      strict_option_values(reference[row["id"]], row["response"], native))
            details[arm][row["id"]] = {
                "tool_score": result["tool_score"],
                "optional_f1": result["optional_f1"],
                "positional_f1": result["positional_f1"],
                "total_score": result["total_score"],
                "exact_match": bool(result["exact_match"]) and not row["truncated"],
                "strict_option_value_correct": bool(strict),
                "format_error": bool(result["format_error"]),
                "truncated": bool(row["truncated"]),
            }
    # Seen/unseen membership is frozen in the scorer lock, not inferred from
    # which holdout references happened to be selected.
    seen_ids = set(lock["seen_ids"])
    assert len(seen_ids) == 60 and seen_ids <= set(reference)
    assert all(reference[k]["tool_name"] in lock["train_tools"] for k in seen_ids)
    assert all(reference[k]["tool_name"] not in lock["train_tools"] for k in set(reference) - seen_ids)
    strata = {"all64": set(reference), "train_seen60": seen_ids,
              "train_unseen4": set(reference) - seen_ids}
    for name, ids in strata.items():
        metrics[name] = {"rows": len(ids), "arms": {}, "paired": {}}
        for arm in ("base", "sft"):
            d = details[arm]
            metrics[name]["arms"][arm] = {
                "native_total_score_mean": sum(d[k]["total_score"] for k in ids) / len(ids),
                "native_exact_match": sum(d[k]["exact_match"] for k in ids),
                "strict_option_value_correct": sum(d[k]["strict_option_value_correct"] for k in ids),
                "format_errors": sum(d[k]["format_error"] for k in ids),
                "truncated": sum(d[k]["truncated"] for k in ids),
            }
        metrics[name]["paired"] = {
            "strict_option_value_correct": paired(
                {k: details["base"][k]["strict_option_value_correct"] for k in ids},
                {k: details["sft"][k]["strict_option_value_correct"] for k in ids}),
            "native_exact_match": paired(
                {k: details["base"][k]["exact_match"] for k in ids},
                {k: details["sft"][k]["exact_match"] for k in ids}),
        }
    output = {"status": "SCORED_PUBLISHER_TRAIN_CONFIRM64",
              "source_official_split": "train", "rows": 64,
              "strata": metrics, "optimizer_steps": 0, "official_TEST_rows": 0,
              "generated_commands_executed": False,
              "human_expert_signoffs": 0, "model_promotion_allowed": False,
              "limitations": ["Publisher silver labels, not independently certified gold.",
                              "Official TRAIN internal holdout, not official TEST or leaderboard score.",
                              "This second panel was selected after viewing the first internal holdout scores, before any predictions on these rows.",
                              "Native command score can credit outputs with incorrect option values; inspect strict diagnostic."]}
    (RUN / "case-details-private.json").write_text(json.dumps(details, indent=2) + "\n")
    (RUN / "scores-private.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "all64": metrics["all64"],
                      "official_TEST_rows": 0, "model_promotion_allowed": False}))


if __name__ == "__main__":
    main()
