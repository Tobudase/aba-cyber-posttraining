#!/usr/bin/env python3
"""Freeze RedSage publisher-TRAIN confirmation inputs, model and scorer."""

import datetime
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-publisher-confirm64-2026-11-10"
FIRST = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
TRAIN = ROOT / "data/benchkit/kali-redsage-publisher-sft638-2026-11-10"
WORKER = ROOT / "scripts/run-kali-redsage-publisher-holdout64-worker-v5-20261110.py"
SCORER = ROOT / "scripts/score-kali-redsage-publisher-confirm64-20261110.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    protocol_path = DATA / "protocol-private.json"
    lock_path = DATA / "scorer-lock-private.json"
    assert not protocol_path.exists() and not lock_path.exists()
    freeze = json.loads((DATA / "freeze-manifest-private.json").read_text())
    assert freeze["status"] == "FROZEN_BEFORE_REDSAGE_PUBLISHER_CONFIRM64_OUTPUTS"
    assert freeze["model_outputs"] == freeze["official_TEST_rows"] == 0
    first_input = json.loads(gzip.decompress((FIRST / "worker-input-private.json.gz").read_bytes()))
    new_input = json.loads(gzip.decompress((DATA / "inputs-private.json.gz").read_bytes()))
    assert len(first_input["anchors"]) == 4 and len(new_input["holdout"]) == 64
    assert not {r["id"] for r in first_input["anchors"]} & {r["id"] for r in new_input["holdout"]}
    raw = json.dumps({"anchors": first_input["anchors"], "holdout": new_input["holdout"]},
                     ensure_ascii=False, separators=(",", ":")).encode()
    (DATA / "worker-input-private.json.gz").write_bytes(gzip.compress(raw))
    training_receipt = json.loads((TRAIN / "gpu-attempt-a100-v3/receipt-private.json").read_text())
    assert training_receipt["status"] == "COMPLETE_PUBLISHER_SFT638"
    assert training_receipt["optimizer_steps"] == training_receipt["nonzero_gradient_steps"] == 638
    assert training_receipt["adapter_reload_max_logit_delta"] <= 1e-4
    first_protocol = json.loads((FIRST / "protocol-a100-v5-private.json").read_text())
    protocol = dict(first_protocol)
    protocol.update({
        "adapter_path": "kali-redsage-publisher-sft638-20261110/adapter",
        "adapter_sha256": training_receipt["adapter_sha256"],
        "scope": "Second deterministic unqueried publisher TRAIN internal panel after first result",
        "worker_sha256": sha(WORKER),
        "inputs_sha256": hashlib.sha256(raw).hexdigest(),
        "worker_input_gzip_sha256": sha(DATA / "worker-input-private.json.gz"),
        "freeze_sha256": sha(DATA / "freeze-manifest-private.json"),
        "references_sha256": sha(DATA / "references-private.json"),
        "prior_protocol_sha256": sha(FIRST / "protocol-a100-v5-private.json"),
        "first_sft_receipt_sha256": sha(TRAIN / "gpu-attempt-a100-v3/receipt-private.json"),
        "confirmation_selection_after_first_result": True,
        "prepared_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_promotion_allowed": False,
    })
    assert protocol["status"] == "FROZEN_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64_BEFORE_OUTPUTS"
    assert protocol["rows"] == 64 and protocol["official_TEST_rows"] == protocol["optimizer_steps"] == 0
    write(protocol_path, protocol)
    refs = json.loads((DATA / "references-private.json").read_text())
    train_tools = set(json.loads((FIRST / "scorer-lock-v5-private.json").read_text())["train_tools"])
    seen_ids = sorted(r["custom_id"] for r in refs if r["tool_name"] in train_tools)
    assert len(refs) == 64 and len(seen_ids) == 60
    lock = {
        "status": "CONFIRM64_SCORER_LOCK_BEFORE_OUTPUTS",
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scorer_sha256": sha(SCORER),
        "protocol_sha256": sha(protocol_path),
        "source_sha256": sha(DATA / "references-private.json"),
        "seen_ids": seen_ids,
        "train_tools": sorted(train_tools),
        "official_TEST_rows": 0,
        "commands_executed": False,
        "model_promotion_allowed": False,
    }
    write(lock_path, lock)
    print(json.dumps({"status": "FROZEN_CONFIRM64_BEFORE_OUTPUTS", "rows": 64,
                      "seen": 60, "unseen": 4, "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
