#!/usr/bin/env python3
"""Verify released TRAIN-diagnostic records; does not reproduce private inference."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "results/kali-prefix-followup-2026-10-26"


def read(p):
    return json.loads(p.read_text())


def main():
    manifest = read(DIRECTORY / "publication-manifest.json")
    for name, digest in manifest["file_sha256"].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
    probe = read(DIRECTORY / "fixed-weight-probe.json")
    assert probe["new_generations"] == 56 and probe["new_optimizer_steps"] == 0
    assert all(v["identical_generated_token_sequences"] == 8 for v in probe["paired_generation_comparisons"].values())
    for arm in ["NF4_adapter_cache", "NF4_adapter_no_cache", "NF4_adapter_fresh_loader"]:
        assert probe["sets"][arm]["only_whitespace_before_EOS"] == 8 and probe["sets"][arm]["correct"] == 0
    assert all(v["truncated"] == 0 for v in probe["sets"].values())
    attribution = read(DIRECTORY / "prefix-loss-attribution.json")
    for name in ["NF4_adapter_set_state", "NF4_adapter_from_pretrained"]:
        value = attribution["arms"][name]
        assert value["critical_token_EOS_argmax_rows"] == 8 and value["critical_target_argmax_rows"] == 0
        assert 0.006 < value["mean_critical_target_probability"] < 0.009
        assert 0.45 < value["mean_critical_EOS_probability"] < 0.49
    test = read(DIRECTORY / "CPU-loss-alignment.json")
    assert test["uniform_matches_HF_CE"] and test["weighted_matches_independent_scalar_formula"] and test["invalid_inputs_rejected"] == 5
    static = read(DIRECTORY / "unsupported-static-review.json")
    assert static["rows"] == 3 and static["all_fail_explicit_requirements"] and static["commands_executed"] == 0 and static["historical_scores_unchanged"]
    status = read(DIRECTORY / "stage-status.json")
    repair = read(DIRECTORY / "matched-prefix-loss-control.json")
    if status["repair_executed"]:
        assert repair["new_optimizer_steps"] == 256 and repair["new_generations"] == 48
        receipts = read(DIRECTORY / "training-receipts.json")
        assert set(receipts) == {"uniform", "prefix8"}
        assert len({x["initial_LoRA_sha256"] for x in receipts.values()}) == 1
        assert len({x["epoch_order_sha256"] for x in receipts.values()}) == 1
        for name, weight in [("uniform", 1), ("prefix8", 8)]:
            assert receipts[name]["critical_prefix_weight"] == weight and receipts[name]["optimizer_steps"] == 128
            assert receipts[name]["nonzero_gradient_steps"] == 128 and receipts[name]["adapter_reload_max_logit_delta"] <= 1e-4
        assert status["completed_additional_8B_optimizer_steps"] == 256 and status["completed_additional_8B_generations"] == 104
    else:
        assert repair["status"] == "NOT_EXECUTED_NO_GPU_ALLOCATION"
        assert status["completed_additional_8B_optimizer_steps"] == 0 and status["completed_additional_8B_generations"] == 56
    assert status["official_TEST_calls"] == status["old_sealed_validation_calls"] == status["new_confirmation_calls"] == status["external_teacher_calls"] == 0
    assert not status["new240_SFT_executed"] and not status["new_ABA_search_executed"] and status["formal_default"] == "original_base"
    assert status["all_round_resources_cleaned"]
    assert read(DIRECTORY / "resource-cleanup.json")["remaining_owned_resources"] == 0
    allowed = {"README.md"}
    for folder in manifest["prior_manifest_order"]:
        path = ROOT / "results" / folder
        before = read(path / "publication-manifest.at-678e5c7.json")["file_sha256"]
        after = read(path / "publication-manifest.json")["file_sha256"]
        assert set(before) == set(after) and {k for k in before if before[k] != after[k]} <= allowed
        allowed.add(str((path / "publication-manifest.json").relative_to(ROOT)))
    print(json.dumps({"status": "PASS_PREFIX_FOLLOWUP_PUBLIC_RECORDS", "files_verified": len(manifest["file_sha256"]), "repair_executed": status["repair_executed"], "private_model_reproduction": False}))


if __name__ == "__main__":
    main()
