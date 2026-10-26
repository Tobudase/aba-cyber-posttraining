#!/usr/bin/env python3
"""Check published matched-control receipts and frozen gate arithmetic."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "results/kali-prefix-control-2026-10-26"


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(DIRECTORY / "publication-manifest.json")
    for name, digest in manifest["file_sha256"].items():
        p = ROOT / name
        assert p.resolve().is_relative_to(ROOT) and p.is_file() and not p.is_symlink()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == digest, name
    result = read(DIRECTORY / "matched-control.json")
    receipts = read(DIRECTORY / "training-receipts.json")
    assert result["new_optimizer_steps"] == 256 and result["new_generations"] == 48
    assert set(result["arms"]) == set(receipts) == {"uniform", "prefix8"}
    assert len({x["initial_LoRA_sha256"] for x in receipts.values()}) == 1
    assert len({x["epoch_order_sha256"] for x in receipts.values()}) == 1
    passing = []
    for name, weight in [("uniform", 1), ("prefix8", 8)]:
        arm, tr = result["arms"][name], receipts[name]
        assert arm["critical_prefix_weight"] == tr["critical_prefix_weight"] == weight
        assert tr["optimizer_steps"] == len(tr["trace"]) == tr["nonzero_gradient_steps"] == 128
        assert tr["changed_tensors"] > 0 and tr["adapter_reload_max_logit_delta"] <= 1e-4
        assert all(math.isfinite(x["loss"]) and math.isfinite(x["gradient_norm_before_clip"]) for x in tr["trace"])
        drop = (arm["token_weighted_NLL_before"] - arm["token_weighted_NLL_after"]) / arm["token_weighted_NLL_before"]
        assert abs(drop - arm["relative_loss_drop"]) < 1e-12
        nf4, bf16 = result["sets"][name + "_NF4_TRAIN"], result["sets"][name + "_BF16"]
        passed = (nf4["correct"] >= 7 and bf16["correct"] >= result["sets"]["base_BF16"]["correct"] and drop >= 0.5
            and nf4["truncated"] == bf16["truncated"] == 0 and nf4["format_complete"] == bf16["format_complete"] == 8)
        assert arm["predeclared_sanity_gate_passed"] == passed
        if passed:
            passing.append(name)
    selected = min(passing, key=lambda x: result["arms"][x]["critical_prefix_weight"]) if passing else None
    assert result["selected_arm"] == selected and result["training_sanity_gate_passed"] == bool(passing)
    provenance = read(DIRECTORY / "evidence-provenance.json")
    for file, field in [("kali_sft_recipe.py", "optimizer_source_sha256"), ("kali_prefix_sft_recipe.py", "prefix_optimizer_source_sha256")]:
        assert hashlib.sha256((ROOT / "scripts" / file).read_bytes()).hexdigest() == provenance[field]
    candidate = read(DIRECTORY / "native-rationale-preparation.json")
    assert candidate["TRAIN_rows"] == 8 and candidate["supervised_tokens"] == 452 and candidate["shared_TRAIN_recipe_schema_check"] == "PASS"
    assert candidate["model_generations"] == candidate["optimizer_steps"] == candidate["GPU_allocations"] == candidate["external_teacher_calls"] == 0
    assert not candidate["independent_human_review"]
    status = read(DIRECTORY / "stage-status.json")
    assert status["weight_control_training_sanity_gate_passed"] == bool(passing) and status["formal_default"] == "original_base"
    assert status["official_TEST_calls"] == status["old_sealed_validation_calls"] == status["new_confirmation_calls"] == status["external_teacher_calls"] == 0
    assert not status["new240_SFT_executed"] and not status["new_ABA_search_executed"] and not status["native_rationale_candidate_trained"]
    assert read(DIRECTORY / "resource-cleanup.json")["remaining_owned_resources"] == 0
    reseg = read(DIRECTORY / "same-text-resegmentation.json")
    reseg_receipts = read(DIRECTORY / "resegmentation-training-receipts.json")
    assert reseg["new_optimizer_steps"] == 256 and reseg["new_generations"] == 48
    assert len({v["initial_LoRA_sha256"] for v in reseg_receipts.values()}) == 1
    assert len({v["epoch_order_sha256"] for v in reseg_receipts.values()}) == 1
    reseg_passing = []
    for name in ["canonical", "resegmented"]:
        arm, tr = reseg["arms"][name], reseg_receipts[name]
        assert tr["optimizer_steps"] == len(tr["trace"]) == tr["nonzero_gradient_steps"] == 128 and tr["changed_tensors"] > 0 and tr["adapter_reload_max_logit_delta"] <= 1e-4
        nf4, bf16 = reseg["sets"][name + "_NF4_TRAIN"], reseg["sets"][name + "_BF16"]
        drop = (arm["token_weighted_NLL_before"] - arm["token_weighted_NLL_after"]) / arm["token_weighted_NLL_before"]
        assert abs(drop - arm["relative_loss_drop"]) < 1e-12
        passed = (nf4["correct"] >= 7 and bf16["correct"] >= reseg["sets"]["base_BF16"]["correct"] and drop >= 0.5
            and nf4["truncated"] == bf16["truncated"] == 0 and nf4["format_complete"] == bf16["format_complete"] == 8
            and nf4["think_closed"] == bf16["think_closed"] == 8)
        assert arm["predeclared_sanity_gate_passed"] == passed
        if passed:
            reseg_passing.append(name)
    assert reseg["training_sanity_gate_passed"] == status["resegmentation_training_sanity_gate_passed"] == bool(reseg_passing)
    encoding = read(DIRECTORY / "resegmentation-encoding-audit.json")
    assert encoding["canonical_supervised_tokens"] == 240 and encoding["resegmented_supervised_tokens"] == 248
    assert encoding["native_input_token_IDs_identical"] and encoding["complete_decoded_training_text_identical"] and encoding["model_tokenizer_on_disk_unchanged"]
    parity = read(DIRECTORY / "resegmentation-exported-encoder-parity.json")
    assert parity["rows"] == 8 and parity["actual_prepared_input_IDs_reproduced_exactly"]
    assert parity["source_sha256"] == hashlib.sha256((ROOT / "scripts/kali_target_segmentation.py").read_bytes()).hexdigest()
    audit = read(DIRECTORY / "special-token-weight-audit.json")
    assert audit["GPU_allocations"] == audit["model_generations"] == audit["optimizer_steps"] == 0
    for value in audit["tensors"].values():
        assert not value["rows"]["151668"]["exact_all_zero"] and not value["closing_equals_EOS"]
    replication = read(DIRECTORY / "uniform-replication.json")
    assert all(replication["same_fields"].values()) and replication["NLL_after_exact_equal"]
    assert status["completed_additional_8B_optimizer_steps"] == 512 and status["completed_additional_8B_generations"] == 96
    allowed = {"README.md"}
    for folder in manifest["prior_manifest_order"]:
        p = ROOT / "results" / folder
        before = read(p / "publication-manifest.at-ab1af0f.json")["file_sha256"]
        after = read(p / "publication-manifest.json")["file_sha256"]
        assert set(before) == set(after) and {k for k in before if before[k] != after[k]} <= allowed
        allowed.add(str((p / "publication-manifest.json").relative_to(ROOT)))
    print(json.dumps({"status": "PASS_PUBLIC_MATCHED_PREFIX_CONTROL", "files_verified": len(manifest["file_sha256"]),
        "selected_arm": selected, "private_model_reproduction": False, "TRAIN_fitting_not_generalization": True}))


if __name__ == "__main__":
    main()
