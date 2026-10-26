# Stepwise SFT progress — 2026-10-26

Completed a real TRAIN-recall diagnostic and two controlled 8B microfit arms. The predeclared training-sanity gate failed, so the new 240-row SFT and new ABA search have not started. Keep the original base. These are exposed TRAIN diagnostics, not official KaliBench or generalization results.

Existing-adapter recall on the same L4: NF4 corrections 4/22→5/22; BF16 corrections 3/22→1/22; easy replay 20/20 unchanged in both precisions. The new diagnostic uses greedy decoding and is not directly comparable to earlier sampled DEV scores.

Two fresh microfit arms used the same eight failed TRAIN examples, initialization, order and 128 updates each. Base NF4/BF16 correctness is 0/8 and 2/8. At 5e-6, correctness is 4/8 and 0/8; at 2e-5 it is 0/8 and 5/8, with three additional BF16 alternatives unsupported by the limited contract. The higher-rate NF4 arm emits newline then EOS for every row despite a 92% TRAIN NLL reduction. Both arms have finite nonzero gradients, 144 changed tensors and zero adapter reload logit delta. No posthoc gate relaxation or automatic model promotion.

The new authored curriculum has 240 TRAIN / 72 DEV / 72 withheld confirmation rows, covering 40/12/12 intent groups. All 384 gold commands and 448 negative checks passed Linux execution with separately implemented Python expectations. Six variants per intent are correlated; independent human review remains absent. All 240 TRAIN encodings passed native-template/mask/EOS checks: 6624 supervised tokens,maximum 375 sequence tokens. Empty-think/final-answer supervision remains an experimental choice, not a proven optimal target mode.

Released: original synthetic TRAIN/DEV, eight byte-matched audited input fixtures, a strict shared SFT recipe consumer, a native TRAIN encoder, local-weight-only training CLI, configurations and aggregate receipts. The shared optimizer also passed a real 16-step tiny CPU test and 11 rejection guards. The toy test is not pretrained 8B training or a cybersecurity gain.

Fixed-weight runtime/prefix controls were prepared, but two ordinary scheduling attempts received no allocation within their three-minute and ten-minute bounds. Both were cleaned, so no prefix-diagnostic model result is claimed. Next, resolve the failed training-sanity check using these controls. Only then run matched fixed-data SFT; confirmation and ABA comparison require their separate predeclared gates. Unknown commands are not executed. The conservative DEV gate bounds unsupported baseline alternatives rather than assuming they are all wrong.

See the [Chinese report](KALI_SFT_PROGRESS_ZH_2026-10-26.md), [data](../data/benchkit/kali-verified-sft-v1/README.md), [stage status](../results/kali-sft-progress-2026-10-26/stage-status.json) and [prefix diagnostic status](../results/kali-sft-progress-2026-10-26/prefix-probe-status.json). Full task/fixture generation is withheld while confirmation is protected; public checks do not independently reproduce the complete protected audit. No old private trajectories, model reasoning, encoded tokens, tensors, credentials or cluster metadata are released. No official TEST, old sealed validation, new confirmation or external teacher calls.

Check with `python3 scripts/verify-kali-sft-progress.py`. This verifies released-byte and numeric consistency, not private model-output reproduction.
