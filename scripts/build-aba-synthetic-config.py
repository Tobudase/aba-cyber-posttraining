#!/usr/bin/env python3
"""Write a credential-free ABA configuration for the synthetic CPU fixture."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--remote-root", default="/home/minhao/aba-synthetic-20261016")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
roles = "aggregator coder coder_review committee designer designer_review finalizer judge meta meta_review planner reviewer reviser reviser_review router selector setup setup_review submitter worker worker_review writer writer_review".split()
config = {
    "run": {
        "task_name": "synthetic-bigram-cpu",
        "data_root": args.remote_root + "/task",
        "playground_root": args.remote_root + "/playground",
        "budget": {"wall_clock_minutes": 20, "cost_usd": 5, "per_agent_cost_cap_usd": 2,
                   "reminder_interval_divisor": 1},
    },
    "llm": {
        "default": {"model": "qwen3-small", "max_thinking_tokens": 0},
        "retry_ceiling_s": 60,
        "system_instructions": {
            "setup": "Read the complete supplied synthetic task. Standard library only; no package installs, external data or KB required. Keep dev.jsonl and evaluate.py private. Wrap the existing evaluator without modifying it. Pass the real baseline scoring gate. Be direct and finish promptly.",
            "designer": "Produce exactly one concise SGD adaptation plan. The README and base model already specify the complete fixture; no need to read all individual training rows or search references. Python standard library only, eight-token bigram model, no downloads. Choose 32 epochs and learning rate 0.1. No revisions; references=[].",
            "worker": "Implement and EXECUTE actual SGD starting from base_model.json on train.jsonl only. Use Python standard library. Save model.json, train_metrics.json, README.md and source run.py. CRITICAL: copy the exact executed source run.py into attempt_dir (OUTPUT_DIR) too: the Finalizer can read selected output only, not your source_dir/scratch. Verify attempt_dir/run.py exists before submitting. Use 32 epochs, learning rate 0.1, seed 42; no revisions. Do not access dev or grading files. Finish with real files and genuine steps.",
            "finalizer": "Selected output_dir contains final_model/model.json, train_metrics.json, README.md and run.py. Copy these four existing files, preserving bytes, into deliverable with matching relative paths, then immediately submit StructuredOutput with all four paths. Do not reconstruct code, retrain, score again, search other directories, fetch data or write a paper. If any requested file is missing, report the missing file rather than inventing it.",
        },
    },
    "work_units": [
        {"kind": "llm_agent", "name": name, "budget": {"kind": "fixed", "minutes": 6 if name in ("setup", "worker") else 4}, "retry": 0}
        for name in roles
    ] + [
        {"kind": "llm_agent", "name": "manager", "budget": {"kind": "pipeline"}, "retry": 0},
        {"kind": "program", "name": "score_program", "budget": {"kind": "fixed", "minutes": 1}, "retry": 0},
        {"kind": "program", "name": "training", "budget": {"kind": "fixed", "minutes": 1}, "retry": 0},
    ],
    # This source requires a positive revision ceiling; max_evaluations=1
    # prevents a second candidate and the Worker is instructed to emit none.
    "search": {"kind": "nb_tree", "input": {"parallel": 1, "num_designs": 1, "num_revisions": 1, "max_evaluations": 1, "early_stopping": 1}},
    "resources": {
        "run": {"cpu_max_cores": 2, "memory_max_gb": 6, "disk_free_floor_gb": 4},
        "work_unit": {"cpu_max_cores": 2, "memory_max_gb": 4},
        "sandbox": {"enable": True},
        "cuda_visible_devices": [],
    },
    "disallowed_tools": ["WebSearch", "WebFetch"],
    "scheduler": {"recheck_seconds": 10},
    "writer": {"enable": False},
    "mcps": {},
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(config, indent=2) + "\n")
print(json.dumps({"status": "CONFIG_WRITTEN", "model": "qwen3-small", "gpu_count": 0, "candidates": 1, "exploration_minutes": 20}))
