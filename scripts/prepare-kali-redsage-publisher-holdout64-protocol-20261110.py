#!/usr/bin/env python3
"""Lock a target-aligned inference protocol, including historical anchors."""

import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
OLD = ROOT / "data/benchkit/kali-redsage-c13-external26-2026-11-10"
WORKER = ROOT / "scripts/run-kali-redsage-publisher-holdout64-worker-20261110.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main():
    assert not (OUT / "protocol-private.json").exists(), "Do not revise a frozen protocol"
    freeze = json.loads((OUT / "freeze-manifest-private.json").read_text())
    assert freeze["status"] == "FROZEN_BEFORE_REDSAGE_PUBLISHER_HOLDOUT_OUTPUTS"
    assert freeze["model_outputs"] == freeze["official_TEST_rows"] == 0
    prior = json.loads((OLD / "protocol-r3-private.json").read_text())
    assert prior["status"] == "FROZEN_C13_EXTERNAL26_MATCHED_WRAPPER_R3_BEFORE_OUTPUTS"
    previous = json.loads(gzip.decompress((OLD / "inputs-private.json.gz").read_bytes()))
    new = json.loads(gzip.decompress((OUT / "inputs-private.json.gz").read_bytes()))
    assert len(previous["anchors"]) == 4 and len(new["holdout"]) == 64
    assert set(previous["anchors"][0]) == {"id", "native_messages", "expected_sha256"}
    assert not {r["id"] for r in previous["anchors"]} & {r["id"] for r in new["holdout"]}
    raw = json.dumps({"anchors": previous["anchors"], "holdout": new["holdout"]},
                     ensure_ascii=False, separators=(",", ":")).encode()
    (OUT / "worker-input-private.json.gz").write_bytes(gzip.compress(raw))
    protocol = {k: prior[k] for k in (
        "LoRA_config", "adapter_path", "adapter_sha256", "allowed_GPU_models",
        "batch_size", "checkpoint_files", "expected_packages", "inference_seed",
        "initialization_seed", "max_new_tokens", "resource_request", "runtime_archive_sha256")}
    protocol.update({
        "status": "FROZEN_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64_BEFORE_OUTPUTS",
        "scope": "publisher-verified KaliBench TRAIN internal holdout, not official TEST",
        "rows": 64, "anchors": 4, "arms": ["base", "sft"],
        "worker_sha256": sha(WORKER),
        "inputs_sha256": hashlib.sha256(raw).hexdigest(),
        "worker_input_gzip_sha256": sha(OUT / "worker-input-private.json.gz"),
        "freeze_sha256": sha(OUT / "freeze-manifest-private.json"),
        "references_sha256": sha(OUT / "references-private.json"),
        "optimizer_steps": 0, "official_TEST_rows": 0,
        "human_expert_signoffs": 0, "formal_gate_satisfied": False,
        "model_promotion_allowed": False,
        "pod_runtime_seconds": 7200, "queue_deadline_seconds": 7 * 24 * 3600,
        "result_ttl_seconds": 24 * 3600,
        "metrics": ["native_total_score", "native_exact_match",
                    "strict_option_value_correct", "format_error", "truncated"],
    })
    write(OUT / "protocol-private.json", protocol)
    print(json.dumps({"status": protocol["status"], "rows": 64,
                      "arms": 2, "GPU_count": 1,
                      "official_TEST_rows": 0, "model_promotion_allowed": False}))


if __name__ == "__main__":
    main()
