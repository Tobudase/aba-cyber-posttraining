#!/usr/bin/env python3
"""Mechanical audit of frozen Qwen confirmation outputs; never execute commands."""

import collections
import difflib
import hashlib
import json
import re
import statistics
from pathlib import Path

from benchkit import load_jsonl, score_predictions


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-qwen-confirmation-2026-10-28"
RUN = ROOT / "docs/verification/kali-qwen-confirmation-2026-10-28/gpu-cycle"
TRAIN = ROOT / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_train.jsonl"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(response, gold, truncated):
    blocks = re.findall(r"<output>\s*(.*?)\s*</output>", response, re.S)
    return len(blocks) == 1 and blocks[0].strip() == gold.strip() and not truncated


def repeated_fivegram_max(response):
    tokens = re.findall(r"\S+", response)
    grams = collections.Counter(tuple(tokens[i:i + 5]) for i in range(max(0, len(tokens) - 4)))
    return max(grams.values(), default=0)


def main():
    selection = json.loads((DATA / "selection-ids-private.json").read_text())
    primary = set(selection["primary87"])
    all_rows = load_jsonl(DATA / "dev93-private.jsonl")
    rows = [r for r in all_rows if r["id"] in primary]
    assert len(rows) == 87
    by_id = {r["id"]: r for r in rows}
    train = load_jsonl(TRAIN)
    by_train_tool = collections.defaultdict(list)
    for row in train:
        by_train_tool[row["native_label"]["tool_name"]].append(row)
    phase = {}
    for name in ("baseline", "post_sft"):
        p = json.loads((RUN / f"{name}-predictions-private.json").read_text())
        assert len(p) == 93 and len({x["id"] for x in p}) == 93
        phase[name] = {"pred": {x["id"]: x for x in p}}
        scored = score_predictions(rows, [phase[name]["pred"][r["id"]] for r in rows], "kali")
        phase[name]["strict"] = {d["id"]: bool(d["strict_option_value_correct"])
                                 for d in scored["details"]}
    cases = []
    counts = collections.Counter()
    for identifier in sorted(primary):
        row = by_id[identifier]
        before = phase["baseline"]["pred"][identifier]
        after = phase["post_sft"]["pred"][identifier]
        a = phase["baseline"]["strict"][identifier]
        b = phase["post_sft"]["strict"][identifier]
        if a == b and not after["truncated"]:
            continue
        transition = "gained" if not a and b else "lost" if a and not b else "both_wrong_truncated"
        tool = row["native_label"]["tool_name"]
        peers = by_train_tool[tool]
        ratio = max((difflib.SequenceMatcher(None, row["native_label"]["query"].lower(),
                                                    t["native_label"]["query"].lower()).ratio()
                     for t in peers), default=None)
        item = {
            "id": identifier,
            "transition": transition,
            "tool": tool,
            "tool_present_in_train512": bool(peers),
            "same_tool_train_rows": len(peers),
            "max_same_tool_train_query_sequence_ratio": ratio,
            "baseline_exact_gold_command": exact(before["response"], row["native_label"]["ground_truth_command"],
                                                 before["truncated"]),
            "post_exact_gold_command": exact(after["response"], row["native_label"]["ground_truth_command"],
                                             after["truncated"]),
            "baseline_tokens": before["output_tokens"],
            "post_tokens": after["output_tokens"],
            "baseline_has_closed_output": bool(re.search(r"<output>.*?</output>", before["response"], re.S)),
            "post_has_closed_output": bool(re.search(r"<output>.*?</output>", after["response"], re.S)),
            "post_truncated": bool(after["truncated"]),
            "post_repeated_fivegram_max": repeated_fivegram_max(after["response"]),
            "human_semantic_review": "PENDING_INDEPENDENT_REVIEW",
        }
        cases.append(item)
        counts[transition] += 1
    assert counts == {"gained": 9, "lost": 1, "both_wrong_truncated": 3}
    assert sum(x["tool_present_in_train512"] for x in cases if x["transition"] == "gained") == 8
    assert sum(x["post_exact_gold_command"] for x in cases if x["transition"] == "gained") == 7
    trunc = [x for x in cases if x["post_truncated"]]
    assert len(trunc) == 3 and all(x["post_tokens"] == 512 and
                                   not x["post_has_closed_output"] and
                                   x["post_repeated_fivegram_max"] >= 10 for x in trunc)
    def lengths(name):
        arr = sorted(p["output_tokens"] for p in phase[name]["pred"].values())
        return {"min": arr[0], "median": statistics.median(arr), "p95_nearest_rank": arr[88],
                "max": arr[-1], "at_least_256_tokens": sum(n >= 256 for n in arr),
                "at_512_token_cap": sum(n >= 512 for n in arr)}
    result = {
        "status": "MECHANICAL_TRIAGE_ONLY_HUMAN_REVIEW_PENDING",
        "scope": "primary87 strict transitions and post-SFT truncations",
        "source_prediction_sha256": {n: sha(RUN / f"{n}-predictions-private.json")
                                     for n in ("baseline", "post_sft")},
        "case_counts": dict(counts),
        "gains_with_tool_present_in_train512": 8,
        "gains_with_tool_absent_from_train512": 1,
        "gains_exact_gold_command": 7,
        "gains_strict_correct_but_not_exact_gold_string": 2,
        "losses_with_tool_absent_from_train512": 1,
        "truncated_at_cap_without_closed_output_and_with_repeated_fivegram": 3,
        "token_lengths_all93": {n: lengths(n) for n in ("baseline", "post_sft")},
        "cases": cases,
        "interpretation_limit": "String/format checks and lexical ratios do not establish semantic correctness or data independence."
    }
    (RUN / "mechanical-triage-private.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "case_counts", "gains_exact_gold_command",
                                                    "truncated_at_cap_without_closed_output_and_with_repeated_fivegram",
                                                    "token_lengths_all93")}))


if __name__ == "__main__":
    main()
