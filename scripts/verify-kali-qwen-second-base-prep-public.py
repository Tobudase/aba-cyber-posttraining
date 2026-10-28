#!/usr/bin/env python3
"""Check Qwen second-base TRAIN preparation aggregates and release integrity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-second-base-prep-2026-10-28"


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    assert manifest["schema"] == "kali.qwen.second-base-prep.public.v1"
    for name, digest in manifest["file_sha256"].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    summary = json.loads((OUT / "summary.json").read_text())
    assert summary["status"] == "PASS_QWEN_NATIVE_TRAIN_ENCODING_PREP_NOT_TRAINING_APPROVED"
    assert summary["model_id"] == "Qwen/Qwen3-8B"
    assert summary["TRAIN_rows"] == 240 and summary["intent_groups"] == 40
    assert summary["all_prompt_labels_masked"] and summary["all_target_and_EOS_labels_supervised"]
    assert summary["all_decoded_roundtrips_exact"] and summary["negative_controls_rejected"] == 6
    assert summary["native_parser_synthetic_controls"] == 2
    assert summary["rows_approved_for_training"] == summary["independent_human_reviews"] == 0
    assert all(summary[k] == 0 for k in ("DEV_rows_opened", "confirmation_rows_opened",
                                          "official_TEST_rows_opened", "model_calls", "GPU_jobs", "optimizer_steps"))
    assert summary["weight_shards_published"] == 5 and summary["model_weights_downloaded"] is False
    assert "docs/verification/kali-qwen3-8b-second-base-2026-10-28/" in (ROOT / ".gitignore").read_text()
    print(json.dumps({"status": "PASS_PUBLIC_QWEN_PREP_AGGREGATES",
                      "train_rows_encoded": 240, "train_rows_approved": 0,
                      "private_token_arrays_reproduced": False}))


if __name__ == "__main__":
    main()
