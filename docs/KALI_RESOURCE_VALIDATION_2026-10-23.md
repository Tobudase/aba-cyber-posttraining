# Resource validation — October 23, 2026

Nautilus admission has recovered: the namespace accepted new jobs. A100 scheduling did not find a suitable available node during the finite probe; that request was deleted. This differs from the earlier global `pods=0` admission failure.

## Actual completed checks

- CPU-only Linux job: four fixed command-semantics checks passed, using inert authored fixture inputs and no external target. Packages included TShark 3.6.2, YARA 4.1.3, net-tools and pev 0.81. They differ from the upstream Kali help snapshot, so this is selected mechanism validation, not whole-benchmark container reproduction.
- CPU-only replay check: all 32authored general utility examples produced their expected output under C locale.
- First generic GPU attempt: allocated GTX 1080 Ti (sm61), which the pinned PyTorch 2.8 / CUDA 12.8 image does not support. It failed before optimizer steps and was deleted.
- Corrected GPU probe: normal scheduler capability constraints selected an **NVIDIA A10, 23,686,938,624 bytes**. PyTorch 2.8.0+cu128 completed 20 synthetic linear-layer optimizer updates; loss 0.333109→0.325011. Peak tensor allocation was 25.8MB; compute took 2.05 seconds. The finished job was deleted. This proves a small CUDA runtime path, not 8B LLM training, sustained utilization, or full memory capacity validation.

The pinned runtime image digest is in `verification/kali-cuda-runtime-2026-10-23.json`. Setup failures are preserved in `verification/kali-cpu-cache-preparation-attempts-2026-10-23.json`.

## 8B preparation stage

A bounded CPU-only model-cache stage is resuming the official RedSage checkpoint by pinned revision, exact file sizes and SHA256. Public reports will be refreshed with its final outcome. Dependencies and weights are prepared before any GPU model allocation. The 32 GiB project cache contains public model files and dependencies, not protected research data; it is not uploaded to GitHub. The existing VM root volume is left untouched.

A finite 20-step NF4 LoRA smoke script is prepared. It uses two TRAIN records only and records genuine parameter changes, saved-adapter reload, memory and GPU telemetry. It has not yet established 8B GPU readiness. CUDA (NF4 / rank 16 / all q-v) and Mac (MLX affine4 / rank 8 / last 4 layers) use different recipes, so a future formal CUDA comparison needs its own matched baseline and frozen protocol.

Actual ABA domain training, private evaluator isolation and automatic GPU submission remain unvalidated. Do not enable ABA search or claim an official benchmark result from runtime preparation.

## Resource controls

Finite batch Jobs with active deadlines, restart limits and cleanup; matched resource requests/limits; one GPU at most; no sleeping Job, quota/priority changes or namespace bypass. CPU downloads do not hold a GPU. Short diagnostics do not establish sustained policy-compliant utilization for a long training run; the full workload must be monitored and sized separately. See [NRP cluster policies](https://nrp.ai/documentation/userdocs/start/policies/).
