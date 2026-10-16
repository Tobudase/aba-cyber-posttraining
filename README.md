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
- External-data screening found a promising public CyberForge trajectory source, but a project-level overlap audit found 62 of 100 source project names also in the reserved CyberGym index. Of 880 inspected Gemma teacher trajectory metadata records, 498 were from those same-name projects. The other 382 remain **manual-review candidates**, not training data; see [external-data review](docs/EXTERNAL_DATA_REVIEW.md).

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
3. Finish source provenance, grouped deduplication and candidate-quality review; freeze train/validation data. The 382 CyberForge records without an exact project-name match are still on hold pending repository/fork, vulnerability and licensing review.
4. Build the ABA control-model interface or use an existing compatible endpoint, then run a small controlled domain post-training experiment. The two-step synthetic GPU adapter check has already passed.
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
