#!/usr/bin/env python3
"""Score the frozen operator P07 coverage control on two exposed TRAIN DEV panels."""

import argparse
import hashlib
import json
from pathlib import Path

from benchkit import native_kali, strict_option_values

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data/benchkit"
STUDY = BENCH / "kali-redsage-aba-publisher-v2-2026-11-10"
REF1 = BENCH / "kali-redsage-publisher-holdout-2026-11-10/references-private.json"
REF2 = BENCH / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"
TRAIN_SOURCE = BENCH / "kali-screened/train.jsonl"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(a, b, ids):
    return {"gained": sum(not a[i]["strict"] and b[i]["strict"] for i in ids),
            "lost": sum(a[i]["strict"] and not b[i]["strict"] for i in ids)}


def summarize(details, ids):
    return {"rows": len(ids),
            "native_total_mean": sum(details[i]["native_total"] for i in ids) / len(ids),
            "strict_correct": sum(details[i]["strict"] for i in ids),
            "native_exact_correct": sum(details[i]["native_exact"] for i in ids),
            "format_errors": sum(details[i]["format_error"] for i in ids),
            "truncations": sum(details[i]["truncated"] for i in ids)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id", choices=["P07"])
    args = parser.parse_args()
    data = STUDY / args.candidate_id
    run = data / "gpu-attempt-a100"
    score_path = run / "scores-private.json"
    assert not score_path.exists(), "Frozen score cannot be overwritten"
    lock = json.loads((data / "scorer-lock-private.json").read_text())
    assert lock["status"] == "COVERAGE733_SCORER_LOCK_BEFORE_P07_OUTPUTS"
    assert lock["scorer_sha256"] == sha(Path(__file__))
    assert lock["dev1_references_sha256"] == sha(REF1)
    assert lock["dev2_references_sha256"] == sha(REF2)
    freeze = json.loads((data / "freeze-manifest-private.json").read_text())
    assert freeze["status"] == "BROAD_COVERAGE_CONTROL_FROZEN_BEFORE_OUTPUTS"
    assert freeze["protocol_sha256"] == sha(data / "protocol-private.json")
    assert lock["protocol_sha256"] == freeze["protocol_sha256"]
    assert freeze["dev1_references_sha256"] == sha(REF1)
    assert freeze["dev2_references_sha256"] == sha(REF2)
    host = json.loads((run / "host-run-private.json").read_text())
    receipt = json.loads((run / "receipt-private.json").read_text())
    assert host["status"] == "COLLECTED" and host["remaining_owned_resources"] == 0
    assert not host["cleanup_errors"]
    assert receipt["status"] == "COMPLETE_ABA_CANDIDATE"
    assert receipt["candidate_id"] == args.candidate_id
    assert receipt["official_TEST_rows"] == 0
    assert receipt["optimizer_steps"] == receipt["nonzero_gradient_steps"] == freeze["training_rows"]
    assert receipt["adapter_reload_max_logit_delta"] <= 1e-4
    refs1 = json.loads(REF1.read_text())
    refs2 = json.loads(REF2.read_text())
    ref = {r["custom_id"]: r for r in refs1 + refs2}
    panel1 = {r["custom_id"] for r in refs1}
    panel2 = {r["custom_id"] for r in refs2}
    assert len(ref) == 128 and len(panel1) == len(panel2) == 64
    protocol = json.loads((data / "protocol-private.json").read_text())
    import gzip
    payload = json.loads(gzip.decompress((data / "payload-private.json.gz").read_bytes()))
    train_ids = {r["id"] for r in payload["train_rows"]}
    train_source = {r["id"]: r for r in map(json.loads, TRAIN_SOURCE.read_text().splitlines())}
    seen_tools = {train_source[i]["native_label"]["tool_name"] for i in train_ids}
    unseen = {i for i, r in ref.items() if r["tool_name"] not in seen_tools}
    assert unseen
    native = native_kali()
    all_details = {}
    for arm, filename in (("base", "base-predictions-private.json"),
                          (args.candidate_id, "candidate-predictions-private.json")):
        rows = json.loads((run / filename).read_text())
        assert len(rows) == 128 and {r["id"] for r in rows} == set(ref)
        assert all(r["arm"] == arm for r in rows)
        details = {}
        for row in rows:
            scored = native.score_one(ref[row["id"]], row["response"])
            details[row["id"]] = {
                "native_total": scored["total_score"],
                "native_exact": bool(scored["exact_match"]) and not row["truncated"],
                "strict": not row["truncated"] and strict_option_values(ref[row["id"]], row["response"], native),
                "format_error": bool(scored["format_error"]),
                "truncated": bool(row["truncated"]),
            }
        all_details[arm] = details
    panels = {"dev1": panel1, "dev2": panel2, "combined": set(ref),
              "train_unseen_tools": unseen}
    summary = {name: {"base": summarize(all_details["base"], ids),
                      "candidate": summarize(all_details[args.candidate_id], ids),
                      "paired": paired(all_details["base"], all_details[args.candidate_id], ids)}
               for name, ids in panels.items()}
    base = summary["combined"]["base"]
    candidate = summary["combined"]["candidate"]
    unseen_base = summary["train_unseen_tools"]["base"]
    unseen_candidate = summary["train_unseen_tools"]["candidate"]
    gates = {
        "native_total_improves": candidate["native_total_mean"] > base["native_total_mean"],
        "strict_no_drop": candidate["strict_correct"] >= base["strict_correct"],
        "unseen_strict_no_drop": unseen_candidate["strict_correct"] >= unseen_base["strict_correct"],
        "format_no_increase": candidate["format_errors"] <= base["format_errors"],
        "zero_truncations": candidate["truncations"] == 0,
    }
    result = {"status": "SCORED_OPERATOR_COVERAGE_CONTROL_EXPOSED_DEV",
              "candidate_id": args.candidate_id, "training_rows": freeze["training_rows"],
              "optimizer_steps": receipt["optimizer_steps"], "source_official_split": "train",
              "official_TEST_rows": 0, "final64_used": False,
              "model_promotion_allowed": False, "human_expert_signoffs": 0,
              "summary": summary, "selection_gates": gates,
              "passes_all_gates": all(gates.values()),
              "limitations": ["P07 is operator-prepared, not ABA-selected.",
                              "The 128-row DEV was exposed to previous model runs.",
                              "Publisher silver labels are not independent expert gold.",
                              "Internal DEV panels come from official TRAIN.",
                              "This is not an official KaliBench leaderboard evaluation."]}
    (run / "case-details-private.json").write_text(json.dumps(all_details, indent=2) + "\n")
    score_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "candidate_id", "summary", "selection_gates", "passes_all_gates", "official_TEST_rows", "final64_used")}))


if __name__ == "__main__":
    main()
