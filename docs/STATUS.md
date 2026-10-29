# Current status — October 29, 2026

**October 29 update:** A publisher terminal-receipt text screen flagged 111/512 TRAIN rows for effect review, but these are not proven wrong labels. An exploratory 401-unique-row/512-step Qwen SFT completed; on the reused internal DEV128 it scored **39/128** strict versus **43/128** for the original adapter, with one versus zero post-SFT truncations. The screened set lost 43 tools. A preliminary source check of six discordant cases also questions the sole automatic gain for the screened adapter. Keep the original Qwen adapter as the stronger internal candidate and RedSage-K as the formal default. Human signoffs remain zero, and the independent-source validation set is still absent. [Full report](KALI_QWEN_RECEIPT_SCREEN_ZH_2026-10-29.md) · [Aggregate comparison](../results/kali-qwen-receipt-screen-2026-10-29/comparison.json).

The subsequent read-only [TRAIN512 audit](KALI_QWEN_TRAIN512_DATA_AUDIT_ZH_2026-10-28.md) verified frozen publisher provenance and target formatting, found 275 tools (165 represented by one training row), and created a private all-row review queue. This did not change the model, adapter, automatic scores, or formal default. Independently human-reviewed training labels remain **0/512**; the 13-case independent adjudication form is blank. A [next-experiment protocol draft](KALI_QWEN_NEXT_EXPERIMENT_PROTOCOL_DRAFT_ZH_2026-10-28.md) awaits source-separated data and review before any new GPU run.

The KaliBench track now has a completed Qwen3-8B fixed SFT and a separate, frozen internal confirmation. All data in these readouts came from **publisher-verified official TRAIN**, not official TEST. The 512-row, 512-step one-seed NF4 QLoRA study measured strict tool/option-value correctness **29/128 → 43/128** on initial internal DEV. On 87 previously unqueried, command-group-separated internal DEV rows, the same saved adapter measured **18/87 → 26/87** (nine gained, one lost). The 22 rows involving tools absent from TRAIN512 showed **5/22 → 5/22**. Three outputs newly hit the 512-token cap after SFT. One initial DEV prompt embedded its reference command; the 87-row primary confirmation contains none.

This is an internal development signal with publisher silver labels, one seed and no independent-source blind validation. It is **not** an official KaliBench leaderboard score, an ABA automated data-generation/search result, or a CyberGym transfer result. The original RedSage-K remains the formal default. The next scientific steps are independent semantic review of the 13 changed/truncated cases, a source-separated frozen holdout, and then a matched replication or ABA experiment if warranted. All owned confirmation GPU objects were cleaned. [Result figure](../results/kali-qwen-confirmation-2026-10-28/before-after.png) · [Chinese report](KALI_QWEN_UNQUERIED_CONFIRMATION_ZH_2026-10-28.md) · [Public aggregate](../results/kali-qwen-confirmation-2026-10-28/summary.json).

A subsequent **AI documentation review**, not independent human approval, found one disputed `lvmconfig` reference among the nine automatically scored gains and one ambiguous `hardlink` task. Excluding only the disputed reference gives 18/86 → 25/86 as a sensitivity result; the original automatic metric remains unchanged. [Aggregate source review](../results/kali-qwen-confirmation-2026-10-28/source-review-summary.json).

The dated sections below preserve earlier states and are superseded by this update.

## Historical CUDA/ABA preparation — October 23

See [latest preparation and blocker](KALI_CUDA_ABA_PREPARATION_2026-10-23.md). No new GPU allocation/results; ordinary quota admission restored, hardware scheduling unavailable during bounded attempts. Native config/bwrap preflight only; actual ABA domain cycle pending. All owned cycle resources cleaned and VM stopped.

## October 23: expanded data and frozen replay ablation completed

Expanded the domain pool to **156 source-silver rows / 80 correlated families**, added **32 independent-source general utility replay rows**, and verified all32 replay fixtures plus four selected semantic checks on Linux. Mandatory-option coverage gaps fell from34/36to12/36 in the exposed domain development set.

Two predeclared128-step LoRA arms started from the original RedSage-K8B base. Both used the same96-row domain core; control repeated32domain records, treatment replaced those32presentations with replay. Equal steps do not mean equal tokens or domain exposure.

| Matched development | Original base | Domain control | Domain + replay |
| --- | ---: | ---: | ---: |
| Domain Exact / option diagnostic |6/36|5/36|5/36|
| CLI retention Exact / option diagnostic |66/72|54/72|54/72|
| Retention native Total |97.22|89.63|80.37|

**Keep the original base.** Neither candidate passed the frozen rule; this replay did not solve the regression. These are exposed development results from manual local SFT. Actual ABA, fresh independent validation and official benchmark evaluation remain pending.

Read the [full ablation report](KALI_REPLAY_ABLATION_REPORT_2026-10-23.md) and [paired evidence](verification/kali-replay-v2/comparison.json). Nautilus now also passed a **real 20-step 8B NF4 LoRA runtime check on one L4**, including genuine parameter changes and adapter save/reload with zero logit difference. The finished job was cleaned up; this is training/persistence validation on two TRAIN records, not benchmark evaluation or actual ABA. Startup staging still needs optimization before repeated runs. The [resource report](KALI_RESOURCE_VALIDATION_2026-10-23.md) records the precise stage reached.

## October 23: fixed document-data SFT — negative result

Completed a single frozen 108-step LoRA experiment on RedSage-K-SFT-GRPO (8B, local MLX affine4, M2 Pro/16GiB), using 108 source-silver rows across 55 correlated intent families. Matched inference used the SFT-aligned prefix without tool help.

| Authored development set | Original base | New adapter |
| --- | ---: | ---: |
| Domain Exact / option diagnostic | 6/36 | 5/36 |
| General CLI retention Exact / option diagnostic | 66/72 | 54/72 |

**Keep the original base; do not promote the adapter.** Domain Total rose from 73.41 to 76.45, but the frozen acceptance rule failed. The 12 retention regressions belong to two correlated tshark families. These are development engineering results, not official KaliBench scores or actual ABA results.

A preceding prefix control brought the earlier base and 20-step adapter to the same 66/72, so the older 61→62 comparison below is historical and does not establish training gains. Domain inference controls were native 4/36, aligned 6/36, and aligned with tool help 25/36; tool-help gains are inference assistance, not learning.

Read the [full report](KALI_DOC_SFT_REPORT_2026-10-23.md), [frozen comparison](verification/kali-doc-sft-v1-2026-10-22/comparison.json), and [public reproduction instructions](REPRODUCTION.md). Released: training data, 36 search-dev rows, scripts, predictions and receipts. New confirmation bodies and all tensors remain excluded. Actual ABA/CUDA integration and independent semantic validation are pending.

## Historical status — October 22, 2026

Minhao owns KaliBench; the collaborator owns AthenaBench. The real local RedSage8B affine4 cycle completed:72externaldev E0 61/72 Exact →20continuedSFT optimizer steps→same72E1 62/72. NativeTotal93.75→93.52;5gains4regressions, no reliable improvement. Keep the base. Training changed16LoRA tensors, persistedadapter reload delta0, peakMetal5.72GB. Independent4case token/stream/replay audit passed.

Official BF16/5,000-test evaluation and true ABA domain integration remain pending; the local fixed SFT is not ABA. The36reservedconfirm examples remain unused. Linux compute admission is still blocked at the last resource check. No weights/adapters or account configuration are published. See [current Kali details](KALI_MLX_PILOT.md).

## Historical preparation snapshot

## Historical status — October 21, 2026

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
