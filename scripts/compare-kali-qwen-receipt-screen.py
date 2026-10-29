#!/usr/bin/env python3
"""Compare two already completed Qwen SFT pilots on the same exposed internal DEV."""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from benchkit import load_jsonl, score_predictions


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(response, gold, truncated):
    blocks = re.findall(r"<output>\s*(.*?)\s*</output>", response, re.S)
    return len(blocks) == 1 and blocks[0].strip() == gold.strip() and not truncated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-summary", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    split = root / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28"
    manifest = json.loads((split / "manifest.json").read_text())
    dev_path = split / "pilot_dev.jsonl"
    assert sha(dev_path) == manifest["file_sha256"]["pilot_dev.jsonl"]
    dev = load_jsonl(dev_path)
    assert len(dev) == 128 and all(r["source_official_split"] == "train" and not r["official_test"] for r in dev)
    old_run = root / "docs/verification/kali-qwen-official-executed-pilot-2026-10-28/gpu-cycle"
    new_run = root / "data/benchkit/kali-qwen-receipt-screen-2026-10-29/gpu-cycle"
    screen = root / "data/benchkit/kali-qwen-receipt-screen-2026-10-29"
    screen_summary_path = args.public_summary.parent / "summary.json"
    screen_summary = json.loads(screen_summary_path.read_text())
    assert screen_summary["counts"]["no_lexical_failure_cue"] == 401
    new_train_path = screen / "receipt_clear_train_private.jsonl"
    assert sha(new_train_path) == screen_summary["private_derived_sha256"]["receipt_clear_train"]
    new_tools = {r["native_label"]["tool_name"] for r in load_jsonl(new_train_path)}
    assert len(new_tools) == 232
    phases = {}
    hashes = {"internal_dev128": sha(dev_path), "screened_train401": sha(new_train_path)}
    for arm, run in (("original512", old_run), ("receipt_screen401", new_run)):
        receipt_path = run / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        protocol_path = run / "frozen-protocol.json"
        assert receipt["status"] == "COMPLETE" and receipt["optimizer_steps"] == 512
        assert receipt["official_TEST_rows"] == 0 and receipt["development_gradient_rows"] == 0
        assert sha(protocol_path) == receipt["protocol_sha256"]
        hashes[arm + "_receipt"] = sha(receipt_path)
        for phase in ("baseline", "post_sft"):
            path = run / f"{phase}-predictions-private.json"
            assert sha(path) == receipt[phase + "_sha256"]
            predictions = json.loads(path.read_text())
            assert len(predictions) == 128 and {p["id"] for p in predictions} == {r["id"] for r in dev}
            scored = score_predictions(dev, predictions, "kali")
            strict = {d["id"]: bool(d["strict_option_value_correct"]) for d in scored["details"]}
            by_id = {p["id"]: p for p in predictions}
            gold = {r["id"]: r["native_label"]["ground_truth_command"] for r in dev}
            phases[(arm, phase)] = {"predictions": by_id, "strict": strict,
                                    "exact": {i: exact(p["response"], gold[i], p["truncated"])
                                              for i, p in by_id.items()},
                                    "score": scored["summary"]}
            hashes[arm + "_" + phase] = sha(path)

    old_baseline = phases[("original512", "baseline")]
    new_baseline = phases[("receipt_screen401", "baseline")]
    baseline_identical = all(old_baseline["predictions"][i]["response"] == new_baseline["predictions"][i]["response"]
                             for i in old_baseline["predictions"])
    pair = collections.Counter()
    strata = collections.defaultdict(list)
    private_rows = []
    for row in dev:
        i = row["id"]
        old = phases[("original512", "post_sft")]["strict"][i]
        new = phases[("receipt_screen401", "post_sft")]["strict"][i]
        state = "both_correct" if old and new else "original_only" if old else "screened_only" if new else "both_wrong"
        pair[state] += 1
        bucket = "tool_retained" if row["native_label"]["tool_name"] in new_tools else "tool_lost_by_screen"
        strata[bucket].append((old, new))
        private_rows.append({"id": i, "tool": row["native_label"]["tool_name"],
                             "tool_retained_in_screened401": bucket == "tool_retained",
                             "original_post_strict": old, "screened_post_strict": new,
                             "comparison_state": state})

    def summarize(arm, phase):
        v = phases[(arm, phase)]
        return {"strict_correct": sum(v["strict"].values()),
                "exact_gold_command": sum(v["exact"].values()),
                "truncated": sum(p["truncated"] for p in v["predictions"].values()),
                "complete_output_block": sum(bool(re.search(r"<output>.*?</output>", p["response"], re.S))
                                             for p in v["predictions"].values()),
                "native_total_score": v["score"]["total_score"]}

    results = {arm: {phase: summarize(arm, phase) for phase in ("baseline", "post_sft")}
               for arm in ("original512", "receipt_screen401")}
    assert results["original512"]["baseline"]["strict_correct"] == 29
    assert results["original512"]["post_sft"]["strict_correct"] == 43
    assert sum(pair.values()) == 128
    stratum_public = {key: {"rows": len(values), "original_post_correct": sum(a for a, b in values),
                            "screened_post_correct": sum(b for a, b in values)}
                      for key, values in strata.items()}
    public = {"status": "EXPLORATORY_REUSED_INTERNAL_DEV_COMPARISON_NOT_BLIND",
              "source_sha256": hashes,
              "scope": "Both arms use publisher official-TRAIN internal DEV128; no official TEST or source-separated validation",
              "baseline_responses_identical": baseline_identical,
              "results": results,
              "paired_post_strict": dict(sorted(pair.items())),
              "by_screened_tool_coverage": stratum_public,
              "limitations": ["Screening used only TRAIN terminal receipts, not DEV outputs, but DEV128 was already queried in the older experiment.",
                              "The screened arm has 401 unique rows repeated to 512 exposures, losing 43 tools; this is not a single-factor semantic-label-quality test.",
                              "Publisher silver labels and automated strict scoring are not independent human semantic verification.",
                              "No model promotion is warranted from this exposed internal comparison."],
              "official_TEST_rows": 0, "independent_human_signoffs": 0}
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps({"public": public, "cases": private_rows}, indent=2) + "\n")
    args.public_summary.write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps({"status": public["status"], "results": results,
                      "paired_post_strict": public["paired_post_strict"],
                      "by_screened_tool_coverage": stratum_public}, indent=2))


if __name__ == "__main__":
    main()
