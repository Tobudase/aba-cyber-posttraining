# Paired seed replication and frozen transfer check — October25,2026

**The original retention recovery repeated under seed43, but the new transfer panel did not demonstrate an overall improvement over the base. Keep the original base as the formal default.** This updates the previous scoped format-mechanism finding; it does not revoke the verified counting-prefix intervention or imply that all task errors were fixed.

| Model | Old domain strict | Old retention strict | New transfer strict | Verified fixture passes | Not executed |
| --- | ---: | ---: | ---: | ---: | ---: |
| base | 2/36 | 52/72 | 8/24 | 10/24 | 2 |
| seed42_compact | 3/36 | 36/72 | 7/24 | 10/24 | 3 |
| seed42_newline | 5/36 | 54/72 | 8/24 | 10/24 | 2 |
| seed43_compact | 3/36 | 36/72 | 7/24 | 11/24 | 2 |
| seed43_newline | 4/36 | 54/72 | 8/24 | 10/24 | 2 |

The old seed42 primary rows are historical cached results, with three original-output controls per adapter rerun in this study. The original base108 primary responses were fully reproduced. Every model received24 fresh transfer queries. Verified fixture passes use the full24-row denominator; the separate last column is not executed, not an observed execution failure.

## Completed, bounded steps

1. Authored24 transfer tasks across eight readonly/offline CLI tools, then froze them before model calls. Full queries/commands had zero exact overlap with localTRAIN and exposeddev. Gold references passed24 Linux checks before inference. Tools/intents are related to existing tasks; authors knew earlier failures. This is a **purposive transfer panel, not independent expert or official validation**.
2. Starting fresh from the pinned base, trained compact/newline arms at seed43,128 steps each. Queries, canonical commands and original learning rate1e-5 stayed fixed. Both arms had identical initial LoRA parameter hashes and training-ID order. The numerical training AST changed only the shuffle seed42→43; initialization also used torchseed43. Compact/newline supervision remains3222/3374tokens, so loss weighting is not equalized.
3. Generated450 bounded single-example greedy predictions, including historical controls and transfer evaluations. Both new arms completed; no additional candidates, label changes or tuning from transfer outputs were allowed.
4. Reviewed all transfer argv. The144 postvalidation records include24 gold and120 model outputs: **133 commands were executed;11 capture-mode predictions were not executed**. Readonly `cat FILE | wc --lines` and `ls --block-size=1` were admitted after syntax review, without changing references, output predicates or strict scoring. No missing `-r` was inserted and no interface flag was removed from a model answer.

## What replicated and what did not

Seed42 retention was36→54/72; seed43 was also36→54/72. Old domain strict was3→5/36 under seed42 and3→4/36 under seed43. These are descriptive two-seed results on the same exposed, correlated development rows, not additional independent samples or a powered significance study.

On the new panel, both repaired models scored8/24strict and10/24verified fixture passes, equal to the base. The seed43compact control had11 verified passes. A new certificate query exposed omission of `-noout` in repaired/base answers; compact answers retained it. Wrong filename copying/quoting, incorrect jq selection and offline tcpdump arguments also remain. The narrow format repair therefore does **not** establish broad capability improvement.

All predeclared internal checks were not met: complete safe execution coverage was required, but some capture-mode outputs did not satisfy the offline-only review. Formal default remains the base. The new panel will not be reused as an allegedly untouched holdout after tuning on its failures. Independent validation remains outstanding; no larger training or official evaluation was started.

## Reusable opt-in fix

The new helper changes only eligible TRAIN targets, refuses original/existing-file overwrite and leaves queries, commands, inference and scoring unchanged:

```sh
python3 scripts/kali_target_envelope.py --input TRAIN.jsonl --output NEW_TRAIN.jsonl
```

Its128row output matched the actual frozen newline treatment hash; already-formatted rows are idempotent. Non-TRAIN/official-test records, multiple envelopes and multiline commands are rejected. Freeze new data/manifest hashes and repeat tokenizer boundary checks before using a transformed dataset. This helper implements the treatment, not guaranteed model gains or automatic adoption.

## Resource and publication scope

OneA6000 was used sequentially, with256 actual optimizer steps and a45-minute hard job limit. Owned GPU/CPU Jobs/Pods/ConfigMaps were removed and the CPUVM stopped. Whole-worker GPU utilization sampling averaged35.26%; the measurement is not namespace-wide utilization certification and does not justify idle compute to meet a target.

These are NF4/BF16, final-only aligned-prefix, greedy256 diagnostics; they do not reproduce official full-precision/thinking evaluation. OfficialTEST and old confirmation reads/queries were zero. The study was operator-fixed, not a new native ABA search cycle. Prior scientific records and raw scores remain unchanged.

Published: aggregates, selected numerical receipts, source-artifact hash commitments, helper and offline consistency verification. Excluded: raw predictions, new panel bodies, weights, credentials, private identifiers/endpoints and operational launchers. Public summaries cannot independently recompute unreleased predictions or reproduce private runtime provenance.

```sh
python3 scripts/verify-kali-seed43-publication.py
```

[Aggregates](../results/kali-seed43-replication-2026-10-25/summary.json) · [Numerical receipts](../results/kali-seed43-replication-2026-10-25/numerical-receipts.json) · [中文说明](KALI_SEED43_REPLICATION_ZH_2026-10-25.md)
