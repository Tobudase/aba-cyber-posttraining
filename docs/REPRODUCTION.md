# Current entry point — October22 Kali pilot

See [Kali MLX pilot reproduction](KALI_MLX_PILOT.md) for the actual8B local run and score-only replay from published predictions. Formal BF16 and ABA runs are still pending. The earlier preparation instructions below remain useful but do not describe a completed ABA domain experiment.

# Reproduction scope

Updated October 21, 2026. Start with [Athena/Kali preparation](ATHENA_KALI_PROGRESS.md). This is a curated research snapshot, not a one-command reproduction of official benchmark results. Model weights, official tests, raw Kali training records, private operational logs and account configuration are excluded.

## Current Athena/Kali entry points

The source/tokenizer receipts are published; the upstream files themselves remain ignored. Restore the exact recorded bytes under their upstream terms:

```sh
python3 scripts/restore-benchkit-sources.py --execute
python3 scripts/restore-benchkit-sources.py
```

The second command verifies all hashes without downloads. This fetches code, scoring resources, tokenizer metadata, primary tool documentation and Kali TRAIN only; it fetches no official test examples or weight tensors. A changed unversioned documentation URL may fail its historical hash: obtain the original snapshot rather than accepting changed bytes. Model-card license fields are metadata, not blanket permission.

Inspect the released data without third-party scoring dependencies:

```sh
python3 scripts/benchkit-cli.py audit-data --dataset data/benchkit/athena-v3/manifest.json
python3 scripts/benchkit-cli.py audit-data --dataset data/benchkit/kali-external-dev/manifest.json
```

For scoring, use an isolated environment with the native scorer dependencies (`cvss`, `python-dotenv`, `PyYAML`, `tqdm`); the original grading environment used Transformers 4.57.6, while model training used 5.20.1. The candidate CUDA requirements are not a tested Linux lock. An example using YOUR completed predictions, with exactly the requested IDs:

```sh
python scripts/benchkit-cli.py score --dataset data/benchkit/athena-v3/manifest.json --split dev --predictions YOUR_PREDICTIONS.jsonl --output NEW_OUTPUT_DIRECTORY
```

`benchkit.py` checks hashes, ID coverage, group separation and runtime failures; commands are scored as strings, never executed. `train-benchkit.py` and `infer-benchkit.py` require explicit `--execute` and CUDA for actual large-model experiments. They use local caches only. `cache-benchkit-model.py --execute` is a separate CPU-only weight-download step, not run by source restoration. Do not hold GPUs idle while downloading.

Kali normalization/screening utilities are included, but rebuilding the entire local screening pipeline also requires the audit receipts generated in that local sequence. The full 23-test workspace audit is recorded as historical evidence, not claimed to be runnable from this curated snapshot. Public preparation checks are recorded separately in `results/publication-checks-2026-10-21.json`. No adapters, worker image or GPU training outcomes are packaged.

The sections below preserve historical October 17 instructions; CTI is no longer the primary experimental track.

## CTI pilot: no network or credentials required

Use Python 3.12 or later:

```sh
python3 scripts/verify-cti-pilot-boundaries.py
```

This loads the released 47/16 source-silver split and exercises six provenance/leakage guards. It does not load model weights or official tests. Read the data notice and complete CVE terms next to the examples.

## Restore pinned code and tokenizer metadata

```sh
python3 scripts/restore-cti-source.py
```

This fetches only the 249 explicitly allowed, hash-pinned public metadata/source files. It does not fetch official benchmark test bodies or model weight tensors. Upstream code and tokenizer licenses apply. `.tools/` stays ignored. Regenerating all original NVD/CNA intake snapshots is separate: the intake scripts require the recorded local source snapshots and grouping/exposure evidence, which are not all included. Re-querying a live database is not guaranteed to reproduce a historical snapshot; do not overwrite or silently change the frozen pilot hashes.

## Reproduce the tiny CPU training-interface check

On macOS, create a separate Python 3.12 venv and install `configs/requirements-cti-train-macos.lock.txt`, then run:

```sh
python scripts/test-cti-pilot-training.py
```

The Mac dependency lock is not a Linux/CUDA lock. This uses cached Qwen3.8 tokenizer metadata and a RANDOM TINY architecture, not pretrained 27B weights. It validates assistant-only masking, two actual updates on pilot train rows, changed adapter tensors and reload consistency. No performance improvement or benchmark score is implied. Runtime outputs go to ignored `artifacts/`; the tiny adapter cannot be applied to the full model.

## Pretrained GPU pilot: prepared, not yet GPU-validated

Check your authorized GPU environment without exposing account credentials:

```sh
python3 scripts/probe-cti-gpu.py
```

Create an isolated Linux environment using `configs/requirements-cti-gpu.candidate.txt`. Verify CUDA wheel/driver compatibility; this candidate file is not a proven complete lock. Do not replace a shared system Python. After verifying disk and GPU capacity, an example sequence is:

```sh
python scripts/run-cti-pretrained-pilot.py --model-key qwen14_model --phase baseline
python scripts/run-cti-pretrained-pilot.py --model-key qwen14_model --phase sft --steps 8
```

Default total timeout: 1,800 seconds per command, including public weight download/hash checks. Exactly one GPU must be exposed. Weights and local cache are not committed. The eight default steps cover the eight pilot classes in round-robin order. No official tests are read; only the fixed pilot train rows enter optimization. Matching baseline/data/prompt/precision/environment contracts are required before SFT. Failed/partial runs must not be reported as complete.

For native grading, create `.tools/cti-faith-venv` separately using `configs/requirements-cti-faith.lock.txt`. Its Transformers 4.57.6 is intentionally separate from the model runtime's 5.20.1:

```sh
.tools/cti-faith-venv/bin/python scripts/grade-cti-pretrained-pilot.py artifacts/cti-pretrained-pilot/qwen14_model/baseline.json
.tools/cti-faith-venv/bin/python scripts/grade-cti-pretrained-pilot.py artifacts/cti-pretrained-pilot/qwen14_model/sft.json
```

These outputs would measure external silver-label DEVELOPMENT agreement, not official CTI-Bench accuracy. The full formal evaluation and ABA–CTI integration have not run. The current FAITH configuration expects 990 records after ten duplicate drops; paper-protocol equivalence is unverified.

## Synthetic ABA evidence

The reviewed generated trainer and its training inputs are under `examples/aba-bigram/`. Running that trainer alone does not rerun the ABA controller. The public result summary records the successful pinned/patched ABA run and independent reproduction. It is a toy integration result, not an LLM/cybersecurity score.

## Historical reproduction notes


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
