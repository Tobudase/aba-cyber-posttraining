#!/usr/bin/env python3
"""Freeze P08 as an exact data/seed repeat of P07 before GPU output."""

import datetime
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "data/benchkit"
STUDY = B / "kali-redsage-aba-publisher-v2-2026-11-10"
P07 = STUDY / "P07"
P08 = STUDY / "P08"
SCORER = ROOT / "scripts/score-kali-redsage-coverage733-replica-20261111.py"
REF1 = B / "kali-redsage-publisher-holdout-2026-11-10/references-private.json"
REF2 = B / "kali-redsage-publisher-confirm64-2026-11-10/references-private.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    assert not P08.exists(), "never overwrite a frozen replicate"
    p07_freeze = read(P07 / "freeze-manifest-private.json")
    p07_protocol = read(P07 / "protocol-private.json")
    assert p07_freeze["status"] == "BROAD_COVERAGE_CONTROL_FROZEN_BEFORE_OUTPUTS"
    assert sha(P07 / "protocol-private.json") == p07_freeze["protocol_sha256"]
    assert p07_protocol["candidate_id"] == "P07" and p07_protocol["training_rows"] == 733
    assert p07_protocol["official_TEST_rows"] == 0
    assert sha(P07 / "payload-private.json.gz") == p07_freeze["payload_gzip_sha256"]
    assert sha(REF1) == p07_freeze["dev1_references_sha256"]
    assert sha(REF2) == p07_freeze["dev2_references_sha256"]
    p07_score = read(P07 / "gpu-attempt-a100/scores-private.json")
    assert p07_score["candidate_id"] == "P07" and p07_score["official_TEST_rows"] == 0
    assert not p07_score["model_promotion_allowed"]
    assert SCORER.exists() and b'choices=["P08"]' in SCORER.read_bytes()

    protocol = dict(p07_protocol)
    protocol["candidate_id"] = "P08"
    protocol["prepared_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    protocol["scope"] = ("Operator exact-repeat diagnostic of P07 with identical payload, "
                         "optimizer, seeds, checkpoint and inference; exposed TRAIN DEV; "
                         "no official TEST/final64 outputs; no model promotion")
    assert protocol["optimizer"] == p07_protocol["optimizer"]
    for key in ("payload_sha256", "payload_gzip_sha256", "encoded_sha256",
                "checkpoint_files", "runtime_archive_sha256", "worker_sha256",
                "recipe_sha256", "LoRA_config", "initialization_seed", "inference_seed",
                "batch_size", "max_new_tokens", "resource_request", "allowed_GPU_models"):
        assert protocol[key] == p07_protocol[key], key
    assert protocol["model_promotion_allowed"] is False

    P08.mkdir(parents=True)
    for name in ("payload-private.json.gz", "train-encoded-private.json"):
        (P08 / name).write_bytes((P07 / name).read_bytes())
        assert sha(P08 / name) == sha(P07 / name)
    protocol_path = P08 / "protocol-private.json"
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    freeze = dict(p07_freeze)
    freeze.update({
        "candidate_id": "P08",
        "replication_of": "P07",
        "replication_type": "exact_payload_optimizer_seed_checkpoint_inference; numerical run variation still possible",
        "operator_control_not_ABA_selected": True,
        "model_promotion_allowed": False,
        "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path),
        "p07_protocol_sha256": sha(P07 / "protocol-private.json"),
    })
    (P08 / "freeze-manifest-private.json").write_text(json.dumps(freeze, indent=2) + "\n")
    lock = {
        "status": "COVERAGE733_SCORER_LOCK_BEFORE_P08_OUTPUTS",
        "candidate_id": "P08",
        "replication_of": "P07",
        "scorer_sha256": sha(SCORER),
        "protocol_sha256": sha(protocol_path),
        "dev1_references_sha256": sha(REF1),
        "dev2_references_sha256": sha(REF2),
        "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (P08 / "scorer-lock-private.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(json.dumps({"status": "P08_EXACT_REPLICA_FROZEN_BEFORE_OUTPUTS",
                      "same_payload_sha256": sha(P08 / "payload-private.json.gz") == sha(P07 / "payload-private.json.gz"),
                      "same_optimizer": protocol["optimizer"] == p07_protocol["optimizer"],
                      "same_seeds": all(protocol[k] == p07_protocol[k]
                                        for k in ("initialization_seed", "inference_seed")),
                      "training_rows": 733, "gpu_count": 1,
                      "official_TEST_rows": 0, "model_promotion_allowed": False}))


if __name__ == "__main__":
    main()
