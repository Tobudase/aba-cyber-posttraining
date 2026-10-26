# Native-protocol KaliBench pilot — October 25, 2026

Completed one new native ABA baseline–post-training–evaluation cycle using the
original `RISys-Lab/RedSage-K-SFT-GRPO` learner (about 8.19B parameters). Actual optimizer steps: 42. The original numerical run passed native Setup, deterministic verifier and semantic
review before training. Its Finalizer initially delivered task inputs instead of the
required model files; an independent strict check rejected that delivery. A fresh
native controller replay used the cached 42-step result and a declared pre-Setup
zero-step baseline snapshot to complete verified four-file delivery. The replay
performed 0 new optimizer steps and allocated 0 new GPU jobs.
Official TEST queries: 0. CPU VM and owned GPU Jobs were stopped/removed.

| Matched BF16/native inference | Base |42-step candidate |
|---|---:|---:|
| New self-authored DEV exact argv |4/12|2/12|
| Already-exposed24 retention strict |13/24|13/24|

Post-hoc offline execution review found the two strict regressions are equivalent
OpenSSL option ordering. Each model has 4/12 fixture-verified passes, 9/12 commands
executed and 3/12 not executed after explicit review. Across gold+models: 36 records,
30 actual executions,6 not executed. This is an explanatory audit, not a changed
selection criterion; the strict gate below remains the original frozen rule.

Developer gate passed: **False**. Native-selected artifact:
**E0**. Formal research default remains the original base:
this tiny, utility-heavy synthetic pilot is not independent expert validation.

Family-held-out validation: Not queried: candidate failed the frozen developer gate. This protects the sealed panel.

## Why a fresh baseline was required

The model card's intended usage retains the native `<think>` generation prefix,
BF16,sampling temperature0.2 and8192 output tokens. Earlier format investigations
used NF4,final-only prompts,a removed `<think>` suffix and256 greedy tokens. Their
paired format effect remains valid within that diagnostic protocol.

On the same 24 exposed development tasks, the untrained base scores 8/24 strict with
the historical protocol and 13/24 with model-card-aligned Transformers usage.
Native exact is9/24 vs14/24. This is an inference configuration change, **not a
post-training gain**. Prompt,prefix,sampling,budget and precision changed together;
there is no single-factor causal claim or official vLLM leaderboard reproduction.
Three legacy controls matched exactly. Six matched native tasks score4/6 NF4 vs5/6 BF16.

All 30 native continuations contain extractable output but omit a closing think tag.
Official scoring accepts their output blocks. An initial local analyzer wrongly
imposed an extra closure gate; it was archived/corrected without regenerating outputs
or modifying the official scorer. Closing-think is reported only as a diagnostic.

## Data and supervision

The private self-authored corpus has 64 TRAIN, 12 DEV, and 12 sealed validation rows, with
8/4/4 disjoint intent/template families. Gold commands pass 88/88 Linux fixture
checks; 4 negative controls pass. Filename variants are correlated, author knew
earlier failures, and the set is not independently authored expert/official gold.

Collected 64 real BF16 TRAIN continuations and 12 DEV baseline responses, plus 3 exact
parity controls. Strict literal-argv filtering initially retained 25 rows; a declared
TRAIN-only revision admitted reviewed equivalent spellings through execution.
56 read-only model commands were reviewed/executed: 50 passed, 6 failed, and 8 others were not
executed. Eight passing PCAP commands omitted the query's explicitly required-n;
fixture settings had masked that constraint. They were excluded before GPU training.
The50-row native attempt was interrupted with **0 GPU jobs and 0 optimizer steps**;
the corrected isolated cycle used **42 rows, 6 families**, including hashing.

No responses,commands or reasoning were repaired/invented. Actual native prompt and
teacher continuation token IDs were retained. Only the output block+EOS receive
loss; prompt and pre-output generated text are context-only. There are 891 supervised
tokens,maximum 390 total tokens per sample. The teacher is the same original base; these
are correctness-filtered self-generated examples, not new solutions from a stronger
teacher. No literal final-command repetition was found in masked context (0/42). All 42 sequences were re-encoded identically;
negative guards reject DEV/official TEST,changed responses,assistant input,oversize
sequences and extra trailing content. The custom template ignores enable_thinking=False.

Training:one epoch, batch size 1, AdamW at 5e-6, weight decay 0, seed 42,NF4weights/BF16compute,
q/v all-layer LoRA rank16,alpha32,dropout0,max_sequence2048. BF16 base and BF16
base+adapter use the same native inference settings. Parameters changed and adapter
save/reload passed; see the released numerical receipt. Do not infer improvement
from decreasing TRAIN loss alone.

## ABA scope and evaluation discipline

Operator supplies the frozen data/scaffold; ABA orchestrates one fixed candidate.
There is no autonomous data-generation or hyperparameter-search claim. The agent
sees only TRAIN/client/base/README and a declared four-file zero-step baseline snapshot; DEV/validation gold,raw responses and credentials
stay host-side. Actual native Setup/verifier/reviewer pass before training is allowed.

Selection rule,declared before candidate results:DEV exact argv>4/12,exposed24strict
>= 13/24,no native output-format/truncation failures. Base/candidate use the same
pinned native command extractor. A closed-think requirement is not added. Validation
is queried once on both models only after the developer gate passes; no official TEST.

## Compute and reproducibility boundary

One GPU at a time;finite jobs,hard deadlines and automatic cleanup. Model staging
has substantial overhead. Whole-worker vs post-staging utilization are released
separately; the latter does not establish whole-allocation40% utilization.
CPU runtime installation was I/O-bound; this overhead is not model training.

This public release contains aggregate scores,numerical receipts and a generic
supervision helper. Raw private data,reasoning,weights,operational launchers and
cluster/account identifiers are excluded. The offline verifier checks byte hashes,
arithmetic and input guards; it does not regenerate the private experiment.

Run `python3 scripts/verify-kali-native-publication.py`.

Primary sources: [pinned model card](https://huggingface.co/RISys-Lab/RedSage-K-SFT-GRPO/blob/843e2e3096e7de68f5c35eb16238f4909f21695a/README.md),
[official prompts](https://github.com/RISys-Lab/KaliBench/blob/0b5bf54c9e343f94e113874b98ff5de815780328/src/prompt.py),
[official scorer](https://github.com/RISys-Lab/KaliBench/blob/0b5bf54c9e343f94e113874b98ff5de815780328/src/model_score.py).

Official SFT source has newline output-only labels; the released SFT-GRPO model card
enables native thinking at evaluation. These are different stages, not one contract.
