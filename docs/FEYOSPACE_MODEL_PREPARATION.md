# Feyospace-v1.1-small candidate preparation (2026-10-16)

## Decision

Keep `Qwen/Qwen3.8-27B` as the licensed, reproducible **post-training starting point**. Treat `feyospace/feyospace-v1.1-small` as a higher-scoring **public-weight candidate/reference**, not yet an approved post-training base: the checked Hugging Face metadata has no license identifier and the repository has no license file. Public access to tensor files does not establish permission to fine-tune or redistribute derivatives. The original Qwen license cannot be assumed to cover this derivative.

This distinction matters for Han's request for an "open sourced" checkpoint. Clarify rights with the model publisher or choose the licensed Qwen starting point before training Feyospace. No request to the publisher or the group has been sent by this preparation.

## Verified evidence

| Item | Result | Evidence |
| --- | --- | --- |
| Identity | `feyospace/feyospace-v1.1-small`, pinned SHA `ab6a8372eceb18c10357e2683ce14808217bf5e9` | [Hugging Face model](https://huggingface.co/feyospace/feyospace-v1.1-small), pinned API response |
| Access | Public and ungated; 12 BF16 weight shards listed, **weights not downloaded here** | [Hugging Face files](https://huggingface.co/feyospace/feyospace-v1.1-small/tree/main) |
| Size | 27,781,427,952 parameters; about 55.56 GB of BF16 tensor payload before cache, runtime, activations, or optimizer | HF safetensors metadata; arithmetic estimate |
| Architecture | `Qwen3_5ForConditionalGeneration`, `qwen3_5` config | Pinned `config.json` |
| License | No card `license` value and no LICENSE/COPYING file in checked repository listing | Pinned HF API response; `configs/feyospace-v1.1.candidate.lock.json` |
| CyberGym result | 84.41% appears in the official model-focused leaderboard, with Claude Code as the agent harness and one trial | [CyberGym leaderboard](https://www.cybergym.io/cybergym/), [publisher model card](https://huggingface.co/feyospace/feyospace-v1.1-small) |
| Baseline comparison | Qwen3.8-27B 54.51% is a **paper-reported** baseline, not a standalone official leaderboard row | [Feyospace paper](https://arxiv.org/html/2609.08418v1) |

The official page aggregates submissions and harnesses. The 84.41% entry does not establish that our own tooling, inference budget, or post-training run will get that score. The publisher's September 23 fifth-place statement is a dated snapshot, not a permanent rank.

The [Feyospace-v1 paper](https://arxiv.org/html/2609.08418v1) describes using 200 CyberGym tasks during development/trajectory analysis. This is relevant exposure for a strict independent evaluation. It does **not** by itself prove gradient training on official answers, but the provenance and overlap need review before interpreting further CyberGym gains. No checkpoint's training corpus has been independently audited here.

## What was actually prepared

`scripts/prepare-feyospace-metadata.py` downloads six small, pinned config/tokenizer/processor files via system TLS and records each SHA256 in `configs/feyospace-v1.1.candidate.lock.json`. The files are in ignored `.tools/model-tokenizer/feyospace-v1.1-ab6a8372eceb/`. The script does not request tensor shards. The lock records an unresolved license and `weights_downloaded_locally=false`.

`scripts/check-feyospace-preparation.py` verifies those hashes offline and tests a benign assistant response and `add_numbers` tool exchange. It passed using a tokenizer-only Python environment (Transformers 4.57.6); see `docs/verification/feyospace-preparation.json`. Both Qwen and Feyospace tokenizers expose 248,077 tokens and the same chat template, but their `tokenizer.json` files differ; do not silently substitute one tokenizer for the other. This is **not** a model-load, GPU, generation-quality, LoRA, or benchmark result. The previously validated Qwen3.5 Linux CPU stack is a useful compatibility starting point, not proof that Feyospace full-weight inference or training works.

To reproduce the metadata check, run `python3 scripts/prepare-feyospace-metadata.py`, then run `python scripts/check-feyospace-preparation.py` in an environment with Transformers 4.57.6 or newer and a tokenizer backend. Both scripts use only a fixed benign synthetic prompt; neither reads CyberGym tasks.

## Gate before any real training

1. Resolve Feyospace license/derivative rights. If unresolved, use licensed Qwen3.8-27B for post-training and Feyospace only as a reported-result reference.
2. Decide with the group whether to retain CyberGym or switch to a cybersecurity benchmark that has a suitable, accessible checkpoint and a clean evaluation protocol.
3. Lock a separate external training/validation dataset. Audit same-repository, CVE/fix-commit, code/family, and task identity overlaps with official evaluation, and record what could not be checked. The existing three pilot candidates are **not training-ready**.
4. Recheck actual GPU availability. A 27.8B BF16 tensor payload alone exceeds a 40 GB card; quantization, multi-GPU placement, context length and adapter training each need a measured memory test. Do not infer fit from parameter count or a CPU tokenizer check.
5. Freeze a matched baseline protocol: exact checkpoint revision, harness, tools, task set, inference budget, seeds/trials and scoring. Use development tasks for adjustments; official evaluation/testing remains untouched until final assessment.
6. After those gates, validate a benign full-checkpoint load and one short generation, then a tiny synthetic adapter update before domain data or ABA-managed iterations. Record cost, wall time, memory and failure modes.

No GPU Job was submitted in this preparation. Recheck actual compute allocation before attempting a full-weight load.
