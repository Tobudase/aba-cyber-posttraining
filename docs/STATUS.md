## October 23: fixed document-data SFT — negative result

Completed a single frozen 108-step LoRA experiment on RedSage-K-SFT-GRPO (8B, local MLX affine4, M2 Pro/16GiB), using 108 source-silver rows across 55 correlated intent families. Matched inference used the SFT-aligned prefix without tool help.

| Authored development set | Original base | New adapter |
| --- | ---: | ---: |
| Domain Exact / option diagnostic | 6/36 | 5/36 |
| General CLI retention Exact / option diagnostic | 66/72 | 54/72 |

**Keep the original base; do not promote the adapter.** Domain Total rose from 73.41 to 76.45, but the frozen acceptance rule failed. The 12 retention regressions belong to two correlated tshark families. These are development engineering results, not official KaliBench scores or actual ABA results.

A preceding prefix control brought the earlier base and 20-step adapter to the same 66/72, so the older 61→62 comparison below is historical and does not establish training gains. Domain inference controls were native 4/36, aligned 6/36, and aligned with tool help 25/36; tool-help gains are inference assistance, not learning.

Read the [full report](KALI_DOC_SFT_REPORT_2026-10-23.md), [frozen comparison](verification/kali-doc-sft-v1-2026-10-22/comparison.json), and [public reproduction instructions](REPRODUCTION.md). Released: training data, 36 search-dev rows, scripts, predictions and receipts. New confirmation bodies and all tensors remain excluded. Actual ABA/CUDA integration and independent semantic validation are pending.

# Current status — October 22, 2026

Minhao owns KaliBench; the collaborator owns AthenaBench. The real local RedSage8B affine4 cycle completed:72externaldev E0 61/72 Exact →20continuedSFT optimizer steps→same72E1 62/72. NativeTotal93.75→93.52;5gains4regressions, no reliable improvement. Keep the base. Training changed16LoRA tensors, persistedadapter reload delta0, peakMetal5.72GB. Independent4case token/stream/replay audit passed.

Official BF16/5,000-test evaluation and true ABA domain integration remain pending; the local fixed SFT is not ABA. The36reservedconfirm examples remain unused. Linux compute admission is still blocked at the last resource check. No weights/adapters or account configuration are published. See [current Kali details](KALI_MLX_PILOT.md).

## Historical preparation snapshot

# Current status

Updated October 21, 2026. Current preparation covers AthenaBench and KaliBench, with eventual transfer to CyberGym. Models and experiment protocols remain provisional.

- Athena RCM: 161 train / 22 dev / 9 reserved confirmation source-silver records. The 22-row dev is byte-identical to the previous local version; 9 confirmation examples have not been queried. Confirmation covers only eight groups and four classes.
- Kali: 3,376 screened training rows from 3,504 originals; 128 holds statically triaged into 11 primary categories, none relabeled or promoted. Public external dev has 72 search / 36 confirmation examples across 18 authored families.
- Cisco 8B official Q4 local dev: native prefix 19/22 source-label matches; removing opening `<think>` 20/22, with two gains and one regression. The latter still generated closing `</think>` in 15/22 outputs, so this is not reasoning-disabled inference. Both private services were stopped; their logged local ports were independently confirmed closed.
- Random tiny Llama/Qwen optimizer and adapter reload checks passed; 23 targeted workspace tests passed. Neither is a formal 8B training result.
- Kali native scoring can ignore wrong option values; preserve official metrics and report a separate diagnostic. Published rankings have not been proven affected. Athena VSP requires output coverage reporting.
- Latest GPU admission check: October 21, 18:19 PDT. Authentication/Job permissions worked, but a server-side one-A100 dry run was rejected by `pods=0`. No actual GPU jobs were launched in this preparation.

Formal BF16 baselines, actual 8B domain SFT, ABA domain end-to-end execution and official Athena/Kali evaluation remain undone. Draft worker images and submission/private-evaluation interfaces still require Linux/CUDA validation. The current external Athena data covers only RCM, and both dev pools are small and biased. Official tests were not downloaded or used in this preparation.

See [current details](ATHENA_KALI_PROGRESS.md), [reproduction](REPRODUCTION.md) and [draft protocols](../configs/benchkit/).

## Historical October 17 status

Updated October 17, 2026. The candidate direction is CTI-Bench root-cause mapping, with a public specialized reference and general Qwen adaptation candidates. Final model and formal protocol are not frozen.

## Completed

- Public source-silver pilot: 47 train / 16 development rows, eight classes, source hashes, conservative group separation, semantic review decisions, complete CVE terms and copyright.
- Six data-boundary checks; native FAITH grading with twelve edge cases.
- Actual two-step LoRA check using pilot training rows on a random tiny architecture; adapter parameters changed and save/reload matched. No pretrained large-model training is implied.
- Cisco official Q4 file verified and used for authored template/output-budget diagnostics. These are not benchmark scores.
- Patched, pinned ABA completed a synthetic bigram training/scoring/delivery task; independent reproduction passed. This supersedes the earlier statement that ABA end-to-end had not run.
- GPU probe, pinned-weight baseline/SFT runner and separate native grading entry point prepared; GPU execution pending.

## Still required

Verify the actual GPU/runtime/disk, choose and freeze the research model and inference settings, run real pretrained baseline and fixed-data SFT, enlarge/review external data, integrate CTI with ABA, then perform official evaluation at predefined points. Official CTI test content has not been loaded for this preparation.

The original 1,977-record external intake remains held. Only the separate released source-silver pilot is eligible for the limited exploratory experiment. AI review is not expert gold; its development split is not independent final testing.

## Earlier evidence

CyberGym checks used fixed neutral input, not successful vulnerability solving. VulnLLM-R-7B CPU INT8 produced four structured outputs, two source-label matches, all predictions negative; generation constraints and short budgets limit interpretation. Feyospace BF16 benign inference and two synthetic NF4 QLoRA steps passed, but no domain training or published-score reproduction occurred. External CyberForge screening did not approve that data pool for training. The earlier SEC-bench/Gemma 31B alternative remains historical and exceeds the current nominal 27B model-class target.

See [CTI progress](CTI_RCM_PROGRESS.md), [reproduction](REPRODUCTION.md), and [ABA synthetic result](../results/aba-synthetic-validation.json).
