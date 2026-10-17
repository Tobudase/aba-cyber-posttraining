# ABA Cybersecurity Post-training Research

Research code, a small source-traceable data pilot, and engineering evidence for using an ABA agent to adapt an open-weight language model on cybersecurity tasks.

**Updated October 17, 2026:** the current candidate task is **CTI-Bench root-cause mapping (CTI-RCM)**: classify a vulnerability description into a CWE identifier. Final model selection and the formal evaluation protocol remain open. The real pretrained-model GPU baseline, domain SFT, ABA–CTI integration and official CTI evaluation have **not** run.

## Latest verified progress

| Component | Actual result | Scope |
| --- | --- | --- |
| External pilot data | 47 train / 16 development records, eight CWE classes, frozen hashes and conservative group separation | Assistant-reviewed source-silver labels, not independent expert gold |
| Training-data checks | Six boundary checks passed; assistant-only loss masks and explicit truncation rejection | Data and training-interface checks |
| Local LoRA check | Two real optimizer steps on actual pilot training rows; four adapter tensors changed; save/reload maximum logit difference 0 | **Random tiny architecture**, not pretrained 27B weights |
| Native CTI grading | 12 edge cases passed using pinned, unchanged FAITH extraction and aggregation | No official test records loaded |
| ABA end-to-end integration | Generated and executed a toy trainer, scored it, delivered artifacts, independently reproduced the result | Synthetic eight-token bigram task, not an LLM or cybersecurity result |
| Pretrained GPU runner | Pinned NF4 baseline → bounded SFT → development predictions → separate native grading | Code prepared; actual GPU execution pending |

See [CTI progress and limitations](docs/CTI_RCM_PROGRESS.md), [current status](docs/STATUS.md), and [reproduction instructions](docs/REPRODUCTION.md).

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
