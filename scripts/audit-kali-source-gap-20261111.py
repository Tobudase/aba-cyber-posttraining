#!/usr/bin/env python3
"""Read-only, aggregate check of remaining publisher-verified TRAIN supply."""

import collections
import gzip
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/benchkit/kali/src"))
import model_score  # noqa: E402

B = ROOT / "data/benchkit"
STUDY = B / "kali-redsage-aba-publisher-v2-2026-11-10"
P07 = STUDY / "P07"
RUNS = {
    "E0": STUDY / "P07/gpu-attempt-a100",
    "P04": B / "kali-redsage-p02-lr1e5-control-2026-11-10/gpu-attempt-a100-sxm4",
    "P05": STUDY / "P05/gpu-attempt-a100",
    "P06": STUDY / "P06/gpu-attempt-a100",
}
REFS = [B / "kali-redsage-publisher-holdout-2026-11-10/references-private.json",
        B / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"]
PUBLISHER = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
SCREENED = B / "kali-screened/train.jsonl"
HELD = B / "kali-screened/hold.jsonl"
FINAL = B / "kali-redsage-aba-final64-2026-11-10/inputs-private.json.gz"
OUT = B / "kali-source-gap-2026-11-11/aggregate.json"


def read(path):
    return json.loads(path.read_text())


def predictions(folder, arm):
    filename = "base-predictions-private.json" if arm == "E0" else "candidate-predictions-private.json"
    rows = read(folder / filename)
    assert len(rows) == len({row["id"] for row in rows}) == 128
    return {row["id"]: row["response"] for row in rows}


def main():
    refs = {r["custom_id"]: r for path in REFS for r in read(path)}
    assert len(refs) == 128
    scored = {arm: {i: model_score.score_one(refs[i], p)
                    for i, p in predictions(folder, arm).items()}
              for arm, folder in RUNS.items()}
    harmed = [i for i in refs if all(scored[a][i]["total_score"] < scored["E0"][i]["total_score"]
                                   for a in ("P04", "P05", "P06"))]
    assert len(harmed) == 29
    publisher = {r["custom_id"]: r for r in map(json.loads, PUBLISHER.open())}
    verified = {i for i, r in publisher.items()
                if r["terminal_verification"]["label"] == "PASS_EXECUTED"
                and r["model_verification"]["model_output"]["verdict"] == "ACCURATE"}
    screened = {r["id"] for r in map(json.loads, SCREENED.open())}
    held = {r["id"] for r in map(json.loads, HELD.open())}
    assert len(verified) == 954 and len(verified & screened) == 936
    assert verified - screened <= held and len(verified - screened) == 18
    payload = json.loads(gzip.decompress((P07 / "payload-private.json.gz").read_bytes()))
    used = {r["id"] for kind in ("train_rows", "dev1", "dev2", "anchors") for r in payload[kind]}
    final = {r["id"] for r in json.loads(gzip.decompress(FINAL.read_bytes()))["holdout"]}
    used |= final
    verified_unused_screened = (verified & screened) - used
    assert len(verified_unused_screened) == 11
    freeze = read(P07 / "freeze-manifest-private.json")
    assert freeze["excluded_protected_command_group"] == 8
    assert freeze["excluded_duplicate_new_command_group"] == 3
    old_train = {r["id"] for r in payload["train_rows"]}
    source = {r["id"]: r for r in map(json.loads, SCREENED.open())}
    by_tool = collections.defaultdict(set)
    for i in old_train:
        label = source[i]["native_label"]
        for group in model_score.parse_optional_args(label.get("optional_args")):
            by_tool[label["tool_name"]].update(group.split("|"))
    held_by_tool = collections.defaultdict(set)
    for i in verified - screened:
        r = publisher[i]
        for group in model_score.parse_optional_args(r.get("optional_args")):
            held_by_tool[r["tool_name"]].update(group.split("|"))
    required = covered_old = covered_held = held_tool_rows = 0
    for i in harmed:
        label = refs[i]
        groups = [set(g.split("|")) for g in model_score.parse_optional_args(label.get("optional_args"))]
        required += len(groups)
        covered_old += sum(bool(g & by_tool[label["tool_name"]]) for g in groups)
        held_tool_rows += label["tool_name"] in held_by_tool
        covered_held += sum(bool(g & held_by_tool.get(label["tool_name"], set())) for g in groups)
    result = {
        "status": "READ_ONLY_PUBLISHER_TRAIN_SOURCE_GAP_AUDIT",
        "official_TEST_rows": 0,
        "sealed_final64_model_outputs": 0,
        "verified_PASS_EXECUTED_ACCURATE_total": len(verified),
        "verified_in_screened": len(verified & screened),
        "verified_held_for_nonperfect_gold_echo": len(verified - screened),
        "verified_screened_in_P07_train_DEV_final": len((verified & screened) & used),
        "verified_screened_unused_excluded_by_P07_group_rules": len(verified_unused_screened),
        "unused_protected_command_group": freeze["excluded_protected_command_group"],
        "unused_duplicate_new_command_group": freeze["excluded_duplicate_new_command_group"],
        "prior_common_harm_rows": len(harmed),
        "reference_required_flag_groups": required,
        "groups_covered_in_P07_train": covered_old,
        "harm_rows_with_matching_tool_in_verified_held": held_tool_rows,
        "required_groups_covered_by_verified_held": covered_held,
        "interpretation": (
            "No additional ready-to-admit, group-distinct PASS_EXECUTED/ACCURATE rows remain in the current "
            "screened publisher TRAIN pool. The 18 publisher-verified held rows failed the prior native "
            "gold-echo screen and require scorer/label reconciliation; none supplies a missing required "
            "flag group for the 29 harmed cases. Other external or authored data were not surveyed here."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        assert read(OUT) == result, "existing aggregate differs"
    else:
        OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
