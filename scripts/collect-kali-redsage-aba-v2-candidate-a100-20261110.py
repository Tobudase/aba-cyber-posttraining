#!/usr/bin/env python3
"""Collect one repaired ABA candidate and remove owned resources."""

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
DATA = OUT = RECORD = NAME = None
BASE = ["kubectl", "--context", "nautilus", "-n", "ecepxie"]
LABEL = "app.kubernetes.io/managed-by=miw113"


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
               if line.startswith("ABA_CANDIDATE_RECEIPT=")]
    succeeded = bool(job.get("status", {}).get("succeeded"))
    try:
        assert succeeded and len(markers) == 1
        receipt = json.loads(markers[0])
        protocol = json.loads((DATA / "protocol-private.json").read_text())
        assert receipt["status"] == "COMPLETE_ABA_CANDIDATE"
        assert receipt["candidate_id"] == protocol["candidate_id"]
        assert receipt["protocol_sha256"] == sha(DATA / "protocol-private.json")
        assert receipt["worker_sha256"] == protocol["worker_sha256"]
        assert receipt["optimizer_steps"] == receipt["nonzero_gradient_steps"] == protocol["training_rows"]
        assert receipt["changed_tensors"] > 0
        assert receipt["dev_predictions"] == 128 and receipt["official_TEST_rows"] == 0
        assert receipt["adapter_reload_max_logit_delta"] <= 1e-4
        assert receipt["base_anchors_compared"] == 4
        anchors = [line.split("=", 1)[1] for line in logs.splitlines()
                   if line.startswith("PUBLISHER_SFT638_BASE_ANCHORS=")]
        assert len(anchors) == 1
        anchor_rows = json.loads(gzip.decompress(base64.b64decode(anchors[0], validate=True)))
        assert len(anchor_rows) == 4
        (OUT / "base-anchor-audit-private.json").write_text(
            json.dumps(anchor_rows, ensure_ascii=False, indent=2) + "\n")
        prefix = "ABA_CANDIDATE_PREDICTIONS="
        values = [line[len(prefix):] for line in logs.splitlines() if line.startswith(prefix)]
        assert len(values) == 1
        rows = json.loads(gzip.decompress(base64.b64decode(values[0], validate=True)))
        assert len(rows) == len({r["id"] for r in rows}) == 128
        assert all(r["arm"] == protocol["candidate_id"] for r in rows)
        (OUT / "candidate-predictions-private.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        base_values = [line.split("=", 1)[1] for line in logs.splitlines()
                       if line.startswith("ABA_BASE_PREDICTIONS=")]
        assert len(base_values) == 1
        base_rows = json.loads(gzip.decompress(base64.b64decode(base_values[0], validate=True)))
        assert len(base_rows) == len({r["id"] for r in base_rows}) == 128
        assert {r["id"] for r in base_rows} == {r["id"] for r in rows}
        assert all(r["arm"] == "base" for r in base_rows)
        (OUT / "base-predictions-private.json").write_text(
            json.dumps(base_rows, ensure_ascii=False, indent=2) + "\n")
        (OUT / "receipt-private.json").write_text(json.dumps(receipt, indent=2) + "\n")
        record.update(status="COLLECTED", GPU=receipt["GPU"],
                      optimizer_steps=protocol["training_rows"], dev_predictions=128)
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
                      "optimizer_steps": record.get("optimizer_steps"),
                      "dev_predictions": record.get("dev_predictions"),
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
    parser.add_argument("candidate_id", choices=["P05", "P06", "P07", "P08"])
    parser.add_argument("--watch-seconds", type=int, default=0)
    args = parser.parse_args()
    global DATA, OUT, RECORD, NAME
    DATA = ROOT / "data/benchkit/kali-redsage-aba-publisher-v2-2026-11-10" / args.candidate_id
    OUT = DATA / "gpu-attempt-a100"
    RECORD = OUT / "host-run-private.json"
    NAME = "miw113-redsage-aba-" + args.candidate_id.lower()
    assert 0 <= args.watch_seconds <= 7200
    started = time.monotonic()
    while True:
        done = check_once()
        if done or not args.watch_seconds or time.monotonic() - started >= args.watch_seconds:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
