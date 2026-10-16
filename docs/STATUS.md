# Current status

NRP documents an Anthropic-compatible `/anthropic` endpoint for Claude Code. Bounded neutral probes of `qwen3-small` and `qwen3` passed streamed text, tool-use content blocks and tool-result follow-up. Both returned `end_turn` rather than `tool_use` as the tool-call stop reason. Actual Claude SDK execution and ABA end-to-end use remain untested; see [compatibility report](ABA_NRP_COMPAT.md).

The main research objective is ABA-managed post-training of a good-performing, accessible model on a suitable cybersecurity benchmark. Model and benchmark selection remain open.

Feyospace-v1.1-small is pinned as a public-weight, high-scoring candidate. Six public configuration/tokenizer/processor files passed hash and benign chat/tool-template checks. The full BF16 checkpoint then loaded on an A100-80GB and generated a benign short response. A later two-step synthetic NF4 QLoRA check on the actual weights passed adapter save/reload consistency. No domain training or official evaluation has run. The public checkpoint repository still has no explicit license; see [candidate preparation](FEYOSPACE_MODEL_PREPARATION.md), [GPU validation](FEYOSPACE_GPU_VALIDATION.md), and [synthetic QLoRA result](../results/feyospace-qlora-synthetic.json).

The completed full-model validation uses VulnLLM-R-7B, CPU dynamic INT8 and a fixed output grammar. All 15 consistency checks passed. The four development predictions were all negative: two matched source labels and two did not. Format validity is imposed by decoding, not proof of unconstrained instruction following or benchmark capability.

GPU attempts were not scheduled. CPU BF16 loaded but generation was slow without native BF16 support. An initial 24GiB INT8 attempt experienced memory pressure. Increasing to 48GiB and releasing temporary memory allowed complete generation. The 32-token free-output attempt did not produce parseable answers; the final grammar-constrained test did. These limitations are retained in the result summary.

Training-source audit: 2,562 Python records, 1,281 per class; 106 human/test-marked records. Conservative component grouping quarantined 934 records; remaining draft proposals are 1,305 train and 323 validation. Exact duplicates and 934 inferred vulnerable/patched pair edges do not cross draft partitions. Original generation-family identity is incomplete, so semantic independence is not established.

Annotation pilot: 12 requests, 1,382 completion tokens; 9 quarantined after source/format checks, 3 candidates. Brief explanations were reviewed and corrected by an agent, not independently by a human. All remain ineligible for training pending a finalized protocol and source/quality review. No optimizer step on domain data has occurred.
