# Verified teacher SFT core snapshots

These are the actual training, decoding, exact adapter-loading, reference-equivalence and artifact-transport implementations used in this stage. retention_metric.py contains the unchanged host grading function without private file I/O. The source manifest records hashes.

Private questions, labels, teacher/student outputs, encoded training rows and operational credentials are not released. These snapshots therefore do not reproduce the reported aggregate numbers by themselves. Use your own authorized data matching the encoded JSON schema and a hash-verified original Qwen3-8B checkpoint. The paired experiment uses native reasoning_content formatting, prompt-masked causal CE, identical command exposure/order and fresh LoRA initialization; token count and compute are not equalized.

The resume runner validates the complete-batch prefix and replays the first batch exactly. If any output differs it discards the old prefix. Artifact transport uses numbered sub4KiB atomic frames with SHA256/gzip checks; incomplete or corrupt payloads are never accepted.
