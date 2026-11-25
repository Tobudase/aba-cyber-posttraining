# ABA post-training on KaliBench

[中文项目导览](docs/README.md) · [Results by topic](results/README.md) · [Experiment log](EXPERIMENT_LOG.md) · [Reproduce the scores](docs/REPRODUCTION.md)

Can post-training help a small open-weight model solve new cybersecurity-related command-line tasks while retaining the tasks it already solves? We studied Qwen3-8B on KaliBench through fixed supervised fine-tuning (SFT), automated candidate training with ABA, and SFT on teacher demonstrations.

**Current decision: retain the original Qwen3-8B.** Fixed SFT improved one internal development set. ABA candidates missed the retention criteria, and teacher demonstrations produced mixed transfer. All scores below are internal. The official KaliBench test set remains sealed.

On 24 new offline utility tasks, the base, ABA-selected checkpoint and fixed continuation scored **2/24, 4/24 and 3/24**. Both trained checkpoints lost one previously correct retention item. [Five-model confirmation and blind teacher comparison](results/offline-utility-confirmation-2026-11-25/RESULT_ZH.md)

## What the experiments found

| Research question | Finding | Read the study |
| --- | --- | --- |
| Can fixed SFT help? | Strict correctness rose from **18/87 to 26/87** on previously unqueried examples. For tools absent from training it stayed at **5/22**. | [Baseline and error analysis](docs/KALI_QWEN_UNQUERIED_CONFIRMATION_ZH_2026-10-28.md) |
| Can ABA select a better checkpoint? | ABA trained and scored two candidates. Both candidates and the fixed SFT control missed at least one requirement for retaining old capabilities or returning complete answers. | [Selection and confirmation](results/kali-qwen-native-aba-2026-11-15/RESULT_ZH.md) |
| Do teacher trajectories transfer? | Across eight prospectively selected sources, the base passed **23/24** sampled responses, answer-only SFT **21/24**, Qwen trajectory SFT **18/24**, and DeepSeek trajectory SFT **17/24**. | [Paired scores on eight sources](results/constraint-audit-2026-11-23/RESULT_ZH.md) |

The studies use different tasks and denominators. Comparisons are paired **within** a study. Three decoding attempts on each of eight sources yield 24 responses.

## What the student actually learned

On a second training example, the original model selected the right option to list functions or global variables on every attempt, but omitted the program name each time. Both answer-only and Qwen trajectory SFT repaired all eight responses. The Qwen trajectory group also retained performance on a separate bitcode-partitioning task where answer-only SFT failed both attempts.

![Strict passes out of two per prompt. Answer-only and Qwen trajectory SFT passed all four same-source conditions. Qwen trajectory SFT also retained both separate tasks.](results/teacher-transfer-2026-11-23/second-source-transfer.png)

The four columns on the left share one training source. The two on the right are separate TRAIN tasks. Each cell shows two decoding attempts from one model, with one training seed per trained model. Both teacher-trained students reproduced their demonstrations on the original prompt. [Study report and limitations](results/teacher-transfer-2026-11-23/RESULT_ZH.md) · [Per-response scores](results/teacher-transfer-2026-11-23/second-source-sft.json)

**Open question.** Would teacher reasoning help on a broader set where the student repeatedly chooses the wrong operation? Three of 64 screened sources qualify for a planned study requiring eight sources across three skills. [Screening record](results/teacher-transfer-2026-11-23/evidence.json)

## Explore the repository

- **Find a result or figure.** The [results catalogue](results/README.md) groups the studies by research question. The [experiment log](EXPERIMENT_LOG.md) preserves the original dated accounts, including negative results and corrections.
- **Understand a method or reproduce a score.** The [documentation guide](docs/README.md) connects reports to code, data and configurations. The [reproduction guide](docs/REPRODUCTION.md) starts with offline score checks.
- **Review the earlier benchmarks.** The [benchmark pilots](docs/log/benchmark-pilots.md) cover CyberGym engineering checks and the CTI-Bench and AthenaBench preparation work. [Data and source notices](NOTICE.md)
