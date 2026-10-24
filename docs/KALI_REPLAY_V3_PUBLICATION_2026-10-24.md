# V3 public numerical release — 2026-10-24

Run locally without GPU or network:

```sh
python3 scripts/verify-kali-cuda-publication.py
python3 scripts/verify-kali-replay-v3-publication.py
```

The first command checks V1; the second checks V3 release-file integrity, frozen protocol and unchanged numerical worker hashes, receipt cross-references, 128 real optimizer-step records, native host-verification conclusions, the unchanged adoption rule, and recorded cleanup. These checks validate consistency of published evidence. They do not independently recompute scores or reproduce private native artifacts, training data order, model weights or raw predictions.

## Published scope

New files include a sanitized Chinese report, byte-identical frozen V3 protocol, aggregate comparisons, numerical receipt excerpts, and selected semantic/data-use/cleanup conclusions. The only generic runtime code change adds the required `frozen_adoption_gate` / `max` metric contract to operator scaffold provenance, with a regression assertion. Raw cluster/runtime logs, internal identifiers/endpoints, credentials, predictions, new training/evaluation bodies and weights are excluded.

One zero-update native control attempt used the wrong metric name. The host guard refused training. A fresh Setup received an explicit literal metric contract and completed one actual optimization candidate within the original global deadline. Guards, scoring and the frozen numerical worker were not relaxed.

## V1 history and current-tree manifest

The original V1 manifest from commit `20deb24f68fd29065e65eaf6936ae0ceda05ccc8` is retained verbatim as `results/kali-cuda-2026-10-24/publication-manifest.at-20deb24.json`. The current-tree V1 manifest refreshes hashes only for README, the scaffold and its test, and records the archived manifest hash. All V1 scientific artifacts and its numerical verifier are unchanged. This maintenance refresh is not a new V1 experiment or retrospective revision of results.

The V3 protocol retains an inherited `allocation_revision` scheduling-history field mentioning RTX4090. It is not the V3 allocation: frozen `GPU_model` and all executed phase receipts specify RTX A6000. Preserving the frozen bytes keeps the original pre-execution hash verifiable.

## Interpretation

Domain strict correctness 2/36 → 3/36 and retention 52/72 → 36/72 fail the adoption rule. V3 does not improve these strict counts over V1. All 72 extracted retention commands match V1, although the new data, loss sequence and adapter hash differ. Keep the original base. This is one seed on already exposed source-silver development data; official TEST and old confirmation queries remain zero. Data and token budgets differ as disclosed in `study-checks.json`.

Post-staging GPU means are approximately 16.4% / 62.0% / 19.7% for baseline / training / post-evaluation. Sampling includes model loading and excludes earlier staging. This does not establish whole-allocation utilization or compliance with the >40% GPU utilization target. Optimize staging/batching with paired output checks before further repeated GPU runs. Recorded cleanup confirms owned GPU jobs removed and CPU VM stopped.
