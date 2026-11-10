#!/usr/bin/env python3
"""Freeze next RedSage SFT arm before publisher holdout model outputs."""

import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-publisher-sft638-2026-11-10"
HOLDOUT = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
OLD = ROOT / "data/benchkit/kali-redsage-c13-external26-2026-11-10"
WORKER = ROOT / "scripts/run-kali-redsage-publisher-sft638-worker-20261110.py"
RECIPE = ROOT / "scripts/kali_publisher_sft_recipe.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    assert not (DATA / "protocol-private.json").exists(), "Never revise frozen protocol"
    frozen = json.loads((DATA / "freeze-manifest-private.json").read_text())
    comparator = json.loads((HOLDOUT / "protocol-private.json").read_text())
    assert frozen["status"] == "ENCODED_PUBLISHER_TRAIN638_FOR_REDSAGE_BEFORE_NEW_SFT"
    assert comparator["status"] == "FROZEN_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64_BEFORE_OUTPUTS"
    assert frozen["encoded_sha256"] == sha(DATA / "train-encoded-private.json")
    assert frozen["holdout_references_sha256"] == comparator["references_sha256"]
    encoded = json.loads((DATA / "train-encoded-private.json").read_text())
    holdout = json.loads(gzip.decompress((HOLDOUT / "inputs-private.json.gz").read_bytes()))["holdout"]
    anchors = json.loads(gzip.decompress((OLD / "inputs-private.json.gz").read_bytes()))["anchors"]
    assert len(encoded) == 638 and len(holdout) == 64 and len(anchors) == 4
    assert not {r["id"] for r in encoded} & {r["id"] for r in holdout + anchors}
    assert all(set(r) == {"id", "native_messages"} for r in holdout)
    raw = json.dumps({"train_rows": encoded, "holdout": holdout, "anchors": anchors},
                     ensure_ascii=False, separators=(",", ":")).encode()
    (DATA / "payload-private.json.gz").write_bytes(gzip.compress(raw))
    optimizer = {"schema": "kali.sft.optimizer.v1", "seed": 42, "epochs": 1,
                 "max_optimizer_steps": 638, "batch_size": 1,
                 "gradient_accumulation_steps": 1, "max_sequence_tokens": 2048,
                 "learning_rate": 1e-5, "weight_decay": 0,
                 "betas": [0.9, 0.999], "eps": 1e-8, "max_grad_norm": None}
    protocol = {k: comparator[k] for k in (
        "LoRA_config", "allowed_GPU_models", "batch_size", "checkpoint_files",
        "expected_packages", "inference_seed", "initialization_seed",
        "max_new_tokens", "resource_request", "runtime_archive_sha256")}
    protocol.update({
        "status": "FROZEN_REDSAGE_PUBLISHER_SFT638_BEFORE_TRAINING",
        "source_official_split": "train", "official_TEST_rows": 0,
        "optimizer": optimizer, "worker_sha256": sha(WORKER),
        "recipe_sha256": sha(RECIPE),
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_gzip_sha256": sha(DATA / "payload-private.json.gz"),
        "encoded_sha256": sha(DATA / "train-encoded-private.json"),
        "holdout_inputs_sha256": sha(HOLDOUT / "inputs-private.json.gz"),
        "holdout_references_sha256": sha(HOLDOUT / "references-private.json"),
        "training_rows": 638, "holdout_rows": 64,
        "pod_runtime_seconds": 4 * 3600,
        "queue_deadline_seconds": 7 * 24 * 3600,
        "result_ttl_seconds": 24 * 3600,
        "model_promotion_allowed": False,
        "human_expert_signoffs": 0,
        "scope": "Publisher-silver KaliBench TRAIN SFT; internal TRAIN holdout; no official TEST",
    })
    write(DATA / "protocol-private.json", protocol)
    print(json.dumps({"status": protocol["status"], "training_rows": 638,
                      "optimizer_steps_planned": 638, "holdout_rows": 64,
                      "official_TEST_rows": 0, "GPU_jobs_submitted": 0}))


if __name__ == "__main__":
    main()
