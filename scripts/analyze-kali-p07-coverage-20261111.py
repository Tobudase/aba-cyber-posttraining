#!/usr/bin/env python3
"""Predeclared, aggregate-only P07 coverage analysis on exposed internal DEV."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/benchkit/kali/src"))
import model_score  # noqa: E402

BENCH = ROOT / "data/benchkit"
P05 = BENCH / "kali-redsage-aba-publisher-v2-2026-11-10/P05/gpu-attempt-a100"
P07 = BENCH / "kali-redsage-aba-publisher-v2-2026-11-10/P07"
RUN = P07 / "gpu-attempt-a100"
REF1 = BENCH / "kali-redsage-publisher-holdout-2026-11-10/references-private.json"
REF2 = BENCH / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"
SOURCE = BENCH / "kali-screened/train.jsonl"
OUT = BENCH / "kali-p07-coverage-analysis-2026-11-11/aggregate.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predictions(folder, filename):
    rows = read(folder / filename)
    assert len(rows) == len({row["id"] for row in rows}) == 128
    return {row["id"]: row for row in rows}


def metrics(scores, strict, ids):
    return {**{key: sum(scores[i][key] for i in ids) / len(ids)
               for key in ("tool_score", "optional_f1", "positional_f1", "total_score")},
            "strict_correct": sum(strict[i]["strict"] for i in ids), "rows": len(ids)}


def main():
    lock = read(P07 / "analysis-lock-private.json")
    assert lock["status"] == "P07_SUBGROUP_ANALYSIS_LOCK_BEFORE_OUTPUTS"
    assert lock["script_sha256"] == sha(Path(__file__))
    assert lock["protocol_sha256"] == sha(P07 / "protocol-private.json")
    assert lock["ref1_sha256"] == sha(REF1) and lock["ref2_sha256"] == sha(REF2)
    assert lock["source_sha256"] == sha(SOURCE)
    freeze = read(P07 / "freeze-manifest-private.json")
    assert freeze["status"] == "BROAD_COVERAGE_CONTROL_FROZEN_BEFORE_OUTPUTS"
    host, receipt = read(RUN / "host-run-private.json"), read(RUN / "receipt-private.json")
    assert host["status"] == "COLLECTED" and host["remaining_owned_resources"] == 0
    assert not host["cleanup_errors"]
    assert receipt["candidate_id"] == "P07"
    assert receipt["optimizer_steps"] == receipt["nonzero_gradient_steps"] == 733
    assert receipt["official_TEST_rows"] == 0 and receipt["dev_predictions"] == 128
    refs1 = {r["custom_id"]: r for r in read(REF1)}
    refs2 = {r["custom_id"]: r for r in read(REF2)}
    assert len(refs1) == len(refs2) == 64 and not set(refs1) & set(refs2)
    refs = refs1 | refs2
    source = {r["id"]: r for r in map(json.loads, SOURCE.read_text().splitlines())}
    encoded = read(P07 / "train-encoded-private.json")
    assert len(encoded) == 733 and len({r["id"] for r in encoded}) == 733
    old_tools = {source[r["id"]]["native_label"]["tool_name"] for r in encoded[:638]}
    new_tools = {source[r["id"]]["native_label"]["tool_name"] for r in encoded}
    base5 = predictions(P05, "base-predictions-private.json")
    base7 = predictions(RUN, "base-predictions-private.json")
    p05 = predictions(P05, "candidate-predictions-private.json")
    p07 = predictions(RUN, "candidate-predictions-private.json")
    assert set(refs) == set(base5) == set(base7) == set(p05) == set(p07)
    assert all(base5[i]["response"] == base7[i]["response"] for i in refs)
    arms = {"E0": base7, "P05": p05, "P07": p07}
    scores = {name: {i: model_score.score_one(refs[i], row["response"])
                     for i, row in data.items()} for name, data in arms.items()}
    strict = {"E0": read(P05 / "case-details-private.json")["base"],
              "P05": read(P05 / "case-details-private.json")["P05"],
              "P07": read(RUN / "case-details-private.json")["P07"]}
    groups = {"combined128": set(refs), "DEV1_64": set(refs1), "DEV2_64": set(refs2),
              "old_unseen12": {i for i in refs if refs[i]["tool_name"] not in old_tools},
              "newly_covered8": {i for i in refs if refs[i]["tool_name"] not in old_tools
                                 and refs[i]["tool_name"] in new_tools},
              "still_unseen4": {i for i in refs if refs[i]["tool_name"] not in new_tools}}
    assert {k: len(v) for k, v in groups.items()} == {
        "combined128": 128, "DEV1_64": 64, "DEV2_64": 64,
        "old_unseen12": 12, "newly_covered8": 8, "still_unseen4": 4}
    result = {"status": "P07_EXPOSED_DEV_COVERAGE_ANALYSIS",
              "official_TEST_rows": 0, "sealed_final64_model_outputs": 0,
              "operator_control_not_ABA_selected": True, "model_promotion_allowed": False,
              "training_rows": 733, "new_rows": 95, "new_tool_types": 31,
              "base_predictions_equal_P05_P07": 128,
              "groups": {group: {name: metrics(scores[name], strict[name], sorted(ids))
                                 for name in arms} for group, ids in groups.items()},
              "paired_strict": {comparison: {"gained": sum(not strict[a][i]["strict"] and strict[b][i]["strict"] for i in refs),
                                             "lost": sum(strict[a][i]["strict"] and not strict[b][i]["strict"] for i in refs)}
                                for comparison, a, b in (("E0_to_P07", "E0", "P07"),
                                                         ("P05_to_P07", "P05", "P07"))},
              "limitations": ["Exposed publisher-silver TRAIN-source DEV, not independent validation.",
                              "One P07 run cannot isolate a data effect from numerical run variation.",
                              "The 8 newly covered DEV tools are no longer unseen under the P07 training set."]}
    if OUT.exists():
        assert read(OUT) == result, "Frozen aggregate differs"
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "combined": result["groups"]["combined128"],
                      "official_TEST_rows": 0}, indent=2))


if __name__ == "__main__":
    main()
