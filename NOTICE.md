# Notices

This is a public research-work snapshot. No repository-wide license is granted by this snapshot. Third-party models, datasets, prompts, templates and upstream projects retain their own licenses and attribution requirements.

Model metadata reports Apache-2.0 for VulnLLM-R-7B. The upstream VulnLLM-R code repository uses MIT; its data derives from several sources with separate provenance. This repository does not redistribute model tensors. It includes only the explicitly identified small CVE-derived data pilot, with its separate terms and copyright; other raw third-party data are excluded. Upstream prompt literals may be fetched by preparation scripts; those source terms still apply.

The Qwen training-template artifacts under `configs/templates/` originated from the referenced Qwen/TRL sources; the accompanying `TRL-LICENSE.txt` is retained. Source revisions and URLs are recorded in configuration files. Do not infer that a model's or code repository's license covers every underlying dataset.

The CVE-derived pilot under `data/raw/cti-pilot-v1/` retains unchanged CNA descriptions, source labels and provenance. The complete CVE terms and MITRE copyright are in `CVE-TERMS.txt` with the accompanying `NOTICE.md`. These source terms govern the CVE material; no repository-wide license is implied.

The authored CTI integration fixture is synthetic and is not official benchmark data. FAITH source and model files are not vendored; restoration scripts retrieve pinned upstream content under its original terms. The ABA compatibility patch targets the pinned upstream revision recorded in `configs/aba-synthetic-source.lock.json`.

## October 21 Athena/Kali preparation

The external RCM examples under `data/benchkit/athena-v3/` are derived from public CVE CNA records, not from official Athena tests. Their complete CVE terms and source notice accompany the data. AI review does not create expert gold labels or verify every affected-version assertion.

The CLI development examples and fixture under `data/benchkit/kali-external-dev/` and `kali-fixture/` are authored examples checked against referenced primary tool documentation. They are not official KaliBench test records and do not confer licenses to upstream code or models. Original Kali training rows, raw hold records, third-party scorer sources and tokenizer files are not vendored. Scripts may restore exact pinned upstream artifacts for local research under their original terms; restored files remain ignored.

Result files describe the stated narrow experiments only. No model weights or adapter tensors are included. No repository-wide license or unrestricted model derivative redistribution permission is implied.
