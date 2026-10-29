#!/usr/bin/env python3
"""Make a conservative, TRAIN-only exploratory SFT subset from publisher receipts.

This is a lexical environment-failure screen, not semantic label adjudication.
It never executes commands or opens official TEST. Raw outputs remain private.
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path


PATTERNS = {
    "missing_file_or_directory": r"(?i)(no such file or directory|could not find file|file .*not found|failed to open|couldn.t open)",
    "permission_or_capability": r"(?i)(permission denied|operation not permitted|access denied)",
    "network_or_dns_unavailable": r"(?i)(temporary failure in name resolution|could not resolve|connection refused|error while dialing|not a valid domain name|unable to get server.s address)",
    "display_unavailable": r"(?i)(could not connect to display|could not load the .*platform plugin)",
    "dependency_missing": r"(?i)(executable file not found in \$PATH|command not found|not installed)",
    "explicit_error_line": r"(?im)^\s*(?:\x1b\[[0-9;]*m)?(?:ERROR|FATAL|FAILED|Error:|Failed to)\b",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-summary", type=Path, required=True)
    parser.add_argument("--encoded-source", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    train_path = root / "data/benchkit/kali-qwen-official-executed-pilot-2026-10-28/pilot_train.jsonl"
    frozen = json.loads((train_path.parent / "manifest.json").read_text())
    raw_path = root / ".tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl"
    assert sha(train_path) == frozen["file_sha256"]["pilot_train.jsonl"]
    assert sha(raw_path) == frozen["raw_publisher_train_sha256"]
    train = load_jsonl(train_path)
    publisher = {r["custom_id"]: r for r in load_jsonl(raw_path)}
    assert len(train) == 512 and len(publisher) == 3504
    encoding_summary = json.loads((args.encoded_source.parent / "cpu-encoding-summary.json").read_text())
    assert sha(args.encoded_source) == encoding_summary["private_file_sha256"][args.encoded_source.name]
    assert encoding_summary["train_rows"] == 512 and encoding_summary["official_TEST_rows_opened"] == 0
    encoded = json.loads(args.encoded_source.read_text())
    assert len(encoded) == 512 and len({r["id"] for r in encoded}) == 512
    encoded_by_id = {r["id"]: r for r in encoded}
    assert set(encoded_by_id) == {r["id"] for r in train}
    compiled = {key: re.compile(pattern) for key, pattern in PATTERNS.items()}
    kept, held, queue = [], [], []
    cue_counts = collections.Counter()
    for row in train:
        original = publisher[row["id"]]
        receipt = original["terminal_verification"]
        assert receipt["label"] == "PASS_EXECUTED"
        assert receipt["exit_code"] == 0 and receipt["timed_out"] is False
        assert row["source_official_split"] == "train" and not row["official_test"]
        assert row["native_label"]["query"] == original["query"]
        assert row["native_label"]["ground_truth_command"] == original["ground_truth_command"]
        combined = receipt["stdout"] + "\n" + receipt["stderr"]
        cues = [key for key, pattern in compiled.items() if pattern.search(combined)]
        if receipt["stdout_truncated"] or receipt["stderr_truncated"]:
            cues.append("publisher_terminal_output_truncated")
        cue_counts.update(cues)
        copied = dict(row)
        copied["receipt_screen_status"] = "REQUIRES_EFFECT_REVIEW" if cues else "NO_LEXICAL_ENVIRONMENT_FAILURE_CUE"
        copied["receipt_screen_is_semantic_verdict"] = False
        copied["training_eligible"] = not bool(cues)
        (held if cues else kept).append(copied)
        queue.append({"id": row["id"], "tool": row["native_label"]["tool_name"],
                      "question": row["native_label"]["query"],
                      "gold_command": row["native_label"]["ground_truth_command"],
                      "receipt_cues": cues,
                      "publisher_exit_code": receipt["exit_code"],
                      "publisher_stdout_truncated": receipt["stdout_truncated"],
                      "publisher_stderr_truncated": receipt["stderr_truncated"],
                      "human_effect_verdict": "PENDING",
                      "tool_version_checked": None,
                      "evidence_and_rationale": None})
    assert len(kept) + len(held) == 512
    assert not {r["id"] for r in kept} & {r["id"] for r in held}
    args.private_out.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.private_out / "receipt_clear_train_private.jsonl", kept)
    write_jsonl(args.private_out / "effect_review_hold_private.jsonl", held)
    keep_ids = {r["id"] for r in kept}
    encoded_subset = [r for r in encoded if r["id"] in keep_ids]
    assert len(encoded_subset) == len(kept)
    assert all(r["labels"][:r["prompt_tokens"]] == [-100] * r["prompt_tokens"] and
               r["labels"][r["prompt_tokens"]:] == r["input_ids"][r["prompt_tokens"]:] and
               not r["official_test"] for r in encoded_subset)
    encoded_path = args.private_out / "receipt_clear_encoded_train_private.json"
    encoded_path.write_text(json.dumps(encoded_subset, ensure_ascii=False, separators=(",", ":")) + "\n")
    # Preserve the original 512 optimizer-step budget while disclosing that
    # 111 of the 401 unique examples receive one additional exposure.
    repeat_count = 512 - len(encoded_subset)
    assert repeat_count >= 0
    repeat_rank = lambda r: hashlib.sha256(("receipt-screen-512-step-v1\0" + r["id"]).encode()).hexdigest()
    repeats = sorted(encoded_subset, key=repeat_rank)[:repeat_count]
    scheduled = encoded_subset + repeats
    assert len(scheduled) == 512 and len({r["id"] for r in scheduled}) == len(encoded_subset)
    assert max(collections.Counter(r["id"] for r in scheduled).values()) <= 2
    schedule_path = args.private_out / "receipt_clear_512step_schedule_encoded_private.json"
    schedule_path.write_text(json.dumps(scheduled, ensure_ascii=False, separators=(",", ":")) + "\n")
    (args.private_out / "receipt-review-queue-private.json").write_text(json.dumps(
        {"status": "REVIEW_PENDING_NOT_EXPERT_ADJUDICATED", "rows": queue}, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "status": "EXPLORATORY_TRAIN_ONLY_RECEIPT_SCREEN_NOT_SEMANTICALLY_APPROVED",
        "source_sha256": {"frozen_train512": sha(train_path), "publisher_train3504": sha(raw_path)},
        "original_encoded_train_sha256": sha(args.encoded_source),
        "counts": {"source_train_rows": 512, "no_lexical_failure_cue": len(kept),
                   "held_for_effect_review": len(held), "independent_human_effect_verdicts": 0,
                   "publisher_exit_code_zero": 512, "publisher_timed_out": 0},
        "cue_counts_nonexclusive": dict(sorted(cue_counts.items())),
        "private_derived_sha256": {
            "receipt_clear_train": sha(args.private_out / "receipt_clear_train_private.jsonl"),
            "effect_review_hold": sha(args.private_out / "effect_review_hold_private.jsonl"),
            "review_queue": sha(args.private_out / "receipt-review-queue-private.json"),
            "receipt_clear_encoded_train": sha(encoded_path),
            "receipt_clear_512step_schedule_encoded": sha(schedule_path),
        },
        "candidate_encoded_checks": {"rows": len(encoded_subset),
                                     "scheduled_optimizer_exposures": len(scheduled),
                                     "twice_exposed_rows": repeat_count,
                                     "all_prompt_tokens_masked": True,
                                     "all_target_and_EOS_tokens_supervised": True,
                                     "official_TEST_rows": 0},
        "selection_rule": "Keep only original publisher-PASS_EXECUTED TRAIN rows with exit code 0, no timeout, no truncated output and no listed lexical environment-failure cue in stdout/stderr.",
        "limitations": [
            "A flagged terminal receipt does not prove the reference command is wrong; missing external resources can cause valid syntax to fail.",
            "An unflagged terminal receipt does not prove the task was semantically achieved.",
            "This screen is a TRAIN-only exploratory data ablation; do not interpret it as expert-approved data or a final deployment gate.",
            "The 512-step schedule repeats 111 selected records once; a future comparison must disclose changed unique-row and token exposure.",
            "No evaluation outputs or official TEST records informed this selection.",
        ],
        "commands_executed": 0, "model_calls": 0, "optimizer_steps": 0, "official_TEST_rows": 0,
    }
    args.public_summary.parent.mkdir(parents=True, exist_ok=True)
    args.public_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": summary["status"], "counts": summary["counts"],
                      "cue_counts_nonexclusive": summary["cue_counts_nonexclusive"]}, indent=2))


if __name__ == "__main__":
    main()
