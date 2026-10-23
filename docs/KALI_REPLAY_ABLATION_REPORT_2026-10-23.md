# KaliBench second-round ablation and Linux validation — October 23, 2026

Keep the original base; neither adapter passes the frozen acceptance rule.

## Completed data and semantic work

- Domain training pool:156 rows / 80 correlated intent families, expanded from108 rows / 55 families. Six proposed overlapping operation families were excluded before training. Query/command exact and protected operation-signature overlap remain zero; this does not prove semantic or pretraining independence.
- Independent-source general utility replay:32 authored records / 16 families grounded in pinned GNU Coreutils documentation. All 32 executable fixtures passed on Linux. Replay tools do not overlap the authored development/confirmation tool names. The rows retain their creation-time quality label; later Linux verification is in the separate hash-linked receipt.
- Mandatory per-tool option coverage improved:34/36 domain queries had missing flags inV1, versus 12/36 with V2 (also 12/36 in the selected 96-row domain core). This is lexical coverage, not evidence of learning or comprehensive tool coverage.
- Four fixed Linux fixture checks passed: tshark quiet mode suppresses packet output; editcap retains the selected packet range; YARA expects rules before target; netstat accepts the unique long-option abbreviation in this installed version. `pescan` exists and `pe-scan` does not in the installed package; that executable-name check is not fullPE semantic validation.
- Linux package versions differ from the pinned upstream Kali help snapshots. Native gold and scorer were not changed; no additional matches were silently credited.

## Frozen matched experiment

Original RedSage-K-SFT-GRPO 8B, revision 843e2e3096e7de68f5c35eb16238f4909f21695a, local MLX affine4/group64, Apple M2 Pro, 16 GiB. Each arm starts from the same original base. Same LoRA (last 4 layers, q/v, rank 8, scale 2), LR 1e-5, batch 1, seed 42, assistant-only final-answer supervision, greedy 1,024-token evaluation without tool help.

Both arms have 128 optimizer steps. The shared core contains 96 rows covering all 80 domain families. Control adds 32 repeated domain presentations; treatment replaces those 32 presentations with the independent utility replay. This equal-step comparison does **not** equalize token/FLOP budgets or total domain exposure, and cannot isolate a pure added-data effect. The two arm protocols and runner hashes were frozen before either run. No third candidate was tried based on these results.

| Same exposed development | Original base | Domain control | Domain + replay |
| --- | ---: | ---: | ---: |
| Domain Exact / option diagnostic |6/36|5/36|5/36|
| Domain native Total |73.41|75.95|76.23|
| CLI retention Exact / option diagnostic |66/72|54/72|54/72|
| Retention native Total |97.22|89.63|80.37|
| Frozen rule passed |baseline|False|False|

The original 72 CLI rows have repeated template variants; individual rows are not independent skills. The 36 domain rows are source-silver and already exposed during diagnosis. No statistical significance, full-benchmark generalization or independent label-review claim is made. The fixed rule requires improved domain Exact and option matching, nondecreasing domain Total and retention, and no runtime/truncation/XML failures.

## Interpretation and remaining work

Both arms have zero new exact/option matches and the same 13 regressions: one `pescan`→`pe-scan` query and 12 correlated tshark DNS/TLS cases adding `-q`. See `verification/kali-replay-v2/error-family-review.json`. The independent-utility replay deliberately excluded tshark, so this result does not show that every kind of replay is ineffective. Compare both arms to the original base and disclose failures. A reduction in regression relative to the domain control would not by itself justify promotion if the base is still better. Better data coverage has not automatically established successful adaptation. Whole-domain semantic validation, fresh held-out development, multi-seed confirmation and actual ABA-controlled training/evaluation remain separate tasks. New confirmation bodies and official tests remain unqueried.

This round is **manual SFT**, not actual ABA. A train-only 128-row Linux worker package is prepared and checked; the CUDA recipe(NF4 / rank 16 / all q-v layers) differs from MLX, so it requires its own matched baseline/protocol. The realABA controller, private evaluator isolation and controlled submission need end-to-end validation before search is enabled.

## Evidence and score replay

- `verification/kali-replay-v2/comparison.json`: both arms and predeclared decision.
- `verification/kali-replay-v2/<arm>/`: exact executed runner/protocol, raw predictions, scores and training receipts. Tensors are private.
- `verification/kali-v2-option-coverage.json`: descriptive flag coverage.
- `verification/kali-linux-semantics-2026-10-23.json` and `kali-replay-fixtures-2026-10-23.json`: actual Linux execution evidence.
- `configs/kali-replay-v2-*.protocol.json`: frozen protocol hashes, protected-data commitments, budgets.
- After restoring the pinned sources: `python scripts/analyze-kali-replay-ablation-v2.py` recomputes public scores. `--verify-local-adapters` additionally checks private tensors and only works in the original workspace.
- Original workspace: 42 tests passed with its audit dependencies; curated public suite passed 15 tests. Recorded GPU/runtime progress is in the accompanying resource report.
