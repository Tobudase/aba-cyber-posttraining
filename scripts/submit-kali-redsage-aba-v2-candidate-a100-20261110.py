#!/usr/bin/env python3
"""Submit one finite, ordinary-priority repaired ABA candidate GPU Job."""

import argparse
import base64
import datetime
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-aba-publisher-v2-2026-11-10"
WORKER = ROOT / "scripts/run-kali-redsage-aba-candidate-worker-v2-20261110.py"
RECIPE = ROOT / "scripts/kali_publisher_sft_recipe.py"
LABELS = {"app.kubernetes.io/managed-by": "miw113",
          "app.kubernetes.io/part-of": "miw113-redsage-aba-publisher-v2"}
BASE = ["kubectl", "--context", "nautilus", "-n", "ecepxie"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kube(*args, payload=None, check=True):
    result = subprocess.run(BASE + list(args), input=payload, text=True,
                            capture_output=True, timeout=70)
    if check and result.returncode:
        raise RuntimeError("kubectl " + args[0] + " failed: " + result.stderr[-500:])
    return result


def build(candidate_id):
    assert candidate_id in {"P05", "P06", "P07", "P08"}
    data = DATA / candidate_id
    name = "miw113-redsage-aba-" + candidate_id.lower()
    log = "/cache/kali-redsage-aba-logs/" + candidate_id.lower() + "-worker.log"
    protocol = json.loads((data / "protocol-private.json").read_text())
    freeze = json.loads((data / "freeze-manifest-private.json").read_text())
    assert protocol["status"] == "FROZEN_REDSAGE_ABA_CANDIDATE_BEFORE_TRAINING"
    assert freeze["status"] in {"ABA_CANDIDATE_FROZEN_BEFORE_OUTPUTS",
                                "BROAD_COVERAGE_CONTROL_FROZEN_BEFORE_OUTPUTS"}
    assert protocol["candidate_id"] == freeze["candidate_id"] == candidate_id
    assert sha(data / "protocol-private.json") == freeze["protocol_sha256"]
    assert sha(WORKER) == protocol["worker_sha256"]
    assert sha(RECIPE) == protocol["recipe_sha256"]
    assert sha(data / "payload-private.json.gz") == protocol["payload_gzip_sha256"] == freeze["payload_gzip_sha256"]
    assert protocol["training_rows"] in {505, 638, 733}
    assert protocol["optimizer"]["max_optimizer_steps"] == protocol["training_rows"]
    assert protocol["official_TEST_rows"] == 0
    assert protocol["model_promotion_allowed"] is False
    cm = {"apiVersion": "v1", "kind": "ConfigMap",
          "metadata": {"name": name, "labels": LABELS},
          "data": {"worker.py": WORKER.read_text(),
                   "kali_publisher_sft_recipe.py": RECIPE.read_text(),
                   "protocol.json": (data / "protocol-private.json").read_text()}}
    secret = {"apiVersion": "v1", "kind": "Secret",
              "metadata": {"name": name + "-input", "labels": LABELS},
              "type": "Opaque", "data": {"payload.json.gz": base64.b64encode(
                  (data / "payload-private.json.gz").read_bytes()).decode()}}
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
                   "/cache/kali-redsage-aba-logs; "
                   "python -u /input/worker.py 2>&1 | tee " + log],
               "env": [{"name": "HF_HUB_OFFLINE", "value": "1"},
                       {"name": "OMP_NUM_THREADS", "value": "2"},
                       {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"}],
               "resources": {"requests": resources, "limits": resources},
               "volumeMounts": [{"name": "input", "mountPath": "/input", "readOnly": True},
                                {"name": "cache", "mountPath": "/cache"},
                                {"name": "scratch", "mountPath": "/scratch"}]}],
           "volumes": [{"name": "input", "projected": {"defaultMode": 256,
               "sources": [{"configMap": {"name": name}},
                           {"secret": {"name": name + "-input"}}]}},
               {"name": "cache", "persistentVolumeClaim": {"claimName": "miw113-kali-cuda-cache"}},
               {"name": "scratch", "emptyDir": {"sizeLimit": "24Gi"}}]}
    assert "priorityClassName" not in pod and "tolerations" not in pod
    job = {"apiVersion": "batch/v1", "kind": "Job",
           "metadata": {"name": name, "labels": LABELS,
                        "annotations": {"research.ucsd.edu/queue-mode": "one-gpu-bounded"}},
           "spec": {"activeDeadlineSeconds": protocol["queue_deadline_seconds"],
                    "backoffLimit": 0,
                    "ttlSecondsAfterFinished": protocol["result_ttl_seconds"],
                    "template": {"metadata": {"labels": LABELS}, "spec": pod}}}
    return protocol, cm, secret, job, data, name, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id", choices=["P05", "P06", "P07", "P08"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    protocol, cm, secret, job, data, name, log = build(args.candidate_id)
    for obj in (secret, cm, job):
        kube("create", "--dry-run=server", "-f", "-", payload=json.dumps(obj))
    if args.dry_run:
        print(json.dumps({"status": "SERVER_DRY_RUN_PASS", "GPU_count": 1,
                          "candidate_id": args.candidate_id,
                          "training_rows": protocol["training_rows"], "official_TEST_rows": 0}))
        return
    assert not kube("get", "jobs,pods,configmaps,secrets", "-l",
                    "app.kubernetes.io/managed-by=miw113", "-o", "name").stdout.strip()
    out = data / "gpu-attempt-a100"
    assert not out.exists(), "Do not overwrite a previous attempt"
    out.mkdir()
    (out / "protocol-private.json").write_bytes((data / "protocol-private.json").read_bytes())
    record = {"status": "SUBMITTING", "job_name": name,
              "submitted_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "queue_deadline_seconds": protocol["queue_deadline_seconds"],
              "pod_runtime_seconds": protocol["pod_runtime_seconds"],
              "result_ttl_seconds": protocol["result_ttl_seconds"],
              "private_log_on_pvc": log, "GPU_count": 1,
              "priority": "ordinary", "official_TEST_rows": 0,
              "protocol_sha256": sha(data / "protocol-private.json"),
              "cleanup_errors": []}
    receipt = out / "host-run-private.json"
    receipt.write_text(json.dumps(record, indent=2) + "\n")
    created = []
    try:
        for obj in (secret, cm, job):
            kube("create", "-f", "-", payload=json.dumps(obj))
            created.append((obj["kind"].lower(), obj["metadata"]["name"]))
        actual = json.loads(kube("get", "job", name, "-o", "json").stdout)
        uid = actual["metadata"]["uid"]
        assert uid
        owner = {"apiVersion": "batch/v1", "kind": "Job", "name": name,
                 "uid": uid, "controller": False, "blockOwnerDeletion": False}
        for kind, resource_name in (("secret", name + "-input"), ("configmap", name)):
            kube("patch", kind, resource_name, "--type=merge", "-p",
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
    print(json.dumps({"status": record["status"], "job_name": name,
                      "GPU_count": 1, "official_TEST_rows": 0}))


if __name__ == "__main__":
    main()
