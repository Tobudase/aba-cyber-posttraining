#!/usr/bin/env python3
"""Submit one finite, ordinary-priority KaliBench TRAIN-holdout GPU Job."""

import argparse
import base64
import datetime
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-publisher-holdout-2026-11-10"
WORKER = ROOT / "scripts/run-kali-redsage-publisher-holdout64-worker-v5-20261110.py"
NAME = "miw113-redsage-pub64-v5"
LABELS = {"app.kubernetes.io/managed-by": "miw113",
          "app.kubernetes.io/part-of": "miw113-redsage-publisher-holdout64"}
BASE = ["kubectl", "--context", "nautilus", "-n", "ecepxie"]
LOG = "/cache/kali-redsage-publisher-holdout64-20261110/v5-worker.log"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kube(*args, payload=None, check=True):
    result = subprocess.run(BASE + list(args), input=payload, text=True,
                            capture_output=True, timeout=70)
    if check and result.returncode:
        raise RuntimeError("kubectl " + args[0] + " failed: " + result.stderr[-500:])
    return result


def build():
    protocol = json.loads((DATA / "protocol-a100-v5-private.json").read_text())
    freeze = json.loads((DATA / "freeze-manifest-private.json").read_text())
    assert protocol["status"] == "FROZEN_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64_BEFORE_OUTPUTS"
    assert freeze["status"] == "FROZEN_BEFORE_REDSAGE_PUBLISHER_HOLDOUT_OUTPUTS"
    assert sha(WORKER) == protocol["worker_sha256"]
    assert sha(DATA / "freeze-manifest-private.json") == protocol["freeze_sha256"]
    assert sha(DATA / "references-private.json") == protocol["references_sha256"]
    assert sha(DATA / "worker-input-private.json.gz") == protocol["worker_input_gzip_sha256"]
    assert protocol["rows"] == 64 and protocol["arms"] == ["base", "sft"]
    assert protocol["official_TEST_rows"] == protocol["optimizer_steps"] == 0
    assert protocol["model_promotion_allowed"] is False
    cm = {"apiVersion": "v1", "kind": "ConfigMap",
          "metadata": {"name": NAME, "labels": LABELS},
          "data": {"worker.py": WORKER.read_text(),
                   "protocol.json": (DATA / "protocol-a100-v5-private.json").read_text()}}
    secret = {"apiVersion": "v1", "kind": "Secret",
              "metadata": {"name": NAME + "-input", "labels": LABELS},
              "type": "Opaque", "data": {"inputs.json.gz": base64.b64encode(
                  (DATA / "worker-input-private.json.gz").read_bytes()).decode()}}
    models = {"NVIDIA GeForce RTX 3090": "NVIDIA-GeForce-RTX-3090",
              "NVIDIA GeForce RTX 4090": "NVIDIA-GeForce-RTX-4090",
              "NVIDIA L40": "NVIDIA-L40", "NVIDIA L40S": "NVIDIA-L40S",
              "NVIDIA L4": "NVIDIA-L4", "NVIDIA A10": "NVIDIA-A10",
              "NVIDIA RTX A5000": "NVIDIA-RTX-A5000",
              "NVIDIA RTX 5000 Ada Generation": "NVIDIA-RTX-5000-Ada-Generation",
              "NVIDIA A100-SXM4-80GB": "NVIDIA-A100-SXM4-80GB",
              "NVIDIA A100 80GB PCIe": "NVIDIA-A100-80GB-PCIe",
              "NVIDIA A100-PCIE-40GB": "NVIDIA-A100-PCIE-40GB"}
    assert set(protocol["allowed_GPU_models"]) <= set(models)
    resources = protocol["resource_request"]
    assert resources == {"cpu": "2", "memory": "12Gi",
                         "ephemeral-storage": "24Gi", "nvidia.com/a100": "1"}
    pod = {"restartPolicy": "Never",
           "activeDeadlineSeconds": protocol["pod_runtime_seconds"],
           "automountServiceAccountToken": False,
           "nodeSelector": {"kubernetes.io/arch": "amd64"},
           "affinity": {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {
               "nodeSelectorTerms": [{"matchExpressions": [{"key": "nvidia.com/gpu.product",
                   "operator": "In", "values": [models[m] for m in protocol["allowed_GPU_models"]]},
                    {"key": "topology.kubernetes.io/region", "operator": "In",
                     "values": ["us-west", "us-central"]}]}]}}},
           "containers": [{"name": "infer", "image": json.loads(
               (ROOT / "configs/gpu-runtime-image.lock.json").read_text())["image"],
               "command": ["/bin/bash", "-lc", "set -euo pipefail; mkdir -p "
                   "/cache/kali-redsage-publisher-holdout64-20261110; "
                   "python -u /input/worker.py 2>&1 | tee " + LOG],
               "env": [{"name": "HF_HUB_OFFLINE", "value": "1"},
                       {"name": "OMP_NUM_THREADS", "value": "2"},
                       {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"}],
               "resources": {"requests": resources, "limits": resources},
               "volumeMounts": [{"name": "input", "mountPath": "/input", "readOnly": True},
                                {"name": "cache", "mountPath": "/cache"},
                                {"name": "scratch", "mountPath": "/scratch"}]}],
           "volumes": [{"name": "input", "projected": {"defaultMode": 256,
               "sources": [{"configMap": {"name": NAME}},
                           {"secret": {"name": NAME + "-input"}}]}},
               {"name": "cache", "persistentVolumeClaim": {"claimName": "miw113-kali-cuda-cache"}},
               {"name": "scratch", "emptyDir": {"sizeLimit": "24Gi"}}]}
    assert "priorityClassName" not in pod and "tolerations" not in pod
    job = {"apiVersion": "batch/v1", "kind": "Job",
           "metadata": {"name": NAME, "labels": LABELS,
                        "annotations": {"research.ucsd.edu/queue-mode": "one-gpu-bounded"}},
           "spec": {"activeDeadlineSeconds": protocol["queue_deadline_seconds"],
                    "backoffLimit": 0,
                    "ttlSecondsAfterFinished": protocol["result_ttl_seconds"],
                    "template": {"metadata": {"labels": LABELS}, "spec": pod}}}
    return protocol, cm, secret, job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    protocol, cm, secret, job = build()
    for obj in (secret, cm, job):
        kube("create", "--dry-run=server", "-f", "-", payload=json.dumps(obj))
    if args.dry_run:
        print(json.dumps({"status": "SERVER_DRY_RUN_PASS", "GPU_count": 1,
                          "rows": 64, "official_TEST_rows": 0}))
        return
    assert not kube("get", "jobs,pods,configmaps,secrets", "-l",
                    "app.kubernetes.io/managed-by=miw113", "-o", "name").stdout.strip()
    out = DATA / "gpu-attempt5"
    assert not out.exists(), "Do not overwrite a previous attempt"
    out.mkdir()
    (out / "protocol-a100-v5-private.json").write_bytes((DATA / "protocol-a100-v5-private.json").read_bytes())
    record = {"status": "SUBMITTING", "job_name": NAME,
              "submitted_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "queue_deadline_seconds": protocol["queue_deadline_seconds"],
              "pod_runtime_seconds": protocol["pod_runtime_seconds"],
              "result_ttl_seconds": protocol["result_ttl_seconds"],
              "private_log_on_pvc": LOG, "GPU_count": 1,
              "priority": "ordinary", "official_TEST_rows": 0,
              "protocol_sha256": sha(DATA / "protocol-a100-v5-private.json"),
              "cleanup_errors": []}
    receipt = out / "host-run-private.json"
    receipt.write_text(json.dumps(record, indent=2) + "\n")
    created = []
    try:
        for obj in (secret, cm, job):
            kube("create", "-f", "-", payload=json.dumps(obj))
            created.append((obj["kind"].lower(), obj["metadata"]["name"]))
        actual = json.loads(kube("get", "job", NAME, "-o", "json").stdout)
        uid = actual["metadata"]["uid"]
        assert uid
        owner = {"apiVersion": "batch/v1", "kind": "Job", "name": NAME,
                 "uid": uid, "controller": False, "blockOwnerDeletion": False}
        for kind, name in (("secret", NAME + "-input"), ("configmap", NAME)):
            kube("patch", kind, name, "--type=merge", "-p",
                 json.dumps({"metadata": {"ownerReferences": [owner]}}))
        record.update(status="QUEUED_OR_STARTING", job_uid=uid,
                      owned_inputs_garbage_collected_with_job=True)
    except BaseException as exc:
        record.update(status="SUBMISSION_FAILED", error_type=type(exc).__name__,
                      error=str(exc)[:300])
        for kind, name in reversed(created):
            result = kube("delete", kind, name, "--ignore-not-found=true", "--wait=true",
                          "--timeout=45s", check=False)
            if result.returncode:
                record["cleanup_errors"].append(kind + "_delete_failed")
        raise
    finally:
        receipt.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": record["status"], "job_name": NAME,
                      "GPU_count": 1, "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
