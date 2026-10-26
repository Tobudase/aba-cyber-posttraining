#!/usr/bin/env python3
"""Public-byte/numeric checks only; no reconstruction of private model outputs."""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
D = R / 'results/kali-learning-diagnosis-2026-10-25'


def read(p):
    return json.loads(p.read_text())


def main():
    manifest = read(D / 'publication-manifest.json')
    for name, expected in manifest['file_sha256'].items():
        path = R / name
        assert path.resolve().is_relative_to(R) and path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    s = read(D / 'summary.json')
    assert s['status'] == 'COMPLETE_PAIRED_CAUSAL_DIAGNOSTIC'
    assert s['new_optimizer_steps'] == 84 and s['new_learner_generations'] == 174
    assert s['official_TEST_model_calls'] == s['sealed_validation_model_calls'] == s['external_teacher_API_calls'] == 0
    assert s['same_card_fresh_baselines'] and s['matched_new_arm_initialization']
    assert s['new_experiment_is_manual_fixed_ablation_not_ABA_search']
    assert s['interpretations']['formal_default_remains_original_base']
    assert not s['interpretations']['unique_sample_count_cause_confirmed']
    assert not s['interpretations']['generalization_or_official_ranking_confirmed']
    assert not s['old_publication_or_frozen_gate_changed']
    assert s['controls']['native_NF4_controls_full_match'] and s['controls']['native_BF16_controls_full_match']
    assert sum(x['rows'] for x in s['sets'].values()) + 6 == 174
    for key, values in s['sets'].items():
        if key.endswith('_dev'):
            assert values['rows'] == 12 and 0 <= values['contract_correct'] <= 12
        else:
            assert key.endswith('_retention') and values['rows'] == 24
            assert 0 <= values['strict_correct'] <= 24
    assert s['baseline_BF16_DEV_contract'] == s['sets']['bf16_base_dev']['contract_correct']
    assert s['baseline_BF16_retention_strict'] == s['sets']['bf16_base_retention']['strict_correct']
    nll = s['NLL_matrix']
    assert len(nll) == 8
    for key, cell in nll.items():
        assert cell['rows'] == 42 and cell['target_tokens'] > 0
        assert all(math.isfinite(cell[k]) and cell[k] >= 0 for k in ['mean_row_nll', 'token_weighted_nll'])
    for precision, contrast in s['old_precision_and_learning_contrasts'].items():
        before = nll['old_objective_' + precision + '_base']['token_weighted_nll']
        after = nll['old_objective_' + precision + '_old_adapter']['token_weighted_nll']
        assert abs(contrast['old_training_objective_delta_nll'] - (after - before)) < 1e-10
        assert abs(contrast['old_training_objective_relative_change'] - ((after - before) / before)) < 1e-10
        assert contrast['old_DEV_contract_change'] == s['sets'][precision + '_old_adapter_dev']['contract_correct'] - s['sets'][precision + '_base_dev']['contract_correct']
    receipts = read(D / 'training-receipts.json')
    assert set(receipts) == {'style_control', 'hardmix'}
    for arm, tr in receipts.items():
        assert tr['status'] == 'COMPLETE' and tr['optimizer_steps'] == len(tr['losses']) == 42
        assert tr['changed_tensors'] > 0 and tr['adapter_reload_max_logit_delta'] <= 1e-4
        assert tr['seed'] == 42 and tr['learning_rate'] == 5e-6 and tr['DEV_or_validation_gradient_rows'] == 0
        assert tr['initial_LoRA_sha256'] == s['controls']['fresh_initial_LoRA_sha256']
        assert all(math.isfinite(x) for x in tr['losses'])
        a = s['new_matched_arms'][arm]
        dev = s['sets'][arm + '_bf16_dev']
        retention = s['sets'][arm + '_bf16_retention']
        assert a['DEV_contract_correct_BF16'] == dev['contract_correct']
        assert a['retention_strict_BF16'] == retention['strict_correct']
        gate = dev['contract_correct'] > s['baseline_BF16_DEV_contract'] and retention['strict_correct'] >= s['baseline_BF16_retention_strict'] and dev['format_or_truncation_failures'] == retention['format_or_truncation_failures'] == 0
        assert a['promising_developer_gate'] == gate
    assert len({x['adapter_sha256'] for x in receipts.values()}) == 2
    parity = read(D / 'future-encoder-parity.json')
    assert parity['rows_checked'] == 84 and parity['actual_tokenizer'] and not parity['worker_or_payload_modified']
    old = read(D / 'scorer-correction.json')
    assert all(x['contract_correct'] == 4 for x in old['DEV12_recomputed'].values())
    assert old['historical_frozen_scores_and_gate_unchanged'] and old['official_scoring_unchanged']
    assert old['scorer_source_sha256'] == hashlib.sha256((R / 'scripts/kali_command_contract.py').read_bytes()).hexdigest()
    assert not s['resources']['cleanup_errors'] and s['resources']['remaining_owned_resources'] == 0
    assert all(0 <= s['resources'][k] <= 100 for k in ['mean_GPU_whole_worker', 'mean_GPU_after_staging'])
    cross = read(D / 'cross-allocation-reproducibility.json')
    assert cross['same_24_prompts'] and cross['raw_response_changes'] == 7 and cross['extracted_command_changes'] == 3
    execution = read(D / 'new-gain-execution.json')
    assert execution['status'] == 'COMPLETE' and not execution['cleanup_errors'] and execution['owned_resources_remaining'] == 0
    assert len(execution['records']) == 5 and all(x['executed'] and x['matches_frozen_contract'] for x in execution['records'])
    assert sum(x['passed'] for x in execution['records']) == 3
    cleanup = read(D / 'final-resource-cleanup.json')
    assert cleanup['new_diagnostic_jobs_pods_configmaps'] == cleanup['CPU_VM_instances'] == 0 and cleanup['CPU_VM_runStrategy'] == 'Halted'
    folders = ['kali-cuda-2026-10-24', 'kali-replay-v3-2026-10-24', 'kali-causal-findings-2026-10-25', 'kali-seed43-replication-2026-10-25', 'kali-native-family-2026-10-25']
    allowed = {'README.md'}
    for folder in folders:
        path = R / 'results' / folder
        before = read(path / 'publication-manifest.at-ed2405b.json')['file_sha256']
        after = read(path / 'publication-manifest.json')['file_sha256']
        assert set(before) == set(after)
        assert {k for k in before if before[k] != after[k]} <= allowed
        allowed.add(str((path / 'publication-manifest.json').relative_to(R)))
    subprocess.run([sys.executable, str(R / 'scripts/check-kali-diagnostic-guards.py')], check=True)
    print(json.dumps({'status': 'PASS_PUBLIC_LEARNING_DIAGNOSIS_EVIDENCE_AND_GUARDS',
                      'files_verified': len(manifest['file_sha256']),
                      'private_runtime_or_model_output_reproduction': False,
                      'formal_default': 'original_base', 'official_or_sealed_queries': 0}))


if __name__ == '__main__':
    main()
