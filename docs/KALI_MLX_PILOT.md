# KaliBench: real local 8B baseline / continued-SFT cycle

October 22, 2026. Minhao's track is KaliBench. This local cycle uses official `RISys-Lab/RedSage-K-SFT-GRPO`, revision `843e2e3096e7de68f5c35eb16238f4909f21695a`. All four original BF16 shards (16,381,516,824 bytes total) matched the published Hugging Face LFS SHA256. They were lazily quantized on CPU into MLX affine4/group64. No third-party quantized checkpoint was substituted.

## What actually ran

- E0: unchanged quantized pretrained 8B model on all 72 external search-dev examples.
- E1: 20 real continued supervised optimizer updates on 20 deterministically sampled screened TRAIN records, then the same 72 development examples.
- Training: batch 1, LR 5e-5, rank 8, MLX scale 2, last four transformer layers q/v only, no dropout. Assistant-only loss; no fabricated reasoning targets. Sixteen LoRA tensors changed (425,984 trainable parameters); persisted-adapter reload logit delta was zero.
- Hardware: Apple M2 Pro, 16GiB unified memory; MLX 0.32.4 / mlx-lm 0.32.2. Training peak Metal memory was 5.72GB; E0/E1 inference peaks were 5.08/5.14GB. Processes exited normally; no persistent model service was created.
- Inference: same fixed strict unrestricted messages, native opening `<think>`, greedy, seed 42, at most 1,024 output tokens. No official tests, reserved confirmation examples, model API calls or dataset-command execution.

| Metric on the same external 72 rows | E0 | E1 |
| --- | ---: | ---: |
| Native Exact / option-value diagnostic matches | 61/72 (84.72%) | 62/72 (86.11%) |
| Native Total Score | 93.75 | 93.52 |
| Runtime failures / truncations | 0 / 0 | 0 / 0 |
| Complete output XML envelopes | 0/72 | 2/72 |

Five diagnostic outcomes improved and four regressed. The five gains canonicalize `cat FILE | head -n 5` into `head -n 5 FILE`; this is not proof that the earlier pipeline's output semantics were wrong. The four regressions drop `openssl` before `x509`. The `wc --chars` error remains. **Do not claim reliable improvement or promote the tiny adapter as the final model.** Native Total decreased, and the 72 rows are correlated variants in only 12 authored families.

The native scorer accepts a closing `</output>` without an opening tag, so its zero format-error rate does not mean strict XML compliance. XML coverage is reported separately. Four bounded replays compared raw generated token IDs decoded by the pinned tokenizer, streaming text, and original saved predictions; all matched. The sampled tag omissions and dropped tool prefix are model outputs, not serialization losses.

This checkpoint already saw the official 3,504 TRAIN examples. The screened pool contains 3,376 after holding 128 source/scorer mismatches. Continued exposure to 20 of those examples is not new-data adaptation. This is not official BF16 / temperature-0.2 / thinking-prompt / 8,192-output-token / 5,000-test evaluation, and it is **not ABA**. The 36 confirmation examples remain unused. Actual Linux ABA integration and the formal evaluation are pending.

## Recompute scores from published predictions

Restore pinned upstream code/resources using `scripts/restore-benchkit-sources.py --execute` under their original terms, and install the native scoring dependencies in an isolated environment (`cvss`, `python-dotenv`, `PyYAML`, `tqdm`; see candidate requirements). Then, from the repository root:

```sh
python scripts/analyze-kali-mlx-pilot.py --evidence-dir results/kali-mlx --output /tmp/kali-pilot-recomputed.json
```

This makes zero model calls, rechecks exact prediction hashes and ID coverage, and reconstructs all native/diagnostic scores from the released authored dev data. It does not require the unpublished adapter. The published text receipts are unchanged original bytes. Download/conversion receipts have their private absolute directory replaced by a project-relative directory; they explicitly record the original local receipt SHA256 and this redaction.

## Re-run the real model pilot on compatible Apple Silicon

Create a dedicated venv. The observed environment used `mlx==0.32.4`, `mlx-lm==0.32.2`, `transformers==5.20.1`; add the native scoring dependencies above. CUDA/bitsandbytes are not used by this local route. Read upstream terms; no model redistribution rights are inferred from download availability.

```sh
python scripts/restore-benchkit-sources.py --execute
python scripts/prepare-benchkit-data.py
python scripts/audit-benchkit-scorers.py
python scripts/screen-kali-train.py

python scripts/prepare-kali-mlx.py --stage download --execute
python scripts/prepare-kali-mlx.py --stage convert --execute

python scripts/run-kali-mlx-pilot.py --phase baseline --output docs/verification/kali-mlx-e0-2026-10-22 --execute
python scripts/run-kali-mlx-pilot.py --phase train --baseline docs/verification/kali-mlx-e0-2026-10-22 --output docs/verification/kali-mlx-e1-train-2026-10-22 --execute
python scripts/run-kali-mlx-pilot.py --phase post --baseline docs/verification/kali-mlx-e0-2026-10-22 --adapter docs/verification/kali-mlx-e1-train-2026-10-22/adapter --output docs/verification/kali-mlx-e1-dev-2026-10-22 --execute
python scripts/analyze-kali-mlx-pilot.py
```

Source restoration fetches TRAIN, not official tests or weights. The explicit model download is about 16.38GB; the preparation script requires at least 32GB free before downloading. Conversion refuses to overwrite an existing output. Use a new output directory for genuinely new experiments; do not overwrite completed receipts. Final-only SFT differs from the native thinking-generation prefix; format behavior must be validated, not silently assumed.

The first historical training process used no dev gradients; the current runner additionally avoids reading dev row bodies during the train phase. The planned ABA worker/private-judge boundary still requires a separate real integration test. Public metadata and results do not constitute a built GPU environment, merged adapter, final study protocol or paper-score reproduction. The official-evaluation configuration remains disabled in the draft.
