#!/usr/bin/env python3
"""Score frozen unqueried KaliBench TRAIN-internal DEV on host, never run commands."""

import hashlib
import json
import re
from pathlib import Path

from benchkit import load_jsonl, score_predictions


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-qwen-confirmation-2026-10-28"
RUN = ROOT / "docs/verification/kali-qwen-confirmation-2026-10-28/gpu-cycle"
TRAIN = ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_train.jsonl"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(prediction, reference):
    blocks = re.findall(r"<output>\s*(.*?)\s*</output>", prediction["response"], re.S)
    return len(blocks) == 1 and blocks[0].strip() == reference.strip() and not prediction["truncated"]


def summarize(rows, predictions):
    score = score_predictions(rows, predictions, "kali")
    by_id = {r["id"]: r for r in rows}
    exact_by_id = {p["id"]: exact(p, by_id[p["id"]]["native_label"]["ground_truth_command"])
                   for p in predictions}
    strict = {d["id"]: bool(d["strict_option_value_correct"]) for d in score["details"]}
    summary = dict(score["summary"])
    summary.update(exact_command_count=sum(exact_by_id.values()),
                   exact_command_percent=sum(exact_by_id.values()) / len(rows) * 100,
                   strict_correct_count=sum(strict.values()),
                   complete_output_blocks=sum(bool(re.search(r"<output>.*?</output>", p["response"], re.S))
                                              for p in predictions),
                   truncated_rows=sum(p["truncated"] for p in predictions))
    return summary, strict, exact_by_id


def transition(before, after):
    assert set(before) == set(after)
    counts = {"both_correct": 0, "gained": 0, "lost": 0, "both_wrong": 0}
    for identifier in before:
        a, b = before[identifier], after[identifier]
        key = "both_correct" if a and b else "gained" if not a and b else "lost" if a and not b else "both_wrong"
        counts[key] += 1
    assert sum(counts.values()) == len(before)
    return counts


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    p = json.loads((RUN / "frozen-protocol.json").read_text())
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert manifest["status"] == "FROZEN_93_INPUTS_BEFORE_MODEL_OUTPUTS"
    assert p["status"] == "FROZEN_BEFORE_93_MODEL_OUTPUTS"
    assert sha(DATA / "manifest.json") == p["selection_manifest_sha256"]
    assert sha(RUN / "frozen-protocol.json") == receipt["protocol_sha256"]
    assert receipt["status"] == "COMPLETE_INFERENCE_ONLY"
    assert receipt["prior_GPU_receipt_sha256"] == p["prior_GPU_receipt_sha256"]
    assert receipt["adapter_sha256"] == p["adapter_sha256"]
    assert receipt["official_TEST_rows"] == receipt["optimizer_steps"] == 0
    assert json.loads((RUN / "cleanup.json").read_text())["errors"] == []
    assert sha(DATA / "dev93-private.jsonl") == manifest["file_sha256"]["dev93-private.jsonl"]
    selection_path = DATA / "selection-ids-private.json"
    assert sha(selection_path) == manifest["file_sha256"]["selection-ids-private.json"]
    selection = json.loads(selection_path.read_text())
    rows = load_jsonl(DATA / "dev93-private.jsonl")
    assert len(rows) == 93 and {r["id"] for r in rows} == set(selection["all93"])
    assert all(r["split"] == "dev" and r["source_official_split"] == "train" and
               r["training_eligible"] is False and r["official_test"] is False for r in rows)
    train_tools = {r["native_label"]["tool_name"] for r in load_jsonl(TRAIN)}
    primary_ids = set(selection["primary87"])
    unseen_tools_ids = {r["id"] for r in rows if r["id"] in primary_ids and
                        r["native_label"]["tool_name"] not in train_tools}
    assert len(primary_ids) == 87 and len(unseen_tools_ids) == 22
    assert len(selection["shared_prior_dev_command_group6"]) == 6
    assert len(selection["prompt_embeds_gold1"]) == 1 and not primary_ids.intersection(selection["prompt_embeds_gold1"])
    all_ids = {r["id"] for r in rows}
    sets = {"primary87": primary_ids, "all93": all_ids,
            "primary_tool_absent_from_train22": unseen_tools_ids,
            "all93_without_prompt_embedded_gold92": all_ids - set(selection["prompt_embeds_gold1"])}
    result = {"status": "SCORED_FROZEN_UNQUERIED_INTERNAL_DEV", "model_id": p["model_id"],
              "model_revision": p["model_revision"], "GPU": receipt["GPU"],
              "precision": p["precision"], "optimizer_steps_this_run": 0,
              "official_TEST_rows": 0, "prior_adapter_sha256": p["adapter_sha256"],
              "selection_manifest_sha256": p["selection_manifest_sha256"],
              "protocol_sha256": receipt["protocol_sha256"], "GPU_receipt_sha256": sha(RUN / "receipt.json"),
              "all93_model_predictions_before_this_run": 0,
              "scope": "KaliBench official TRAIN internal holdout only, not official TEST or external validation",
              "sets": {}}
    predictions = {}
    for phase in ("baseline", "post_sft"):
        path = RUN / (phase + "-predictions-private.json")
        assert sha(path) == receipt[phase + "_sha256"]
        records = json.loads(path.read_text())
        assert len(records) == 93 and {r["id"] for r in records} == all_ids
        assert all(r["phase"] == phase for r in records)
        predictions[phase] = {r["id"]: r for r in records}
    for name, selected in sets.items():
        subset = [r for r in rows if r["id"] in selected]
        phase = {}
        flags = {}
        for key in ("baseline", "post_sft"):
            pred = [predictions[key][r["id"]] for r in subset]
            summary, strict, exact_by_id = summarize(subset, pred)
            phase[key] = summary
            flags[key] = {"strict": strict, "exact_command": exact_by_id}
        result["sets"][name] = {
            "rows": len(subset), "baseline": phase["baseline"], "post_sft": phase["post_sft"],
            "paired": {metric: transition(flags["baseline"][metric], flags["post_sft"][metric])
                       for metric in ("strict", "exact_command")}}
    (RUN / "scores-private.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({name: {"rows": data["rows"],
                             "strict_before": data["baseline"]["strict_correct_count"],
                             "strict_after": data["post_sft"]["strict_correct_count"],
                             "exact_before": data["baseline"]["exact_command_count"],
                             "exact_after": data["post_sft"]["exact_command_count"],
                             "paired_strict": data["paired"]["strict"]}
                      for name, data in result["sets"].items()}))


if __name__ == "__main__":
    main()
