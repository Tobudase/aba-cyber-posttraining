#!/usr/bin/env python3
"""Aggregate-only audit of CLI value syntax and frozen KaliBench parsing.

Reads local TRAIN-source DEV and model predictions. Does not load official TEST,
sealed final64 or execute generated commands. Output has no sample IDs or text.
"""

import collections
import json
from pathlib import Path
import shlex
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/benchkit/kali/src"))
import model_score as scorer  # noqa: E402

B = ROOT / "data/benchkit"
REFS = [
    B / "kali-redsage-publisher-holdout-2026-11-10/references-private.json",
    B / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json",
]
RUNS = {
    "E0": B / "kali-redsage-aba-publisher-v2-2026-11-10/P07/gpu-attempt-a100",
    "P04": B / "kali-redsage-p02-lr1e5-control-2026-11-10/gpu-attempt-a100-sxm4",
    "P05": B / "kali-redsage-aba-publisher-v2-2026-11-10/P05/gpu-attempt-a100",
    "P06": B / "kali-redsage-aba-publisher-v2-2026-11-10/P06/gpu-attempt-a100",
    "P07": B / "kali-redsage-aba-publisher-v2-2026-11-10/P07/gpu-attempt-a100",
}
ENCODED = B / "kali-redsage-aba-publisher-v2-2026-11-10/P07/train-encoded-private.json"
SOURCE = B / "kali-screened/train.jsonl"
OUT = B / "kali-sft-syntax-audit-2026-11-11/aggregate.json"


def read(path):
    return json.loads(path.read_text())


def allowed_flags(label):
    return {flag for group in scorer.parse_optional_args(label.get("optional_args"))
            for flag in group.split("|")}


def prediction_map(folder, arm):
    name = "base-predictions-private.json" if arm == "E0" else "candidate-predictions-private.json"
    rows = read(folder / name)
    assert len(rows) == len({row["id"] for row in rows}) == 128
    return {row["id"]: row["response"] for row in rows}


def syntax(tokens, allowed):
    equals, spaced = set(), set()
    for j, token in enumerate(tokens[1:], 1):
        if not token.startswith("-"):
            continue
        if "=" in token:
            flag = token.split("=", 1)[0]
            if flag not in allowed:
                equals.add(flag)
        elif token not in allowed and j + 1 < len(tokens) and not tokens[j + 1].startswith("-"):
            spaced.add(token)
    return equals, spaced


def main():
    refs = {row["custom_id"]: row for path in REFS for row in read(path)}
    assert len(refs) == 128
    assert all(scorer.score_one(ref, "<output>" + ref["ground_truth_command"] + "</output>")["total_score"] == 1
               for ref in refs.values())
    predictions = {name: prediction_map(folder, name) for name, folder in RUNS.items()}
    assert all(set(predictions[name]) == set(refs) for name in predictions)
    scores = {name: {case: scorer.score_one(refs[case], response)
                     for case, response in rows.items()}
              for name, rows in predictions.items()}
    assert all(predictions["E0"][case] == prediction_map(RUNS["P05"], "E0")[case]
               for case in refs)

    # Pin a harmless synthetic demonstration of the parser's value treatment.
    toy = {"tool_name": "toy", "ground_truth_command": "toy --allowed x",
           "optional_args": {"--allowed": "x"}, "positional_args": []}
    toy_equals = scorer.score_one(toy, "<output>toy --unsupported=y</output>")
    toy_space = scorer.score_one(toy, "<output>toy --unsupported y</output>")
    assert toy_equals["tool_score"] == toy_space["tool_score"] == 1
    assert toy_equals["optional_f1"] == toy_space["optional_f1"] == 0
    assert toy_equals["positional_f1"] == 1 and toy_space["positional_f1"] == 0

    source = {row["id"]: row for row in map(json.loads, SOURCE.open())}
    train_ids = [row["id"] for row in read(ENCODED)]
    assert len(train_ids) == len(set(train_ids)) == 733
    train = {}
    by_tool = collections.defaultdict(list)
    for label, ids in (("old638", train_ids[:638]), ("new95", train_ids[638:])):
        counts = collections.Counter()
        for case in ids:
            row = source[case]
            reference = row["native_label"]
            assert scorer.extract_command_from_output(row["target"]) == reference["ground_truth_command"]
            by_tool[reference["tool_name"]].append(reference)
            flags = scorer.get_flags_with_values(scorer.parse_optional_args(reference.get("optional_args")))
            tokens = shlex.split(reference["ground_truth_command"])
            equal = sum(token.startswith("-") and "=" in token and token.split("=", 1)[0] in flags
                        for token in tokens[1:])
            space = sum(token in flags and j + 1 < len(tokens) and not tokens[j + 1].startswith("-")
                        for j, token in enumerate(tokens[1:], 1))
            counts["rows_known_value_equals"] += bool(equal)
            counts["rows_known_value_space"] += bool(space)
            counts["tokens_known_value_equals"] += equal
            counts["tokens_known_value_space"] += space
        train[label] = {"rows": len(ids), **counts}

    output_syntax = {}
    for arm in RUNS:
        counts = collections.Counter()
        for case in refs:
            command = scores[arm][case]["pred_cmd"]
            tokens = [] if command == scorer.FORMAT_ERROR_TOKEN else shlex.split(command)
            equal, space = syntax(tokens, allowed_flags(refs[case]))
            counts["rows_out_of_reference_equals"] += bool(equal)
            counts["rows_out_of_reference_space"] += bool(space)
            counts["tokens_out_of_reference_equals"] += len(equal)
            counts["tokens_out_of_reference_space"] += len(space)
        output_syntax[arm] = dict(counts)

    common = [case for case in refs if all(scores[arm][case]["total_score"] < scores["E0"][case]["total_score"]
                                                for arm in ("P04", "P05", "P06"))]
    assert len(common) == 29
    counts = collections.Counter()
    original_total = counterfactual_total = original_pos = counterfactual_pos = 0.0
    for case in common:
        ref = refs[case]
        allowed = allowed_flags(ref)
        value_flags = scorer.get_flags_with_values(scorer.parse_optional_args(ref.get("optional_args")))
        base_tokens = shlex.split(scores["E0"][case]["pred_cmd"])
        p07_tokens = shlex.split(scores["P07"][case]["pred_cmd"])
        base_equal, base_space = syntax(base_tokens, allowed)
        p07_equal, p07_space = syntax(p07_tokens, allowed)
        counts["E0_outref_equal_rows"] += bool(base_equal)
        counts["E0_outref_space_rows"] += bool(base_space)
        counts["P07_outref_equal_rows"] += bool(p07_equal)
        counts["P07_outref_space_rows"] += bool(p07_space)
        counts["same_flag_E0_equals_P07_space_rows"] += bool(base_equal & p07_space)
        counts["P07_unknown_flag_rows"] += any(flag not in allowed for flag in
                                               scorer.parse_command(scores["P07"][case]["pred_cmd"], value_flags)[1])
        train_flags = {flag for label in by_tool[ref["tool_name"]]
                       for group in scorer.parse_optional_args(label.get("optional_args"))
                       for flag in group.split("|")}
        required_groups = [set(group.split("|"))
                           for group in scorer.parse_optional_args(ref.get("optional_args"))]
        covered_groups = [bool(group & train_flags) for group in required_groups]
        counts["reference_required_flag_groups"] += len(required_groups)
        counts["reference_required_flag_groups_seen_in_same_tool_train"] += sum(covered_groups)
        counts["rows_all_reference_flag_groups_seen_in_same_tool_train"] += all(covered_groups)
        counts["rows_no_reference_flag_group_seen_in_same_tool_train"] += not any(covered_groups)
        counts["P07_outref_flag_seen_same_tool_train_rows"] += bool(p07_space & train_flags)
        _, _, predicted_positionals = scorer.parse_command(scores["P07"][case]["pred_cmd"], value_flags)
        gold_positionals = scorer.parse_positional_args(ref.get("positional_args"))
        extras = collections.Counter(predicted_positionals) - collections.Counter(gold_positionals)
        counts["P07_extra_pos_rows"] += bool(extras)
        filtered = []
        for j, token in enumerate(p07_tokens[1:], 1):
            if token.startswith("-") or (j > 1 and p07_tokens[j - 1] in value_flags):
                continue
            if (j > 1 and p07_tokens[j - 1] in p07_space and extras[token] > 0):
                extras[token] -= 1
                counts["hypothetically_removed_extra_tokens"] += 1
            else:
                filtered.append(token)
        old = scores["P07"][case]
        new_pos = scorer.positional_f1(gold_positionals, filtered)
        new_total = (old["tool_score"] + old["optional_f1"] + new_pos) / 3
        counts["hypothetical_pos_improved_rows"] += new_pos > old["positional_f1"]
        counts["hypothetical_no_longer_below_E0_rows"] += new_total >= scores["E0"][case]["total_score"]
        original_total += old["total_score"]
        counterfactual_total += new_total
        original_pos += old["positional_f1"]
        counterfactual_pos += new_pos

    result = {
        "status": "POSTHOC_SYNTAX_AND_SCORER_MECHANISM_AUDIT",
        "official_TEST_rows": 0,
        "sealed_final64_model_outputs": 0,
        "DEV_reference_self_score_full": 128,
        "synthetic_wrong_flag_equals_positional_f1": toy_equals["positional_f1"],
        "synthetic_wrong_flag_space_positional_f1": toy_space["positional_f1"],
        "training_reference_syntax": train,
        "model_output_out_of_reference_flag_syntax": output_syntax,
        "prior_three_run_common_harm": {
            "rows": len(common), **dict(counts),
            "P07_original_mean_positional_f1": original_pos / len(common),
            "P07_hypothetical_mean_positional_f1": counterfactual_pos / len(common),
            "P07_original_mean_total": original_total / len(common),
            "P07_hypothetical_mean_total": counterfactual_total / len(common),
        },
        "interpretation": (
            "The frozen parser treats a value after an unrecognized flag as positional when space-separated, "
            "but not when joined with '='. The hypothetical filtering is diagnostic only: an unrecognized flag "
            "remains incorrect and some filtered tokens might be intended positionals. This does not replace "
            "the official score or identify a unique causal effect of SFT data."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        assert read(OUT) == result, "existing aggregate differs"
    else:
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
