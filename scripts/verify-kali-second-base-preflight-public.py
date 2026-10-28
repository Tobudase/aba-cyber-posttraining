#!/usr/bin/env python3
"""Verify published second-base preflight aggregates and file integrity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen3-8b-second-base-2026-10-28"


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    assert manifest["schema"] == "kali.second-base-preflight.public.v1"
    for name, digest in manifest["file_sha256"].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    s = json.loads((OUT / "summary.json").read_text())
    assert s["status"] == "PASS_TOKENIZER_ONLY_SECOND_BASE_PREFLIGHT"
    assert s["model_id"] == "Qwen/Qwen3-8B" and s["train_rows"] == 240
    assert s["all_default_prompts_end_at_assistant_header"] is True
    assert s["all_default_prompts_end_at_open_think"] is False
    assert s["all_nonthinking_prompts_include_closed_empty_think"] is True
    assert s["all_proposed_nonthinking_targets_roundtrip"] is True
    assert s["prior_redsage_worker_direct_reuse_valid"] is False
    assert s["prior_redsage_input_hashes_direct_reuse_valid"] is False
    assert all(s[k] == 0 for k in ("model_calls", "new_optimizer_steps", "GPU_jobs",
                                  "DEV_rows_opened", "confirmation_rows_opened", "official_TEST_rows_opened"))
    assert s["model_weights_downloaded"] is False
    print(json.dumps({"status": "PASS_PUBLIC_SECOND_BASE_PREFLIGHT_AGGREGATES",
                      "train_tokenizer_checks": 240, "new_model_results": 0,
                      "private_rows_reproduced": False}))


if __name__ == "__main__":
    main()
