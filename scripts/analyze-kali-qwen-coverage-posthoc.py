#!/usr/bin/env python3
"""Read-only post hoc coverage breakdown of already frozen private outputs."""

import argparse
import collections
import hashlib
import json
from pathlib import Path

from benchkit import load_jsonl, score_predictions


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-summary", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    train_path = root / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_train.jsonl"
    manifest = json.loads((train_path.parent / "manifest.json").read_text())
    assert sha(train_path) == manifest["file_sha256"]["pilot_train.jsonl"]
    train = load_jsonl(train_path)
    assert len(train) == 512
    train_frequency = collections.Counter(r["native_label"]["tool_name"] for r in train)
    data = root / "data/benchkit/kali-qwen-confirmation-2026-10-28"
    selection_path = data / "selection-ids-private.json"
    primary_ids = set(json.loads(selection_path.read_text())["primary87"])
    rows = [r for r in load_jsonl(data / "dev93-private.jsonl") if r["id"] in primary_ids]
    assert len(rows) == len(primary_ids) == 87
    run = root / "docs/verification/kali-qwen-confirmation-2026-10-28/gpu-cycle"
    strict = {}
    hashes = {"train512": sha(train_path), "selection": sha(selection_path)}
    for phase in ("baseline", "post_sft"):
        path = run / f"{phase}-predictions-private.json"
        predictions = [p for p in json.loads(path.read_text()) if p["id"] in primary_ids]
        assert len(predictions) == 87
        result = score_predictions(rows, predictions, "kali")
        strict[phase] = {d["id"]: bool(d["strict_option_value_correct"]) for d in result["details"]}
        hashes[phase] = sha(path)
    buckets = collections.defaultdict(list)
    private_cases = []
    for row in rows:
        identifier = row["id"]
        tool = row["native_label"]["tool_name"]
        freq = train_frequency[tool]
        bucket = "0" if freq == 0 else "1" if freq == 1 else "2plus"
        before, after = strict["baseline"][identifier], strict["post_sft"][identifier]
        buckets[bucket].append((before, after))
        private_cases.append({"id": identifier, "tool": tool, "train_tool_frequency": freq,
                              "baseline_strict": before, "post_sft_strict": after})
    summary = {}
    for key in ("0", "1", "2plus"):
        pairs = buckets[key]
        summary[key] = {"rows": len(pairs), "baseline_correct": sum(a for a, b in pairs),
                        "post_sft_correct": sum(b for a, b in pairs),
                        "gained": sum(not a and b for a, b in pairs),
                        "lost": sum(a and not b for a, b in pairs)}
    assert sum(x["rows"] for x in summary.values()) == 87
    assert sum(x["baseline_correct"] for x in summary.values()) == 18
    assert sum(x["post_sft_correct"] for x in summary.values()) == 26
    assert sum(x["gained"] for x in summary.values()) == 9
    assert sum(x["lost"] for x in summary.values()) == 1
    public = {"status": "POSTHOC_DESCRIPTIVE_COVERAGE_BREAKDOWN_ONLY",
              "scope": "Already queried publisher-TRAIN internal primary87; no new model call, training or official TEST",
              "source_sha256": hashes, "train_tool_frequency_buckets": summary,
              "interpretation_limit": "Bucket selection is post hoc; small correlated samples and silver labels do not establish a causal training-frequency effect or independent-source generalization."}
    private = {"public_summary": public, "cases": sorted(private_cases, key=lambda x: x["id"])}
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_summary.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2) + "\n")
    args.public_summary.write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps(public, indent=2))


if __name__ == "__main__":
    main()
