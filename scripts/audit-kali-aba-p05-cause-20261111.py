#!/usr/bin/env python3
"""Read-only, aggregate cause audit for the frozen P04/P05 KaliBench runs.

The script never prints prompts, commands, sample IDs, or individual predictions.
It does not load official TEST or sealed final64 references.
"""

import collections
import gzip
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/benchkit/kali/src"))
import model_score  # noqa: E402

P04 = ROOT / "data/benchkit/kali-redsage-p02-lr1e5-control-2026-11-10/gpu-attempt-a100-sxm4"
P05 = ROOT / "data/benchkit/kali-redsage-aba-publisher-v2-2026-11-10/P05/gpu-attempt-a100"
P05_FROZEN = P05.parent
DEV1 = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10/references-private.json"
DEV2 = ROOT / "data/benchkit/kali-redsage-publisher-confirm64-2026-11-10/references-private.json"
SCREENED = ROOT / "data/benchkit/kali-screened/train.jsonl"
PUBLISHER = ROOT / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
FINAL_INPUTS = ROOT / "data/benchkit/kali-redsage-aba-final64-2026-11-10/inputs-private.json.gz"
IDS = ROOT / "data/benchkit/kali-qwen-expanded-2026-10-30/selection-ids-private.json"
OUT = ROOT / "data/benchkit/kali-aba-p05-cause-2026-11-11/aggregate.json"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(items):
    items = list(items)
    return sum(items) / len(items)


def predictions(folder, arm):
    rows = read(folder / ("base-predictions-private.json" if arm == "base" else "candidate-predictions-private.json"))
    assert len(rows) == len({row["id"] for row in rows}) == 128
    return {row["id"]: row for row in rows}


def components(pred, refs):
    return {case_id: model_score.score_one(refs[case_id], row["response"])
            for case_id, row in pred.items()}


def component_means(data, cases):
    return {field: mean(data[k][field] for k in cases)
            for field in ("tool_score", "optional_f1", "positional_f1", "total_score")}


def log_trace(path):
    trace = {}
    for line in path.read_text().splitlines():
        if line.startswith("TRAIN {"):
            step = json.loads(line[6:])
            trace[step["step"]] = step
    return trace


def main():
    manifest = read(P05_FROZEN / "freeze-manifest-private.json")
    protocol = read(P05 / "protocol-private.json")
    control_protocol = read(P04 / "protocol-private.json")
    assert manifest["status"] == "ABA_CANDIDATE_FROZEN_BEFORE_OUTPUTS"
    assert digest(P05_FROZEN / "protocol-private.json") == manifest["protocol_sha256"]
    assert protocol["candidate_id"] == "P05" and protocol["official_TEST_rows"] == 0
    for field in ("checkpoint_files", "runtime_archive_sha256", "payload_sha256",
                  "encoded_sha256", "LoRA_config", "optimizer", "initialization_seed",
                  "inference_seed", "batch_size", "max_new_tokens", "allowed_GPU_models",
                  "expected_packages", "resource_request"):
        assert control_protocol[field] == protocol[field], field
    assert digest(DEV1) == manifest["dev1_references_sha256"]
    assert digest(DEV2) == manifest["dev2_references_sha256"]
    refs1 = {r["custom_id"]: r for r in read(DEV1)}
    refs2 = {r["custom_id"]: r for r in read(DEV2)}
    assert len(refs1) == len(refs2) == 64 and not set(refs1) & set(refs2)
    refs = refs1 | refs2
    base4, base5 = predictions(P04, "base"), predictions(P05, "base")
    pred4, pred5 = predictions(P04, "P04"), predictions(P05, "P05")
    assert set(refs) == set(base4) == set(base5) == set(pred4) == set(pred5)
    assert all(base4[k]["response"] == base5[k]["response"] for k in refs)
    details = read(P05 / "case-details-private.json")
    assert set(details) == {"base", "P05"}
    assert set(details["base"]) == set(details["P05"]) == set(refs)
    score = {"base": components(base5, refs), "P04": components(pred4, refs),
             "P05": components(pred5, refs)}
    for arm in ("base", "P05"):
        for k in refs:
            assert abs(score[arm][k]["total_score"] - details[arm][k]["native_total"]) < 1e-9
    cases = sorted(refs)
    means = {arm: component_means(values, cases) for arm, values in score.items()}
    per_panel = {}
    for name, panel in (("DEV1", refs1), ("DEV2", refs2)):
        per_panel[name] = {arm: component_means(values, panel) for arm, values in score.items()}
    strict = {arm: {k: bool(details[arm][k]["strict"]) for k in cases}
              for arm in ("base", "P05")}
    paired = collections.Counter()
    for k in cases:
        a, b = strict["base"][k], strict["P05"][k]
        paired[(a, b)] += 1
    different = [k for k in cases if pred4[k]["response"] != pred5[k]["response"]]
    position_declines = [k for k in cases if score["P05"][k]["positional_f1"] < score["base"][k]["positional_f1"]]
    additional_positionals = 0
    no_gold_positionals = 0
    for k in position_declines:
        label = refs[k]
        gt = collections.Counter(model_score.parse_positional_args(label.get("positional_args")))
        flags = model_score.get_flags_with_values(model_score.parse_optional_args(label.get("optional_args")))
        _, _, parsed = model_score.parse_command(score["P05"][k]["pred_cmd"], flags)
        additional_positionals += bool(collections.Counter(parsed) - gt)
        no_gold_positionals += not gt
    publisher = [json.loads(line) for line in PUBLISHER.open()]
    verified = {r["custom_id"] for r in publisher
                if r["terminal_verification"]["label"] == "PASS_EXECUTED"
                and r["model_verification"]["model_output"]["verdict"] == "ACCURATE"}
    screened = {r["id"]: r for r in map(json.loads, SCREENED.open())}
    ids = read(IDS)
    train_ids = set(ids["old_ai505_train"] + ids["added_train133"])
    final_inputs = json.loads(gzip.decompress(FINAL_INPUTS.read_bytes()))["holdout"]
    assert all(set(r) == {"id", "native_messages"} for r in final_inputs)
    final_ids = {r["id"] for r in final_inputs}
    assert len(train_ids) == 638 and len(final_ids) == 64
    assert not train_ids & set(refs) and not train_ids & final_ids and not set(refs) & final_ids
    assert train_ids <= verified
    train_tool_count = collections.Counter(screened[k]["native_label"]["tool_name"] for k in train_ids)
    coverage = {}
    for label, subset in (("unseen", lambda n: n == 0), ("one", lambda n: n == 1),
                          ("two", lambda n: n == 2), ("three_or_more", lambda n: n >= 3)):
        group = [k for k in cases if subset(train_tool_count[refs[k]["tool_name"]])]
        coverage[label] = {"rows": len(group),
                           "base_strict": sum(strict["base"][k] for k in group),
                           "P05_strict": sum(strict["P05"][k] for k in group),
                           "base_native": mean(score["base"][k]["total_score"] for k in group),
                           "P05_native": mean(score["P05"][k]["total_score"] for k in group)}
    t4, t5 = log_trace(P04 / "worker-log-private.txt"), log_trace(P05 / "worker-log-private.txt")
    shared = sorted(set(t4) & set(t5))
    assert 1 in shared
    output = {
        "status": "READ_ONLY_AGGREGATE_CAUSE_AUDIT",
        "official_TEST_rows": 0, "sealed_final64_model_outputs": 0,
        "training_target_self_score_full": sum(
            model_score.score_one(screened[k]["native_label"], screened[k]["target"])["total_score"] == 1
            for k in train_ids),
        "score_formula": "mean(tool_score, optional_f1, positional_f1)",
        "component_means": means, "panel_means": per_panel,
        "strict_pairs": {"both_wrong": paired[(False, False)], "gained": paired[(False, True)],
                         "lost": paired[(True, False)], "both_correct": paired[(True, True)]},
        "P04_P05_base_predictions_equal": 128,
        "P04_P05_candidate_predictions_different": len(different),
        "P04_P05_native_difference_on_different_only": sum(
            score["P05"][k]["total_score"] - score["P04"][k]["total_score"] for k in different),
        "P04_P05_native_difference_on_equal_only": sum(
            score["P05"][k]["total_score"] - score["P04"][k]["total_score"] for k in cases if k not in different),
        "positional_decline_rows": len(position_declines),
        "positional_decline_with_additional_parsed_positional": additional_positionals,
        "positional_decline_with_no_gold_positional": no_gold_positionals,
        "publisher_PASS_EXECUTED_ACCURATE_total": len(verified),
        "publisher_verified_screened": len(verified & set(screened)),
        "verified_unused_after_train_dev_final": len(verified - train_ids - set(refs) - final_ids),
        "verified_unused_screened_after_train_dev_final": len((verified - train_ids - set(refs) - final_ids) & set(screened)),
        "training_tools": len(train_tool_count),
        "training_single_example_tools": sum(n == 1 for n in train_tool_count.values()),
        "coverage_posthoc": coverage,
        "logged_training_steps_both": len(shared),
        "first_step_loss_equal": t4[1]["loss"] == t5[1]["loss"],
        "first_step_gradient_norm_equal": t4[1]["gradient_norm_before_clip"] == t5[1]["gradient_norm_before_clip"],
        "logged_loss_equal_steps": sum(t4[k]["loss"] == t5[k]["loss"] for k in shared),
        "logged_gradient_norm_equal_steps": sum(t4[k]["gradient_norm_before_clip"] == t5[k]["gradient_norm_before_clip"] for k in shared),
        "interpretation_limit": "Descriptive paired audit; does not isolate numerical nondeterminism or prove a data-quality causal effect."
    }
    assert output["training_target_self_score_full"] == 638
    assert sum(x["rows"] for x in coverage.values()) == 128
    if OUT.exists():
        assert read(OUT) == output, "Frozen audit differs; do not overwrite"
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
