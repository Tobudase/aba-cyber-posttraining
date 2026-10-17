# Current status

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
