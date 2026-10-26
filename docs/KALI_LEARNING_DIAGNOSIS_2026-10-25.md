# Kali learning diagnostic and corrections — 2026-10-25

Completed one fixed manual diagnostic, not another autonomous ABA search. Keep the original base as formal default. These are small exposed, self-authored development panels, not official KaliBench scores.

| Model / 模型 | BF16 DEV contract /12 | BF16 retention strict /24 |
| --- | ---: | ---: |
| Original base / 原底座 | 4 | 12 |
| Old 42-step adapter / 旧适配器 | 5 | not re-run |
| Matched style control / 格式对照 | 5 | 13 |
| Corrected-data mix / 纠错数据组 | 4 | 13 |

The old adapter retention was not re-generated in this job; the prior study reported13/24. New arms use a fresh same-card BF16 retention baseline. All old precision/DEV comparisons are freshly paired on the same actual GPU.

| Precision | Old TRAIN base NLL | Old adapter NLL | Relative change |
| --- | ---: | ---: | ---: |
| NF4 | 0.068622 | 0.036853 | -46.30% |
| BF16 | 0.011349 | 0.012900 | +13.67% |

The old optimizer reduces the actual NF4 TRAIN objective; BF16 does not show the same loss change. Absolute BF16 changes are small. Loss changes alone do not identify the cause of DEV behavior. The old objective conditions on masked generated context; the new empty-think objective has different conditions, so their absolute NLL values are not cross-objective capability scores.

Confirmed scorer defect: two literal-argv false negatives are reviewed OpenSSL option-order equivalents. Contract-v2 retrospectively gives4/12 for both old models; old frozen scores/gate remain unchanged. The contract is deliberately limited to reviewed synthetic commands and does not modify official metrics.

The same-card old adapter also scores5/12; style control therefore adds no DEV gain over it. Hardmix scores4/12, providing no evidence that this corrective data strategy fixes transfer. All four NF4 arms score7/12. Five reviewed Linux offline-PCAP executions confirm the one BF16 UDP-filter gain. Cross-allocation baseline reproduction is incomplete:7/24 response texts and3 commands differ, with one strict loss; matching three sampled controls does not establish full-panel reproducibility. No unique hardware/kernel cause is identified.

Both fresh arms use42 steps, identical fresh seed42 initialization, AdamW5e-6, batch1, q/v all-layer LoRA r16/alpha32/dropout0, NF4/BF16 compute, and identical completion serialization. Style control preserves the original42 already-correct queries/output blocks. Hardmix replaces the strategy with22 execution/constraint-verified existing TRAIN corrections and20 easy replay rows. This changes intents and token counts too; it cannot prove sample count is the unique cause. Both new encodings retain the native input template and supervise only structural empty-think closure, final verified output and EOS; no invented reasoning.

GPU: NVIDIA L4;84 new updates,174 new generations,0 external teacher calls,0 sealed-validation calls,0 official TEST calls. Owned GPU resources cleaned. The hosted-teacher attempt was rejected before execution and disabled; existing local execution-verified gold was used instead. Frozen narrative errata are disclosed separately, without rewriting protocol bytes or selection rules.

See the [Chinese analysis](KALI_LEARNING_DIAGNOSIS_ZH_2026-10-25.md), [aggregates](../results/kali-learning-diagnosis-2026-10-25/summary.json), [command contract](../scripts/kali_command_contract.py), and [opt-in training encoder](../scripts/kali_structural_completion.py). No raw model reasoning/prompts, tensors, credentials or cluster metadata are released. One seed and correlated exposed tasks do not establish generalization or an official ranking.

Run `python3 scripts/verify-kali-learning-publication.py` for public-byte/numeric checks and43 generic regression checks. This is not independent private-runtime or model-output reproduction.
