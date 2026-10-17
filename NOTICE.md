# Notices

This is a public research-work snapshot. No repository-wide license is granted by this snapshot. Third-party models, datasets, prompts, templates and upstream projects retain their own licenses and attribution requirements.

Model metadata reports Apache-2.0 for VulnLLM-R-7B. The upstream VulnLLM-R code repository uses MIT; its data derives from several sources with separate provenance. This repository does not redistribute model tensors. It includes only the explicitly identified small CVE-derived data pilot, with its separate terms and copyright; other raw third-party data are excluded. Upstream prompt literals may be fetched by preparation scripts; those source terms still apply.

The Qwen training-template artifacts under `configs/templates/` originated from the referenced Qwen/TRL sources; the accompanying `TRL-LICENSE.txt` is retained. Source revisions and URLs are recorded in configuration files. Do not infer that a model's or code repository's license covers every underlying dataset.

The CVE-derived pilot under `data/raw/cti-pilot-v1/` retains unchanged CNA descriptions, source labels and provenance. The complete CVE terms and MITRE copyright are in `CVE-TERMS.txt` with the accompanying `NOTICE.md`. These source terms govern the CVE material; no repository-wide license is implied.

The authored CTI integration fixture is synthetic and is not official benchmark data. FAITH source and model files are not vendored; restoration scripts retrieve pinned upstream content under its original terms. The ABA compatibility patch targets the pinned upstream revision recorded in `configs/aba-synthetic-source.lock.json`.
