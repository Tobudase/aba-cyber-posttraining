# ABA Cybersecurity Post-training Research

Research preparation and engineering validation for using an ABA agent to adapt an open-weight language model on cybersecurity tasks.

The current objective is to select a suitable benchmark/model pair and evaluate ABA-managed data preparation and post-training. CyberGym is an initial benchmark, not a required final choice. VulnLLM-R-7B is an engineering candidate; it is not a finalized research selection.

## Verified progress

- Fixed-revision source/model metadata and evaluation-preservation rules.
- CyberGym infrastructure and bounded neutral-input checks (not vulnerability-solving performance).
- Small-model architecture/LoRA compatibility checks (not domain training).
- A full **7,615,616,512-parameter VulnLLM-R-7B** checkpoint downloaded and loaded on Linux CPU.
- **197 Linear layers converted to dynamic INT8**, followed by four actual structured generations, parsing and independent metric recomputation.
- Final engineering run: **4/4 parseable outputs, 2/4 label matches**, all predictions negative; 231.391 seconds including model download, loading, conversion and generation, excluding dependency installation.
- A 2,562-record training-source audit, conservative grouping, test-marker quarantine and a 12-request annotation pilot. Three candidates remain under review; none is marked training-ready.
- A fixed-revision Feyospace-v1.1-small check: full BF16 weights loaded on an A100-80GB and generated a benign short response. A later **two-step synthetic NF4 QLoRA check on the actual checkpoint** also completed, changed adapter tensors, and passed adapter reload consistency. These use no cybersecurity training records and do not reproduce the reported 84.41% CyberGym result. The checked public repository has no explicit license; no weights or derivatives are published here. See [candidate preparation](docs/FEYOSPACE_MODEL_PREPARATION.md), [GPU validation](docs/FEYOSPACE_GPU_VALIDATION.md), and [synthetic QLoRA result](results/feyospace-qlora-synthetic.json).
- External-data screening found a promising public CyberForge trajectory source, but a project-level overlap audit found 62 of 100 source project names also in the reserved CyberGym index. Of 880 inspected Gemma teacher trajectory metadata records, 498 were from those same-name projects. Within the remaining 382 records, 63/290 `patch` and 22/92 `poc-san` trajectories have matching public vulnerability IDs; **none is approved for training**. See [external-data review](docs/EXTERNAL_DATA_REVIEW.md).
- For those 85 linked records, [pinned upstream root-license screening](docs/CYBERFORGE_UPSTREAM_LICENSE_REVIEW.md) found 10 projects with a recognized SPDX label (43 records), 12 with `NOASSERTION` (40), and one lacking a usable HTTPS source URL (2). These checks do not approve any training data.
- An alternative benchmark/model pair has been documented: [SEC-bench patch × the original Gemma 4 31B checkpoint](docs/SEC_BENCH_ALTERNATIVE.md). It has a clear Apache-2.0 model license and a published 58.0% base-model patch result under the CyberForge paper's agent scaffold, but this project has not selected, deployed, or reproduced that pair.
- NRP's documented Anthropic-compatible endpoint passed bounded streamed-text, tool-block and tool-result probes for `qwen3-small` and `qwen3`. Both returned `end_turn` for a tool call where `tool_use` was expected; a subsequent **real Claude Agent SDK 0.2.148 tool round-trip passed** on macOS arm64 with `qwen3-small`: one restricted local addition tool call and a final answer of 15. See [ABA/NRP compatibility](docs/ABA_NRP_COMPAT.md). ABA end-to-end on Linux is still untested.

**These are engineering checks, not benchmark results.** The VulnLLM-R CPU run uses INT8, a short output budget, an assistant prefill and a task-level answer grammar. A preceding unconstrained short-generation run produced 0/4 parseable outputs. The GPU QLoRA run uses only a harmless synthetic string and arithmetic tool exchange. No domain post-training, ABA end-to-end optimization, published-score reproduction or performance improvement is claimed.

## Repository contents

- `scripts/`: metadata preparation, data auditing, bounded model probes, inference and result checks.
- `configs/`: public model/source revisions, example environment locks and evaluation rules.
- `results/`: selected verified result summaries, without raw account or cluster logs.
- `docs/`: project status, reproduction scope and next steps.

This is a curated code-and-results snapshot. Raw third-party datasets, model weights, raw annotations, personal research correspondence, host-specific configuration and credentials are intentionally not part of this repository. Some scripts require regenerated local inputs; see [Reproduction notes](docs/REPRODUCTION.md).

## Next research steps

1. Coordinate shared work and confirm the final benchmark/model pair.
2. Establish adequate generation budgets and a fixed inference/evaluation protocol using development material.
3. Resolve the 297 missing CyberForge vulnerability IDs and finish validation, source provenance, grouped deduplication, task compatibility and licensing review for the 85 linked records before freezing any external train/validation data.
4. Restore reliable Linux access, then run a minimal budget-capped ABA setup with task-neutral synthetic data. The Claude SDK calculator round-trip passed on macOS, but ABA end-to-end has not run. The two-step synthetic GPU adapter check has already passed.
5. Compare the same checkpoint before/after training under matched budgets. Keep official testing separate from training and tuning.

## Evaluation rule

Official benchmark tasks are evaluation-only. Earlier CyberGym internal train/dev splits were cancelled before training and must not be revived. Public training sources may overlap with a checkpoint's prior training; engineering development examples are not independent generalization tests.

## Upstream projects

- [AIBuildAI LLM Post-train Agent](https://github.com/aibuildai-inc/aibuildai-llm-posttrain-agent)
- [CyberGym](https://github.com/sunblaze-ucb/cybergym)
- [VulnLLM-R](https://github.com/ucsb-mlsec/VulnLLM-R)
- [VulnLLM-R-7B checkpoint](https://huggingface.co/Virtue-AI-HUB/VulnLLM-R-7B)
- [NRP documentation](https://nrp.ai/documentation/)

This repository contains neither upstream model weights nor a release of those projects. See [Notices](NOTICE.md).
