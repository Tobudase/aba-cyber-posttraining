# Resource validation — October 23, 2026

Nautilus admission has recovered: the namespace accepted new jobs. A100 scheduling did not find a suitable available node during the finite probe; that request was deleted. This differs from the earlier global `pods=0` admission failure.

## Actual completed checks

- CPU-only Linux job: four fixed command-semantics checks passed, using inert authored fixture inputs and no external target. Packages included TShark 3.6.2, YARA 4.1.3, net-tools and pev 0.81. They differ from the upstream Kali help snapshot, so this is selected mechanism validation, not whole-benchmark container reproduction.
- CPU-only replay check: all 32authored general utility examples produced their expected output under C locale.
- First generic GPU attempt: allocated GTX 1080 Ti (sm61), which the pinned PyTorch 2.8 / CUDA 12.8 image does not support. It failed before optimizer steps and was deleted.
- Corrected GPU probe: normal scheduler capability constraints selected an **NVIDIA A10, 23,686,938,624 bytes**. PyTorch 2.8.0+cu128 completed 20 synthetic linear-layer optimizer updates; loss 0.333109→0.325011. Peak tensor allocation was 25.8MB; compute took 2.05 seconds. The finished job was deleted. This proves a small CUDA runtime path, not 8B LLM training, sustained utilization, or full memory capacity validation.

The pinned runtime image digest is in `verification/kali-cuda-runtime-2026-10-23.json`. Setup failures are preserved in `verification/kali-cpu-cache-preparation-attempts-2026-10-23.json`.

## Actual 8B CUDA training and persistence check — passed

All four official RedSage weight shards (16,381,516,824 bytes) plus pinned metadata were prepared in a CPU-only job and SHA256-verified. A subsequent L4 job staged another checksum-verified copy to node-local scratch, loaded the real 8B checkpoint and completed 20 optimizer updates on two TRAIN records only.

- Model: `RISys-Lab/RedSage-K-SFT-GRPO`, revision `843e2e3096e7de68f5c35eb16238f4909f21695a`.
- Hardware: NVIDIA L4, 23,745,396,736 bytes total GPU memory.
- Recipe: bitsandbytes NF4, BF16 compute; PEFT rank 16 / alpha 32 on all q/v layers; batch 1, LR 1e-5, AdamW weight decay 0, seed 42. This differs from the Mac recipe.
- Genuine optimization: 144 changed trainable tensors, 7,667,712 trainable parameters; training loss 1.7258→0.6187 on the two repeated records. This demonstrates fitting, not generalization.
- Adapter save/reload: maximum logit difference 0.0 after zeroing and restoring adapter tensors.
- Peak CUDA allocation: 10,146,335,232 bytes. Recorded GPU memory usage reached 12,456 MiB; allocations and physical usage are different measures.
- Wall time 442.7 seconds, including 404.8 seconds of local staging. After staging, the recorded computation samples reached 97–100% GPU utilization. Samples start after staging and do not establish full-lifecycle average utilization.
- No domain dev, confirmation or official test rows were queried; no ABA controller ran. This runtime check was not a third candidate in the frozen development comparison.
- Job finished and was deleted. No own Kali pods remained at cleanup. The 32 GiB public-model/dependency cache is retained for subsequent research; the old VM root volume was untouched. No weights or adapter tensors are published.

The first real 8B attempt waited on remote block-storage mmap and was stopped before any optimizer step was observed. The retry used bounded 24 GiB `emptyDir` scratch and completed. Source and receipts are in `verification/kali-cuda-smoke-remote-storage-2026-10-23.json`, `kali-cuda-prefetch-complete-2026-10-23.json` and `kali-cuda-8b-smoke-2026-10-23.json`. The original stopped runner is also preserved. [NRP local scratch guidance](https://nrp.ai/documentation/userdocs/storage/local/) informed the change.

Startup staging dominated the short GPU job. Before repeated ABA experiments, move dependency preparation into a validated immutable image and optimize checkpoint staging/reuse; do not treat this startup-heavy smoke as proof of an efficient long-running workload or scale it to eight GPUs. The actual CUDA recipe requires its own matched baseline/protocol for domain scores. Actual ABA domain training, private evaluator isolation and controlled submission remain unvalidated.

## Resource controls

Finite batch Jobs with active deadlines, restart limits and cleanup; matched resource requests/limits; one GPU at most; no sleeping Job, quota/priority changes or namespace bypass. CPU downloads do not hold a GPU. Short diagnostics do not establish sustained policy-compliant utilization for a long training run; the full workload must be monitored and sized separately. See [NRP cluster policies](https://nrp.ai/documentation/userdocs/start/policies/).
