# October 24: completed KaliBench CUDA / native ABA experiment

This release records a completed fixed-recipe engineering experiment, including
a negative adoption result. It supersedes earlier waiting-for-GPU reports.

## Result

The learner was `RISys-Lab/RedSage-K-SFT-GRPO` (~8.19B), pinned revision
`843e2e3096e7de68f5c35eb16238f4909f21695a`. One RTX A6000 ran a matched
baseline, one128-step LoRA candidate on128 TRAIN rows, and108-row post-training
development evaluation. Native ABA completed its real Setup, deterministic
verifier, enabled semantic review, worker, scoring and final delivery.

| Strict development correctness | Base | After LoRA |
| --- | ---: | ---: |
| Domain | 2/36 | 3/36 |
| Utility retention | 52/72 | 36/72 |

**Keep the original base; do not promote this adapter.** These exposed
source-silver development results are not official KaliBench ranking or evidence
of unseen generalization. The base previously saw official TRAIN. Official tests
and new confirmation data were not queried. No autonomous data generation or
adaptive candidate search was enabled in this fixed recipe.

[Full Chinese report](KALIBENCH_CUDA_POSTTRAIN_REPORT_2026-10-24.md).

## Public scope

Published: executed numerical worker, frozen protocol, generic dedicated GPU
resource mapping, deterministic pre-Setup scaffold and tests, numerical receipt
excerpts, aggregate comparison, recorded host-verification conclusions and
resource-cleanup summary. The job-name prefix in public job-building code is
generic; the numerical worker remains byte-identical to the frozen source.

Excluded: cluster/VM/PVC identifiers, internal endpoints, operational launch and
SSH scripts, credentials, raw native journals, raw predictions, protected
evaluation inputs, and all model/adapter tensors. An earlier broader publication
attempt was automatically blocked; this reduced release is based directly on the
previous remote commit and does not publish that rejected commit or its files.

The protocol retains an older RTX4090 allocation entry as history. The final
A6000 relocation changed only GPU model, storage prefix and freeze timestamp
before learner training. An independently matched A6000 baseline was collected;
the RTX4090 baseline was not used for the final comparison. The public archived
RTX4090 protocol allows comparison of those three changed fields. The numerical
worker was unchanged during the A6000 relocation.

Operator inputs were provided BEFORE native Setup and checked by real native
gates; they are not agent-created data. The private native metrics log replayed
actual receipt losses after training, so its timestamps are not step timings.
Utilization sampling starts after copying/dependency preparation and includes
model loading; it does not measure the whole GPU allocation lifecycle.

## Offline verification and limits

```sh
python3 scripts/verify-kali-cuda-publication.py
```

The script checks release hashes, frozen worker/protocol, numerical receipt
consistency, aggregate results and the adoption decision. Raw source receipts
and native artifacts stay private: the included original receipt hashes and host
verification conclusions record checks made at execution time, but cannot be
freshly recomputed from this public subset. The script does not independently
reproduce private native delivery bytes or recompute accuracy from raw outputs.
No GPU, model download, API call or cluster access is used.

Data-dependent unit tests require a separately obtained authorized local
tokenizer/input projection; these local test inputs are excluded from the release.
Full reruns require authorized data, model/runtime caches and private settings.
Do not relaunch the already completed experiment. Own compute was stopped and
private persistent data retained; further training requires a new frozen study.
