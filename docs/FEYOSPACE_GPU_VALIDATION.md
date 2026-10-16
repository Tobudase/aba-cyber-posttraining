# Feyospace-v1.1-small full-weight engineering check

The checkpoint at revision `ab6a8372eceb18c10357e2683ce14808217bf5e9` was loaded from all 12 BF16 weight shards on one NVIDIA A100-SXM4-80GB. Six pinned metadata file hashes were verified. A short synthetic prompt, “Reply with the word OK.”, generated `OK` in four new tokens. The test used Transformers 5.20.0, Accelerate 1.15.0 and the PyTorch 2.8.0 CUDA runtime. PyTorch peak GPU allocation was 54,912,407,552 bytes. The 152-second script timing includes download and model loading; it is not a generation-throughput metric.

The result was emitted to the log before the opportunistic Job reached `Complete`. The scheduler then preempted the Pod for a higher-priority workload. The Job and its input ConfigMap were deleted, and a later query confirmed no test Pod remained. This supports **full-weight load and short benign generation**, not a clean Job completion or a benchmark score.

A separate two-step synthetic QLoRA compatibility Job was admitted but remained `Pending` because no matching A100 was available. It was cleaned without downloading the checkpoint or taking any optimizer step. Actual 27B adapter training remains unverified. No CyberGym tasks or real cybersecurity training examples were used in either check. Official evaluation/testing remains reserved.

The checked public model repository does not state a license. This result does not assert permission to train, redistribute derivatives, or treat the model as universally open-source. Those rights must be recorded separately before derivative publication.

See [pinned model metadata](../configs/feyospace-v1.1.candidate.lock.json) and the [GPU smoke code](../scripts/test-feyospace-gpu.py). The public repository excludes raw cluster logs, operational manifests and model tensors.
