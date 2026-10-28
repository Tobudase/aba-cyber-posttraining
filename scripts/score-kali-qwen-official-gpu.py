#!/usr/bin/env python3
"""Recompute paired internal-DEV metrics locally; never execute commands."""

import hashlib
import json
import re
from pathlib import Path

from benchkit import load_jsonl, score_predictions


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "docs/verification/kali-qwen-official-executed-pilot-2026-10-28"
RUN = PRIVATE / "gpu-cycle"
SPLIT = ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_command(response, reference):
    blocks = re.findall(r"<output>\s*(.*?)\s*</output>", response, re.S)
    return len(blocks) == 1 and blocks[0].strip() == reference.strip()


def main():
    manifest = json.loads((SPLIT / "manifest.json").read_text())
    protocol = json.loads((RUN / "frozen-protocol.json").read_text())
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert receipt["status"] == "COMPLETE" and receipt["optimizer_steps"] == 512
    assert receipt["official_TEST_rows"] == protocol["official_test_rows"] == 0
    assert receipt["development_gradient_rows"] == 0
    assert digest(RUN / "frozen-protocol.json") == receipt["protocol_sha256"]
    dev_path = SPLIT / "pilot_dev.jsonl"
    assert digest(dev_path) == manifest["file_sha256"]["pilot_dev.jsonl"]
    dev = load_jsonl(dev_path)
    assert len(dev) == 128 and all(r["split"] == "dev" and r["source_official_split"] == "train"
                                   and not r["training_eligible"] and not r["official_test"] for r in dev)
    by_id = {r["id"]: r for r in dev}
    phases = {}
    for name in ("baseline", "post_sft"):
        path = RUN / (name + "-predictions-private.json")
        assert digest(path) == receipt[name + "_sha256"]
        predictions = json.loads(path.read_text())
        assert len(predictions) == 128 and {r["id"] for r in predictions} == set(by_id)
        score = score_predictions(dev, predictions, "kali")
        exact = {r["id"]: exact_command(r["response"], by_id[r["id"]]["native_label"]["ground_truth_command"])
                 and not r["truncated"] for r in predictions}
        strict = {d["id"]: bool(d["strict_option_value_correct"]) for d in score["details"]}
        phases[name] = {"predictions": predictions, "native": score,
                        "exact_command": exact, "strict": strict,
                        "summary": {**score["summary"],
                                    "exact_command_match": sum(exact.values()) / 128 * 100,
                                    "complete_output_blocks": sum(bool(re.search(r"<output>.*?</output>", r["response"], re.S))
                                                                  for r in predictions),
                                    "truncated_rows": sum(r["truncated"] for r in predictions)}}
    before = phases["baseline"]
    after = phases["post_sft"]
    paired = {}
    for key in ("strict", "exact_command"):
        paired[key] = {
            "both_correct": sum(before[key][i] and after[key][i] for i in by_id),
            "gained": sum(not before[key][i] and after[key][i] for i in by_id),
            "lost": sum(before[key][i] and not after[key][i] for i in by_id),
            "both_wrong": sum(not before[key][i] and not after[key][i] for i in by_id),
        }
        assert sum(paired[key].values()) == 128
    result = {"status": "PAIRED_INTERNAL_DEV_SCORED", "model_id": protocol["model_id"],
              "model_revision": protocol["model_revision"], "GPU": receipt["GPU"],
              "train_rows": 512, "dev_rows": 128, "optimizer_steps": 512,
              "official_TEST_rows": 0, "source_quality": "publisher-verified silver, not expert gold",
              "scope": "official TRAIN internal holdout only, not official leaderboard score",
              "baseline": before["summary"], "post_sft": after["summary"],
              "paired_transitions": paired, "automatic_model_promotion": False,
              "protocol_sha256": receipt["protocol_sha256"], "receipt_sha256": digest(RUN / "receipt.json")}
    (RUN / "scores-private.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "baseline_strict": before["summary"]["strict_option_value_correct"],
                      "post_strict": after["summary"]["strict_option_value_correct"],
                      "baseline_exact_command": before["summary"]["exact_command_match"],
                      "post_exact_command": after["summary"]["exact_command_match"],
                      "paired": paired}))


if __name__ == "__main__":
    main()
