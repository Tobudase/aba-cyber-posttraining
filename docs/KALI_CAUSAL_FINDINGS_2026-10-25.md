# KaliBench causal investigation and recovery — October 25, 2026

A target-envelope training treatment recovered the observed retention regression. A subsequent **fixed-weight, bidirectional output-prefix intervention** identified a conditional generation-context mechanism for three correlated newline-counting variants. This is exposed development evidence, not an official benchmark score or independent generalization claim.

## Same primary development protocol

| Study | Domain strict /36 | Retention strict /72 |
| --- | ---: | ---: |
| Original base | 2 | 52 |
| Original V3 compact targets | 3 | 36 |
| Learning rate halved | 3 | 36 |
| Tool directives removed from 32 utility queries | 4 | 36 |
| Newline target envelope | **5** | **54** |

All new training candidates started from the original pinned RedSage-K checkpoint. These manual fixed-recipe cause studies are separate from the previously published native ABA execution. They do not demonstrate autonomous ABA data generation or a new native ABA search cycle. The historical V1/V3 records and scores remain unchanged.

## What changed in the positive training control

Only `target` changed in each of 128 TRAIN records: `<output>COMMAND</output>` became `<output>\nCOMMAND\n</output>`, with **real newline characters**. Queries, canonical commands, labels, fixtures, order, seed42, original learning rate1e-5, LoRA configuration, numerical training AST, inference and scorer stayed fixed. Exact field-level auditing confirmed this. Supervised tokens increased3222→3374 and full tokens52420→52572; token count and within-row mean-loss weighting were **not equalized**.

The study passed216 historical raw-response/token/per-row-score controls, completed128 optimizer steps and108 primary post-training predictions. All108 responses used newlines. The original18 new strict failures recovered: six genuine wrong filenames and twelve added `-n` cases. Only adding newlines to old V3 outputs, without training, still scores36/72. This excludes a direct whitespace-scoring explanation.

A separate CPU-only review performed579 fresh checks:288 original-command executions across reference/base/V3/new candidate,96 exact frame-ID checks on original/permuted synthetic PCAPs,192 newline-count edge cases and three routing-command forms. The new candidate passed all48 counting edge cases; V3 passed0/48. Fixed-fixture full-cohort passes were base58/72, V354/72 and new60/72. These fixture predicates are **not official scores, universal command equivalence or independent success estimates**. Packet tests disabled name resolution and used synthetic captures.

## Fixed parameters: can the prefix switch the same error?

Three already-exposed, correlated filename variants in one `wc` family;18 generations, zero optimization. Before interventions, three original outputs per model matched historical raw responses, generated token IDs and prompt hashes.

| Fixed weights | Original free generation | Opening tag supplied | Opening tag + newline supplied |
| --- | ---: | ---: | ---: |
| Original base | 3/3 correct | **0/3** | **3/3** |
| Unchanged original V3 | 0/3 correct | **0/3** | **3/3** |

The original base with the compact opening reproduced the same wrong-file pipeline as V3. V3 with the newline opening reproduced the same correct counting command as the base. Another108 fresh Linux fixture checks confirmed the execution outcomes, inspecting every pipeline stage; a downstream `wc` exit0 does not hide a failed upstream file read.

With the pinned tokenizer, the supplied prefixes encode as `[27,3006,29]` and `[27,3006,397]`. The original prompt token prefix is unchanged. The terminal token is `>` versus `>` combined with a newline, so the command starts in a different token context. These are **operator-supplied tokens**, not freely generated output. Supplying only the opening tag does not prohibit a generated newline; in these observed cases both models chose compact continuations.

This bidirectional intervention supports a direct context-dependent generation path for the tested counting errors. It does not prove that the same prefix mechanism explains DNS/TLS, quantify all training-loss contributions, or establish a universal root cause. The training treatment also changes supervised-token count and loss allocation.

## Decision and publication boundary

The newline-target candidate passes the exposed development gate. **Keep the original base as the formal default pending independent replication and validation.** Independent validation is not complete. Official TEST and old confirmation reads/queries were zero in these studies; modified-prefix results never replace original primary scores.

GPU/CPU jobs were finite and cleaned, and the CPU VM was stopped. Short-probe GPU utilization remained low; the measured means in the summary are not certification of the40% utilization target or of namespace-wide compliance.

Published: aggregate findings, selected numerical receipt fields, source-artifact hash commitments and an offline consistency verifier. Excluded: raw predictions, new dataset bodies, weights, credentials, internal cluster identifiers/endpoints and operational launchers. The public verifier cannot independently reproduce undisclosed runtime artifacts or recompute private prediction scores.

```sh
python3 scripts/verify-kali-causal-findings.py
```

[Aggregate evidence](../results/kali-causal-findings-2026-10-25/summary.json) · [Numerical receipts](../results/kali-causal-findings-2026-10-25/numerical-receipts.json) · [中文说明](KALI_CAUSAL_FINDINGS_ZH_2026-10-25.md)
