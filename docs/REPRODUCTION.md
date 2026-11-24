# Reproduce the published scores

Run the commands below from the repository root. The two teacher-study checks use Python’s standard library and the released result records. They run offline on a CPU. Each check recomputes counts from recorded decisions. Repeating model training or executing every original evaluation would additionally require the private inputs and model artifacts.

## Recount the teacher experiments

| Study | Command | What to look for |
| --- | --- | --- |
| Second single-example replication | `python3 results/teacher-transfer-2026-11-23/verify.py` | 60 explanation reviews, 24 screening draws, 54 replication draws and nine checkpoint hashes. |
| Earlier eight-source transfer comparison | `python3 results/constraint-audit-2026-11-23/recount.py` | In the `all_prospective` result, base 23, answer-only 21, Qwen trajectory 18, DeepSeek trajectory 17, each out of 24. |

To redraw both figures for the second training example, install Matplotlib in your plotting environment and run `python3 results/teacher-transfer-2026-11-23/figures.py`. The script writes the two PNGs beside the published results. [Study design and figures](../results/teacher-transfer-2026-11-23/RESULT_ZH.md)

## Inspect earlier comparisons

- **Fixed SFT.** The [internal confirmation report](KALI_QWEN_UNQUERIED_CONFIRMATION_ZH_2026-10-28.md) explains the 87-example comparison. The [published summary](../results/kali-qwen-confirmation-2026-10-28/summary.json) and [verification script](../scripts/verify-kali-qwen-confirmation-public.py) provide the numbers and figure checks.
- **Native ABA.** The [experiment report](../results/kali-qwen-native-aba-2026-11-15/RESULT_ZH.md) records candidate selection, development criteria and confirmation. The [dependency audit](../results/kali-qwen-native-aba-2026-11-15/dependency-audit.json) identifies the public and private components.
- **Historical environments.** The [October reproduction notes](REPRODUCTION_OCTOBER.md) preserve version-specific instructions for the early benchmark, CPU, CUDA and synthetic ABA pilots. The [implementation guide](../scripts/README.md) points to the related code and fixtures.
