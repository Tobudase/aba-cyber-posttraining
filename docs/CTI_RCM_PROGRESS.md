# CTI-RCM preparation and evidence

Updated October 17, 2026. All results below are preparation or bounded engineering checks. No official CTI score or successful pretrained-model domain adaptation is claimed.

## Data preparation

A complete fixed NVD publication week contained 2,743 records; structural screening retained 1,977 candidates across 214 CWE labels. Those original candidates remain held. They are not redistributed here.

For a separate small pilot, 128 records were selected in fixed ID-hash order across eight classes, excluding all 556 prior debug/group-linked IDs. All 128 original CNA records were retrieved from CVEProject/cvelistV5 commit `11dcf9dc70eb616a6d4ee95a893a282748a64ed5`. Of those, 109 passed structural source-consistency checks.

An AI assistant semantically reviewed 83 descriptions: 69 were accepted as source-silver examples and 14 remained held. The others are not claimed as semantically reviewed. Examples of held issues include a crash without an explicit memory-write mechanism, a bounds-checked Go panic, and underflow/read chains with ambiguous root versus consequence labels. Agreement between CNA and NVD is not independent expert ground truth.

The released 63-row subset was selected without model predictions. A deterministic group assignment (seed 117) and per-class selection produced:

| CWE | Train | Development |
| --- | ---: | ---: |
| 787 | 5 | 2 |
| 125 | 6 | 2 |
| 502 | 6 | 2 |
| 78 | 6 | 2 |
| 918 | 6 | 2 |
| 89 | 6 | 2 |
| 22 | 6 | 2 |
| 79 | 6 | 2 |
| Total | 47 | 16 |

Grouping combines existing intake groups with conservative vendor/product identity to keep related SSSD, BoKS and Quay descriptions together. Broad vendor grouping may overmerge unrelated products; hidden aliases may still exist. No claim of perfect family independence is made. The 16-row development split is for engineering feedback, not final independent testing.

Descriptions are unchanged English CNA text with original source labels and source hashes. The manifest records the semantic decisions, source revision, groups, split hashes and licensing evidence. Complete CVE terms and copyright are retained next to the data. Official CTI test bodies were not loaded.

## Training-interface checks

The separate Mac training environment used Torch 2.8.0, Transformers 5.20.1, PEFT 0.21.2 and Accelerate 1.15.0. Dependency consistency passed.

The Qwen3.8 tokenizer renders the native chat template before explicit tokenization. The loader verifies data hashes, split/provenance flags, training eligibility and ID/group/description separation. All prompt tokens are masked from the loss; only the assistant target and ending tokens are supervised. Inputs exceeding the configured cap are rejected instead of silently truncated.

All 63 examples were packed successfully; maximum complete sequence length was 282 tokens. Two shortest training examples were used for two actual LoRA optimizer steps on a **random tiny Qwen3.5 architecture**. Four adapter tensors changed; save/reload reproduced final logits exactly. Development optimizer steps: zero. The two losses correspond to different examples and are not a learning curve. The tiny adapter is not compatible with the full 27B model and is not redistributed.

The six boundary checks test valid loading, altered content without matching hash, official-data flags, ineligible training rows, shared train/dev groups and shared descriptions. The [recorded training result](verification/cti-source-pilot-training-smoke.json) and [boundary result](verification/cti-pilot-boundary-checks.json) are included.

## Scoring and model evidence

FAITH commit `35e6a713108b7a6fe37ca14f5a9185b4b58a803a` is pinned without changing its grader. Twelve extraction/format edge cases passed. Unclosed reasoning is not treated as a final answer, and conflicting CWE identifiers do not receive relaxed credit.

The current pinned FAITH configuration drops ten duplicates from 1,000 raw RCM records, giving an expected denominator of 990. Equivalence to the historical paper protocol is unverified. Its five-trial published result has not been reproduced.

For context, [the Cisco technical report, Table 2](https://arxiv.org/html/2601.21051v1#S4.T2) reports Foundation-Sec-8B-Reasoning at 75.3±0.8%, Qwen3-14B at 61.2±0.5%, and Qwen3-8B at 54.2±0.8% for RCM. These are paper-reported results under that protocol, not this repository's measurements or a current global ranking. The Cisco model is a specialized reference; general Qwen models are adaptation candidates. The complete Cisco model is subject to its underlying Llama terms and Cisco notices, not simply a blanket Apache-2.0 characterization.

The official Cisco Q4 GGUF was fully hash-verified. After fixing duplicate BOS transport, a 24-mechanism authored diagnostic completed in 402.039 seconds, with 16 responses hitting a 512-token cap and 12 strict label matches. Three failures selected for a 1,024-token follow-up completed and matched; their results are kept separate. These easy authored examples cannot establish real-world accuracy, full-benchmark latency or a final output budget.

## Prepared GPU work

The real-weight GPU runner supports pinned Qwen3-8B, Qwen3-14B and Qwen3.8-27B metadata. It is limited to one exposed GPU, checks disk headroom and weight hashes, and refuses silent CPU/model fallback. It first saves a baseline, then allows bounded SFT only with matching model/data/prompt/precision/environment contracts. Default SFT: eight steps, with deterministic class-interleaved training order, followed by predictions on the same 16 development examples. Adapter save/reload is checked before evaluation.

The Linux CUDA dependency file is a candidate, not a verified GPU lock. The runner and separate FAITH JSON grading entry point passed syntax/CLI checks but have not been executed with actual pretrained weights in this CTI experiment. GPU memory limits in the code are conservative rejection conditions, not measured fit guarantees. Future outputs are external silver-label development agreement, not official benchmark results.

ABA–CTI integration and the formal pretrained-model comparison remain pending. The earlier synthetic ABA run proves the toy pipeline only. Official testing remains evaluation-only and must not influence data generation, training, early stopping or prompt selection.
