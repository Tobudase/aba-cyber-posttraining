#!/usr/bin/env python3
"""Check the released aggregate Qwen development result without private records."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/kali-qwen-official-executed-pilot-2026-10-28/cycle-summary.json"
WORKER = ROOT / "scripts/run-kali-qwen-official-gpu-worker-qlora.py"


def main():
    result = json.loads(RESULT.read_text())
    assert result["status"] == "COMPLETED_MATCHED_INTERNAL_DEV_QWEN_QLORA_PILOT"
    assert result["model_id"] == "Qwen/Qwen3-8B"
    assert result["GPU_count"] == 1 and result["precision"] == "NF4 QLoRA with BF16 compute"
    assert (result["train_rows"], result["dev_rows"], result["optimizer_steps"]) == (512, 128, 512)
    assert result["official_TEST_rows_opened"] == result["development_gradient_rows"] == 0
    assert result["ABA_search_executed"] is False
    assert result["independent_external_validation"] is False
    assert result["automatic_model_promotion"] is False
    assert result["saved_adapter_hash_reverified_on_PVC"] is True
    assert result["owned_GPU_job_pod_configmap_remaining"] == 0
    assert hashlib.sha256(WORKER.read_bytes()).hexdigest() == result["worker_sha256"]
    n = result["dev_rows"]
    for name, metric, count in (("strict", "strict_option_value_correct", "strict_correct_counts"),
                                ("exact_command", "exact_command_match", "exact_command_correct_counts")):
        paired = result["paired_transitions"][name]
        assert sum(paired.values()) == n
        before = paired["both_correct"] + paired["lost"]
        after = paired["both_correct"] + paired["gained"]
        assert result[count] == {"baseline": before, "post_sft": after}
        assert abs(result["baseline"][metric] - before / n * 100) < 1e-9
        assert abs(result["post_sft"][metric] - after / n * 100) < 1e-9
    assert result["baseline"]["complete_output_blocks"] + result["baseline"]["truncated_rows"] == n
    assert result["post_sft"]["complete_output_blocks"] == n
    assert result["post_sft"]["truncated_rows"] == 0
    prompt_gold = result["prompt_embeds_exact_gold_command"]
    assert (prompt_gold["train_rows"], prompt_gold["dev_rows"]) == (4, 1)
    assert prompt_gold["dev_row_correct_in_baseline_and_post_sft"] is True
    sensitivity = result["sensitivity_excluding_prompt_embedded_gold_dev_row"]
    assert sensitivity["rows"] == n - 1
    assert (sensitivity["strict_correct_baseline"], sensitivity["strict_correct_post_sft"]) == (28, 42)
    assert (sensitivity["exact_command_baseline"], sensitivity["exact_command_post_sft"]) == (24, 35)
    for metric, key in (("strict", "strict_correct"), ("exact_command", "exact_command")):
        assert result[metric + "_correct_counts"]["baseline"] - sensitivity[key + "_baseline"] == 1
        assert result[metric + "_correct_counts"]["post_sft"] - sensitivity[key + "_post_sft"] == 1
    print(json.dumps({"status": "PUBLIC_AGGREGATE_ARITHMETIC_PASS", "train_rows": 512,
                      "dev_rows": 128, "optimizer_steps": 512, "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
