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
