# Partial public development release

Only the 36 `dev_search` rows are released. The original manifest is preserved byte for byte so the frozen protocol and receipts retain their original hashes. Its 12-row `dev_confirm` entry is a provenance commitment; the file and full task recipe are intentionally withheld. Whole-manifest loaders and private data builders therefore cannot run from this checkout alone. Use `scripts/verify-kali-public-results.py` for public score replay. The older 36 confirmation rows in `kali-external-dev` were already public and are a separate dataset.
