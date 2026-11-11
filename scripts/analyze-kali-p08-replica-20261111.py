#!/usr/bin/env python3
"""Aggregate-only P07/P08 exact-repeat analysis on exposed internal DEV."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/benchkit/kali/src"))
import model_score  # noqa: E402

B = ROOT / "data/benchkit"
STUDY = B / "kali-redsage-aba-publisher-v2-2026-11-10"
P04 = B / "kali-redsage-p02-lr1e5-control-2026-11-10/gpu-attempt-a100-sxm4"
P05 = STUDY / "P05/gpu-attempt-a100"
P06 = STUDY / "P06/gpu-attempt-a100"
P07 = STUDY / "P07/gpu-attempt-a100"
P08 = STUDY / "P08/gpu-attempt-a100"
REF1 = B / "kali-redsage-publisher-holdout-2026-11-10/references-private.json"
REF2 = B / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"
LOCK = STUDY / "P08/analysis-lock-private.json"
OUT = B / "kali-p08-replica-analysis-2026-11-11/aggregate.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def pred(folder, arm):
    name = "base-predictions-private.json" if arm == "E0" else "candidate-predictions-private.json"
    rows = read(folder / name)
    assert len(rows) == len({r["id"] for r in rows}) == 128
    return {r["id"]: r["response"] for r in rows}


def means(scores, ids):
    return {field: sum(scores[i][field] for i in ids) / len(ids)
            for field in ("tool_score", "optional_f1", "positional_f1", "total_score")}


def main():
    lock = read(LOCK)
    assert lock["status"] == "P08_REPLICA_ANALYSIS_LOCK_BEFORE_OUTPUTS"
    assert lock["script_sha256"] == sha(Path(__file__))
    assert lock["reference_sha256"] == [sha(REF1), sha(REF2)]
    assert lock["p08_protocol_sha256"] == sha(STUDY / "P08/protocol-private.json")
    assert (STUDY / "P07/payload-private.json.gz").read_bytes() == (STUDY / "P08/payload-private.json.gz").read_bytes()
    assert (STUDY / "P07/train-encoded-private.json").read_bytes() == (STUDY / "P08/train-encoded-private.json").read_bytes()
    p7, p8 = read(STUDY / "P07/protocol-private.json"), read(STUDY / "P08/protocol-private.json")
    changed = {k for k in p7 if p7[k] != p8[k]}
    assert changed == {"candidate_id", "prepared_at_utc", "scope"}
    host, receipt, scored = read(P08 / "host-run-private.json"), read(P08 / "receipt-private.json"), read(P08 / "scores-private.json")
    assert host["status"] == "COLLECTED" and not host["cleanup_errors"] and host["remaining_owned_resources"] == 0
    assert receipt["status"] == "COMPLETE_ABA_CANDIDATE" and receipt["official_TEST_rows"] == 0
    assert receipt["optimizer_steps"] == receipt["nonzero_gradient_steps"] == 733
    assert receipt["adapter_reload_max_logit_delta"] <= 1e-4
    assert scored["official_TEST_rows"] == 0 and not scored["final64_used"]
    refs = {r["custom_id"]: r for p in (REF1, REF2) for r in read(p)}
    assert len(refs) == 128
    predictions = {"E0": pred(P08, "E0"), "P04": pred(P04, "P04"),
                   "P05": pred(P05, "P05"), "P06": pred(P06, "P06"),
                   "P07": pred(P07, "P07"), "P08": pred(P08, "P08")}
    assert all(set(p) == set(refs) for p in predictions.values())
    p07_base = pred(P07, "E0")
    assert all(predictions["E0"][i] == p07_base[i] for i in refs)
    scores = {arm: {i: model_score.score_one(refs[i], p[i]) for i in refs}
              for arm, p in predictions.items()}
    ids = sorted(refs)
    common = [i for i in ids if all(scores[a][i]["total_score"] < scores["E0"][i]["total_score"]
                                    for a in ("P04", "P05", "P06"))]
    assert len(common) == 29
    details = {arm: read(folder / "case-details-private.json")["base" if arm == "E0" else arm]
               for arm, folder in (("E0", P08), ("P07", P07), ("P08", P08))}
    assert all(abs(details[arm][i]["native_total"] - scores[arm][i]["total_score"]) < 1e-9
               for arm in details for i in ids)
    result = {
        "status": "P08_EXACT_REPEAT_EXPOSED_DEV_ANALYSIS",
        "official_TEST_rows": 0,
        "sealed_final64_model_outputs": 0,
        "operator_control_not_ABA_selected": True,
        "model_promotion_allowed": False,
        "same_payload_bytes": True,
        "same_encoded_rows_bytes": True,
        "same_training_settings_except_candidate_id_and_metadata": True,
        "training_rows": 733,
        "nonzero_gradient_steps": 733,
        "base_predictions_equal_P07_P08": 128,
        "candidate_predictions_equal_P07_P08": sum(predictions["P07"][i] == predictions["P08"][i] for i in ids),
        "mean_components": {arm: means(scores[arm], ids) for arm in ("E0", "P07", "P08")},
        "strict_correct": {arm: sum(details[arm][i]["strict"] for i in ids)
                           for arm in ("E0", "P07", "P08")},
        "paired_strict_E0_to_P08": {
            "gained": sum(not details["E0"][i]["strict"] and details["P08"][i]["strict"] for i in ids),
            "lost": sum(details["E0"][i]["strict"] and not details["P08"][i]["strict"] for i in ids),
        },
        "P08_minus_E0_native_mean": means(scores["P08"], ids)["total_score"] - means(scores["E0"], ids)["total_score"],
        "P08_minus_P07_native_mean": means(scores["P08"], ids)["total_score"] - means(scores["P07"], ids)["total_score"],
        "directional_replication_on_exposed_DEV": (
            means(scores["P08"], ids)["total_score"] > means(scores["E0"], ids)["total_score"]
            and sum(details["P08"][i]["strict"] for i in ids) >= sum(details["E0"][i]["strict"] for i in ids)
        ),
        "prior_common_harm29": {
            "rows": len(common),
            "P08_still_below_E0": sum(scores["P08"][i]["total_score"] < scores["E0"][i]["total_score"] for i in common),
            "means": {arm: means(scores[arm], common) for arm in ("E0", "P07", "P08")},
        },
        "limitations": [
            "Internal DEV was exposed before P08; replicate is not independent validation.",
            "P08 is an operator exact repeat, not an ABA-selected candidate.",
            "Training and DEV labels are publisher silver, not independent expert gold.",
            "A repeated direction cannot prove causal benefit of the 95 added rows.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    assert not OUT.exists(), "do not overwrite a prior aggregate"
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
