# ABA Cybersecurity Post-training Research

Research code, traceable external pilot data, and engineering evidence for using an ABA agent to adapt open-weight language models on cybersecurity tasks.

## October 23: expanded data and frozen replay ablation completed

Expanded the domain pool to **156 source-silver rows / 80 correlated families**, added **32 independent-source general utility replay rows**, and verified all32 replay fixtures plus four selected semantic checks on Linux. Mandatory-option coverage gaps fell from34/36to12/36 in the exposed domain development set.

Two predeclared128-step LoRA arms started from the original RedSage-K8B base. Both used the same96-row domain core; control repeated32domain records, treatment replaced those32presentations with replay. Equal steps do not mean equal tokens or domain exposure.

| Matched development | Original base | Domain control | Domain + replay |
| --- | ---: | ---: | ---: |
| Domain Exact / option diagnostic |6/36|5/36|5/36|
| CLI retention Exact / option diagnostic |66/72|54/72|54/72|
| Retention native Total |97.22|89.63|80.37|

**Keep the original base.** Neither candidate passed the frozen rule; this replay did not solve the regression. These are exposed development results from manual local SFT. Actual ABA, fresh independent validation and official benchmark evaluation remain pending.

Read the [full ablation report](docs/KALI_REPLAY_ABLATION_REPORT_2026-10-23.md) and [paired evidence](docs/verification/kali-replay-v2/comparison.json). Nautilus now also passed a **real 20-step 8B NF4 LoRA runtime check on one L4**, including genuine parameter changes and adapter save/reload with zero logit difference. The finished job was cleaned up; this is training/persistence validation on two TRAIN records, not benchmark evaluation or actual ABA. Startup staging still needs optimization before repeated runs. The [resource report](docs/KALI_RESOURCE_VALIDATION_2026-10-23.md) records the precise stage reached.

## October 23: fixed document-data SFT — negative result

Completed a single frozen 108-step LoRA experiment on RedSage-K-SFT-GRPO (8B, local MLX affine4, M2 Pro/16GiB), using 108 source-silver rows across 55 correlated intent families. Matched inference used the SFT-aligned prefix without tool help.

| Authored development set | Original base | New adapter |
| --- | ---: | ---: |
| Domain Exact / option diagnostic | 6/36 | 5/36 |
| General CLI retention Exact / option diagnostic | 66/72 | 54/72 |

**Keep the original base; do not promote the adapter.** Domain Total rose from 73.41 to 76.45, but the frozen acceptance rule failed. The 12 retention regressions belong to two correlated tshark families. These are development engineering results, not official KaliBench scores or actual ABA results.

A preceding prefix control brought the earlier base and 20-step adapter to the same 66/72, so the older 61→62 comparison below is historical and does not establish training gains. Domain inference controls were native 4/36, aligned 6/36, and aligned with tool help 25/36; tool-help gains are inference assistance, not learning.

Read the [full report](docs/KALI_DOC_SFT_REPORT_2026-10-23.md), [frozen comparison](docs/verification/kali-doc-sft-v1-2026-10-22/comparison.json), and [public reproduction instructions](docs/REPRODUCTION.md). Released: training data, 36 search-dev rows, scripts, predictions and receipts. New confirmation bodies and all tensors remain excluded. Actual ABA/CUDA integration and independent semantic validation are pending.

**October 21 preparation snapshot (historical):** the current preparation covers **AthenaBench and KaliBench**, sharing training and evaluation interfaces before an eventual return to CyberGym. **At that point, formal BF16 baselines, actual 8B domain post-training, and ABA domain experiments had not run.** GPU job admission remains blocked; no cluster GPU jobs were launched during this preparation.

## October 22: KaliBench real 8B pilot

Minhao's current track is **KaliBench**; AthenaBench is handled by the collaborator. Using hash-verified official RedSage-K-SFT-GRPO weights, locally quantized to MLX affine4/group64, the following cycle actually ran on an Apple M2 Pro with 16GiB memory:

| Same 72 external dev examples | E0 unchanged base | E1 continued SFT, 20 steps |
| --- | ---: | ---: |
| Native Exact / option-value diagnostic | 61/72 (84.72%) | 62/72 (86.11%) |
| Native Total Score | 93.75 | 93.52 |
| Runtime failures / truncations | 0 / 0 | 0 / 0 |

**This is not reliable improvement:** five cases improved and four regressed; the gains mainly canonicalize a `head` pipeline while the certificate task drops `openssl` in four cases. Total Score decreased. The 72 examples are correlated variants of 12 authored families. Keep the original base; the tiny adapter is not promoted as the final model.

The model completed **20 real supervised optimizer updates**, changing 16 LoRA tensors (425,984 trainable parameters, last four layers q/v); persisted-adapter reload had zero logit difference. Training peak Metal memory was 5.72GB. These are actual pretrained 8B updates, distinct from earlier random tiny checks. No official tests or the 36 reserved confirmation examples were queried. This is a local quantized engineering pilot, **not official BF16 evaluation and not ABA**.

Start with [Kali pilot results and reproduction](docs/KALI_MLX_PILOT.md), [paired results](results/kali-mlx/kali-mlx-pilot-comparison-2026-10-22.json), and [code](scripts/run-kali-mlx-pilot.py). Raw authored-dev predictions and text receipts are included; model and adapter tensors, account settings and private logs are excluded.

## October 21 preparation evidence

| Component | Actual result | Limits |
| --- | --- | --- |
| Athena external RCM data | [161 train / 22 dev / 9 reserved confirmation](data/benchkit/athena-v3/) | AI-reviewed source-silver, eight training classes; not official Athena data or expert gold |
| Additional candidate review | 177 candidates dispositioned: 133 accepted, 9 ambiguous holds, 35 structural/source holds | 142 complete descriptions reviewed; accepted rows undergo separate grouping/deduplication before splitting |
| Kali training audit | 3,504 original train rows; 128 held, 3,376 screened | Original third-party train records are not redistributed; screening is not semantic gold validation |
| Kali external dev | [72 search / 36 confirmation](data/benchkit/kali-external-dev/) | 18 authored template families, nine basic tools; not representative full-task evaluation |
| Real local inference | Cisco official 8B Q4: native prefix 19/22 source-label matches; without opening `<think>` 20/22 | Same exposed RCM dev, no new training; not an official benchmark score or evidence of general improvement |
| Training plumbing | Random tiny Llama and Qwen models: 2 optimizer steps, changed tensors, adapter save/reload delta 0 | Not pretrained 8B domain training |
| Data/tokenizer/package checks | 192 Athena and 3,484 Kali rows tokenized; 23 targeted tests passed in the original workspace | Full original test suite depends on local audit inputs; candidate GPU environment remains unvalidated |
| ABA domain setup | Draft protocols and worker interfaces prepared | Controlled GPU submission/private evaluator bridge has not run end to end |

**Scoring caveat:** the pinned Kali scorer can give full Exact/Total credit to a prediction with an incorrect option value. We retain native metrics and add a separate diagnostic; it is not an official replacement or complete shell semantic checker. The audit does not establish the impact on published model rankings. Athena VSP also needs explicit valid-output coverage reporting.

Start with the [current experiment preparation](docs/ATHENA_KALI_PROGRESS.md), [reproduction instructions](docs/REPRODUCTION.md), and [status](docs/STATUS.md). See [local prefix comparison](results/athena-prefix-comparison-2026-10-21.json) and [scoring evidence](results/benchkit-scorer-audit-summary.json).

## Current provisional model pairs

- Athena: [fdtn-ai/Foundation-Sec-8B-Reasoning](https://huggingface.co/fdtn-ai/Foundation-Sec-8B-Reasoning), revision `63c930c82d7646226d33502bec5870019738400e`.
- Kali: [RISys-Lab/RedSage-K-SFT-GRPO](https://huggingface.co/RISys-Lab/RedSage-K-SFT-GRPO), revision `843e2e3096e7de68f5c35eb16238f4909f21695a`.

Both are already specialized models; their additional training headroom is unproven. RedSage trained on the official 3,504 training examples, so a new split of those records is not unseen validation. Its model card did not declare a license field at the pinned revision; no unrestricted redistribution permission is inferred. No model tensors or derived adapters are released here.

The [protocols](configs/benchkit/) are explicitly drafts. Plan: matched E0 pretrained baseline → E1 fixed SFT → E2 bounded ABA search, select using external dev only, freeze the protocol, then separately evaluate official tests. The official final-evaluation switch remains disabled. Athena preparation currently covers RCM only, not all six tasks.

## Historical CTI pilot and earlier evidence

The following sections preserve the October 17 pilot and earlier engineering work. Their defaults and next-step suggestions are historical, not the current Athena/Kali protocol.

## Public pilot data

The released [pilot](data/raw/cti-pilot-v1/) contains 63 derived examples from pinned public CVE CNA records. The training file has 47 rows; the development file has 16. Classes: CWE-787, 125, 502, 78, 918, 89, 22 and 79.

- Descriptions and labels come from the pinned CNA source, with individual source URL and SHA256.
- Semantic decisions and split hashes are in the [manifest](data/manifests/cti-source-pilot-v1.json).
- Conservative grouping combines earlier reference/text groups with vendor/product identity. It intentionally overmerges some products and may miss hidden aliases.
- Prior debug records and their conservative linked groups were excluded. Selection did not use model predictions.
- CNA/NVD agreement is source consistency, not independent validation. The semantic reviewer was an AI assistant, not an independent expert. This is a narrow convenience pilot, not a representative CTI-Bench dataset.
- The original 1,977-record external intake remains held; this release does not approve that entire pool for training.

[CVE copyright, complete license and notices](data/raw/cti-pilot-v1/NOTICE.md) accompany the derived data. Official CTI test data are not included.

## Model roles

The [pinned candidate metadata](configs/cti-candidates.lock.json) separates a strong public reference, Foundation-Sec-8B-Reasoning, from general models intended for adaptation: Qwen3-8B, Qwen3-14B and Qwen3.8-27B. The GPU runner defaults to Qwen3-14B as an exploratory starting point, not a finalized selection.

Qwen3.8-27B has 27,781,427,952 actual parameters despite its nominal 27B name. Its configuration uses `qwen3_5`; the model runtime requires newer Transformers support than the pinned FAITH grading environment. The two environments exchange JSON results.

The Cisco official Q4 model was hash-verified and run locally on authored examples. A 512-token output budget truncated many responses. Three selected failed cases completed with a 1,024-token budget; that selected follow-up is not an independent test and is not merged into the original cohort. See the [diagnostic summary](docs/verification/cti-local-checks-summary.json). None of these checks reproduces a published benchmark score.

## ABA integration evidence

Pinned ABA commit `c8bd734cafd5a7cd609efb5f561594bde4107d5b`, with the disclosed [one-line compatibility patch](patches/aba-nb-tree-no-request.patch), completed a synthetic bigram task. It performed 8,192 SGD updates, reducing frozen toy development NLL from 4.537171 to 0.768565. Independent reproduction matched weights within 1.8e-15.

The [result summary](results/aba-synthetic-validation.json) and [exact generated trainer](examples/aba-bigram/) are included. This verifies a controller/training/scoring/delivery chain. It does not establish LLM adaptation or cybersecurity performance. ABA has not yet been integrated with the CTI training task.

## Earlier engineering work

CyberGym neutral-input tool checks, VulnLLM-R-7B CPU inference, Feyospace BF16 inference and two synthetic QLoRA steps remain available as historical engineering evidence. Their limitations are documented in [status](docs/STATUS.md) and the earlier reports. They are not current CTI baselines or domain-training results.

## Next experiments

1. Verify the available GPU, CUDA runtime and disk capacity; choose and pin the actual model/protocol.
2. Run the unchanged pretrained checkpoint on the fixed external development file.
3. Run the bounded fixed-data SFT pilot and compare under the same inference settings.
4. Expand and review external training data; integrate the same task into ABA and compare against fixed-data SFT.
5. Use official testing only at predefined evaluation points, without feeding test content into tuning or data generation.

## Repository scope

This is a curated research snapshot, not a complete one-command benchmark reproduction. It contains code, selected results, authored integration examples and the explicitly licensed public CVE-derived pilot. It excludes credentials, private correspondence, account/cluster configuration, raw operational logs, other raw dataset pools and model tensors. See [Notices](NOTICE.md).

Upstream: [ABA](https://github.com/aibuildai-inc/aibuildai-llm-posttrain-agent), [CTI-Bench](https://github.com/maveryn/cti-bench), [FAITH](https://github.com/cisco-foundation-ai/faith), [CyberGym](https://github.com/sunblaze-ucb/cybergym).
