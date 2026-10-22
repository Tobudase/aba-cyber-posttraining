# AthenaBench / KaliBench preparation — October 21, 2026

The shared experiment is E0 (unchanged pretrained checkpoint), E1 (fixed SFT recipe), and E2 (ABA search, at most three candidates), using matched inference settings. External development data guides selection; official tests remain separate and the final-evaluation switch is disabled. These are draft protocols, not completed domain experiments.

## Data and isolation

Athena preparation currently covers **RCM only**. The released external CVE source-silver pilot has 161 training, 22 development and 9 reserved confirmation records. The previous 22-row development file remains byte-identical, SHA256 `b74ccf61d3d6b4a1d9a2e7494f32a3a5e422c0280b1594deb85c7e914d12c818`. Related new cases were held; exact duplicates were removed. Grouping uses known source groups, vendor/product/package identity, references, exact normalized text and high text overlap. This is heuristic and does not prove no hidden aliases, pretraining exposure or official benchmark overlap.

All 177 additional candidates have dispositions: 142 passed structural/source checks and had their full descriptions reviewed, yielding 133 accepted source-silver and 9 ambiguous holds; 35 failed structural/source checks. Source agreement and AI review are not independent expert adjudication. Accepted candidates do not directly equal new training rows because of grouping, duplicate removal and confirmation reservation. The 9 confirmation examples cover just four classes and eight groups, have not been model-queried, and are not a representative final test.

Kali's original 3,504 training examples were normalized locally without downloading the official 5,000-example test. Gold-command round trips were nonperfect on at least one component for 128 records, including 57 native Exact failures. Those records remain held; the screened pool has 3,376 rows. Static triage groups observed incompatibilities into 11 primary categories. It does not prove all 128 labels are incorrect. Raw official train/hold records are not redistributed here.

The public authored Kali dev has 72 search and 36 confirmation examples across 18 template families and nine basic tools. Six filename variants in a family are correlated. Documentation consistency is not independent expert gold, and this narrow read-only/defensive sample does not represent the full Kali tool space.

## Scoring findings

At Kali revision `0b5bf54c9e343f94e113874b98ff5de815780328`, the native scorer gives Exact=1 and Total=1 to `<output>head -n 99 notes.txt</output>` against gold `head -n 5 notes.txt`, with required value `5`. These commands were passed as strings, not executed. Preserve native metrics for comparability and separately report `strict_option_value_correct` on external dev; it is a diagnostic, not an official replacement or complete shell semantic validator. The impact on previously published model scores has not been established.

The pinned Athena VSP calculation can exclude invalid predictions and show an apparently perfect native score when all outputs are invalid. Report valid-output coverage and valid-only MAE explicitly. Six-task Combined must not be computed from an RCM-only subset.

## Actual local model experiment

Official Cisco Q4_K_M GGUF revision `4a04f7b19513ff9f672169b8fe4288000ab87b07`, SHA256 `7a61e41b1ca1b339d41caf3001ea7832469d866e7c52a23980a1e95cbf5cd58b`, ran locally on the same 22 external development cases with a 1,024-token response budget and 4,096-token context:

| Prefix | Source-label matches | Output tokens | Truncated cases |
| --- | --- | --- | --- |
| Native opening `<think>` | 19/22 | 9,938 | 0 |
| Opening `<think>` removed | 20/22 | 7,480 | 0 |

Two cases improved and one regressed. Removing the prefix did not reliably disable reasoning: 15/22 responses still included `</think>`. The native prefix remains the provisional main baseline; this small, previously exposed source-silver RCM set does not justify a six-task protocol change. Sequential runtime observations are not a controlled speed benchmark. Both private local services were stopped and their logged ports independently confirmed closed.

This is not an official Athena score, a BF16 baseline, a post-training comparison or proof of general performance improvement. No reserved confirmation or official test examples were queried.

## Engineering evidence and remaining work

Two random tiny architectures completed two optimizer steps each, changed adapter tensors, and reloaded with zero logit delta. The original workspace passed 23 targeted tests, including group separation, strict ID coverage, v3 frozen-dev preservation and train-only worker packages. Those checks require additional local audit inputs; they are not represented as a runnable full suite in this curated snapshot. Public-checkout checks are recorded separately.

Published protocols and runtime requirements are drafts. Worker images are not built/CUDA-validated, and ABA's controlled submission/private evaluation bridge has not run on either domain. A synthetic ABA bigram demonstration remains historical plumbing evidence only.

Next: restore permitted compute access; validate the Linux/CUDA image and CPU-prefetch pinned weights; run one-card 20-step smoke and measure throughput/memory; run matched E0/E1, validate the ABA bridge, then bounded E2. Confirm scoring objectives and task ownership with collaborators before locking the study. Freeze the full protocol and overlap audit before official evaluation. Resource access does not imply that all granted GPUs should run simultaneously.
