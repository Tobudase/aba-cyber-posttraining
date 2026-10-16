# Reproduction scope

This repository is a sanitized snapshot, not a one-command benchmark release. Configure `YOUR_NAMESPACE` and the `user-` Kubernetes name prefix before any cluster submission. Do not use an example manifest against a shared namespace without reviewing it.

## Local tools

Use Python 3.12. The tokenizer-only preparation/checks used Transformers 4.57.6. The successful Linux CPU run used PyTorch 2.8.0+cpu and the exact 27-package freeze in `configs/requirements-vulnllmr-cpu.lock.txt`. It is a CPU lock and must not be reused as a CUDA training lock.

The full runtime used 4 CPU, 48GiB RAM, 40GiB scratch and a 30-minute hard deadline. Full model weights are downloaded by revision from the public model repository and are not included here. INT8 conversion adds numerical differences; no BF16 equivalence is asserted.

## Source preparation

The data-audit scripts expect a fixed upstream VulnLLM-R source checkout under `.tools/sources/vulnllmr`, commit `5357371a2271df1048666220415a3bc937af5f9d`. Use a sparse checkout for source code and avoid retrieving official test contents for development. `prepare-vulnllmr.py` retrieves public model metadata/tokenizer files and a designated author train file. `audit-vulnllmr-training.py` audits 20 designated Python train files, validates LFS integrity and builds a draft manifest. Neither the original gated SecCodePLT data files nor official evaluation files are required for this audit.

Read source-specific terms before downloading/reusing data. The upstream train files contain human/test markers: exclude both marked records and linked code components. Identical code, AST/name-normalization proxies and inferred adjacent code-pair edges are conservative checks, not a proof of semantic independence.

## Local outputs required by scripts

Raw annotation JSONL, draft code manifests and Job ConfigMaps are not published because they contain third-party code or local operational details. Collection scripts regenerate these outputs in the user's local workspace. The CPU Job builder currently consumes the v2 local pilot annotation file; the curation script contains explicit evidence checks for the three reviewed pilot source IDs. They are pilot utilities, not generic dataset builders. Do not silently replace IDs or export unreviewed records as training-ready.

The result verifier expects the original collected local evidence under `docs/verification/`; this snapshot instead publishes selected summaries under `results/`. The evidence SHA256 in the summary identifies the original local artifact. To reproduce execution, regenerate inputs, inspect the bounded Job, run once, then collect its actual evidence with `collect-vulnllmr-evidence.py` and verify it. A script being present or a local summary being readable is not evidence that a new run succeeded.

## Feyospace metadata-only candidate check

With network access, run `python3 scripts/prepare-feyospace-metadata.py` to download only six pinned public metadata/tokenizer files into ignored `.tools/`. Install a tokenizer-capable Transformers environment, then run `python scripts/check-feyospace-preparation.py`. It verifies SHA256 and a benign chat/tool serialization example; no model tensors or benchmark tasks are used. The recorded local result is in `docs/verification/feyospace-preparation.json`. Its pinned lock deliberately marks license and full-model/GPU training unverified.

## Credentials and policy

Create your own cluster access and API credentials through the provider. Never commit tokens, kubeconfig, private keys, login exports or notebook URLs with tokens. Existing local credential-setup UI helpers and VM account configuration are not part of this snapshot.

Official testing stays separate from training, annotation, candidate filtering and tuning. Do not reuse cancelled CyberGym internal splits. New benchmark selection does not relax this rule.
