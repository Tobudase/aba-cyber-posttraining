#!/usr/bin/env python3
"""Collect publisher TRAIN internal holdout without publishing raw predictions."""

import argparse
import base64
import datetime
import gzip
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/benchkit/kali-redsage-publisher-confirm64-2026-11-10"
OUT = DATA / "gpu-attempt1"
RECORD = OUT / "host-run-private.json"
BASE = ["kubectl", "--context", "nautilus", "-n", "ecepxie"]
LABEL = "app.kubernetes.io/managed-by=miw113"
NAME = "miw113-redsage-confirm64"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def kube(*args, check=True):
    result = subprocess.run(BASE + list(args), capture_output=True, text=True, timeout=70)
    if check and result.returncode:
        raise RuntimeError("kubectl " + args[0] + " failed: " + result.stderr[-350:])
    return result


def save(record):
    RECORD.write_text(json.dumps(record, indent=2) + "\n")


def collect(record, job, pod):
    assert job["metadata"]["uid"] == record["job_uid"]
    logs = kube("logs", pod["metadata"]["name"], check=False).stdout if pod else ""
    (OUT / "worker-log-private.txt").write_text(logs)
    markers = [line.split("=", 1)[1] for line in logs.splitlines()
               if line.startswith("EXTERNAL26_RECEIPT=")]
    succeeded = bool(job.get("status", {}).get("succeeded"))
    try:
        assert succeeded and len(markers) == 1
        receipt = json.loads(markers[0])
        protocol = json.loads((DATA / "protocol-private.json").read_text())
        assert receipt["status"] == "COMPLETE_REDSAGE_PUBLISHER_TRAIN_HOLDOUT64"
        assert receipt["protocol_sha256"] == sha(DATA / "protocol-private.json")
        assert receipt["worker_sha256"] == protocol["worker_sha256"]
        assert receipt["historical_anchors_compared"] == 8
        audit_markers = [line.split("=", 1)[1] for line in logs.splitlines()
                         if line.startswith("PUBLISHER_ANCHOR_AUDIT=")]
        assert len(audit_markers) == 1
        audit = json.loads(gzip.decompress(base64.b64decode(audit_markers[0], validate=True)))
        assert len(audit) == 8
        assert sum(a["exact_cross_gpu_match"] for a in audit) == receipt["historical_anchors_exact_cross_gpu_matches"]
        (OUT / "anchor-audit-private.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
        assert receipt["source_rows"] == 64
        assert receipt["optimizer_steps"] == receipt["official_TEST_rows"] == 0
        for arm in ("base", "sft"):
            prefix = "PUBLISHER_HOLDOUT64_PREDICTIONS_" + arm.upper() + "="
            values = [line[len(prefix):] for line in logs.splitlines() if line.startswith(prefix)]
            assert len(values) == 1
            rows = json.loads(gzip.decompress(base64.b64decode(values[0], validate=True)))
            assert len(rows) == len({r["id"] for r in rows}) == 64
            assert all(r["arm"] == arm for r in rows)
            (OUT / (arm + "-predictions-private.json")).write_text(
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        (OUT / "receipt-private.json").write_text(json.dumps(receipt, indent=2) + "\n")
        record.update(status="COLLECTED", GPU=receipt["GPU"],
                      historical_anchors_compared=8, rows_each_arm=64)
    except BaseException as exc:
        record.update(status="FAILED", job_succeeded=succeeded,
                      receipt_marker_count=len(markers),
                      error_type=type(exc).__name__, error=str(exc)[:200],
                      pod_phase=pod.get("status", {}).get("phase") if pod else "NoPod")
    record["collected_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(record)
    response = kube("delete", "job", NAME, "--ignore-not-found=true", "--wait=true",
                    "--timeout=60s", check=False)
    if response.returncode:
        record["cleanup_errors"].append("job_delete_failed")
    for kind, name in (("configmap", NAME), ("secret", NAME + "-input")):
        if kube("get", kind, name, check=False).returncode == 0:
            response = kube("delete", kind, name, "--ignore-not-found=true", "--wait=true",
                            "--timeout=45s", check=False)
            if response.returncode:
                record["cleanup_errors"].append(kind + "_delete_failed")
    left = kube("get", "jobs,pods,configmaps,secrets", "-l", LABEL, "-o", "name").stdout.splitlines()
    record["remaining_owned_resources"] = len(left)
    save(record)
    print(json.dumps({"status": record["status"], "GPU": record.get("GPU"),
                      "rows_each_arm": record.get("rows_each_arm"),
                      "cleanup_errors": record["cleanup_errors"],
                      "remaining_owned_resources": len(left),
                      "official_TEST_rows": 0}), flush=True)
    return True


def check_once():
    record = json.loads(RECORD.read_text())
    if record["status"] in {"COLLECTED", "FAILED"}:
        print(json.dumps({"status": record["status"], "GPU": record.get("GPU"),
                          "official_TEST_rows": 0}), flush=True)
        return True
    assert record["status"] in {"QUEUED_OR_STARTING", "PENDING", "RUNNING"}
    response = kube("get", "job", NAME, "-o", "json", check=False)
    if response.returncode:
        raise RuntimeError("Queued Job missing before collection; inspect private PVC log")
    job = json.loads(response.stdout)
    assert job["metadata"]["uid"] == record["job_uid"]
    pods = json.loads(kube("get", "pods", "-l", "job-name=" + NAME, "-o", "json").stdout)["items"]
    assert len(pods) <= 1
    pod = pods[0] if pods else None
    phase = pod.get("status", {}).get("phase", "NoPod") if pod else "NoPod"
    if job.get("status", {}).get("succeeded") or job.get("status", {}).get("failed"):
        return collect(record, job, pod)
    record["status"] = "RUNNING" if phase == "Running" else "PENDING"
    record["last_checked_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record["last_pod_phase"] = phase
    record["pod_scheduled"] = bool(pod and pod.get("spec", {}).get("nodeName"))
    save(record)
    print(json.dumps({"status": record["status"], "pod_phase": phase,
                      "pod_scheduled": record["pod_scheduled"],
                      "official_TEST_rows": 0}), flush=True)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch-seconds", type=int, default=0)
    args = parser.parse_args()
    assert 0 <= args.watch_seconds <= 7200
    started = time.monotonic()
    while True:
        done = check_once()
        if done or not args.watch_seconds or time.monotonic() - started >= args.watch_seconds:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
