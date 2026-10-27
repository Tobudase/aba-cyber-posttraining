#!/usr/bin/env python3
"""Verify aggregate SFT receipts and frozen gates; no private inference replay."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results/kali-bf16-240-sft-2026-10-26'


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(D / 'publication-manifest.json')
    for name, digest in manifest['file_sha256'].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
    s, receipt, config, freeze = [read(path) for path in [D / 'summary.json',
        D / 'training-receipt.json', ROOT / 'configs/kali-bf16-240-sft-executed.json', D / 'evidence-provenance.json']]
    for key, path in [('worker_sha256', ROOT / 'scripts/check-kali-bf16-240-sft.py'),
                      ('optimizer_source_sha256', ROOT / 'scripts/kali_sft_recipe.py'),
                      ('effective_config_sha256', ROOT / 'configs/kali-bf16-240-sft-executed.json'),
                      ('TRAIN_file_sha256', ROOT / 'data/benchkit/kali-verified-sft-v1/train.jsonl'),
                      ('DEV_file_sha256', ROOT / 'data/benchkit/kali-verified-sft-v1/dev.jsonl')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == freeze[key], path
    assert s['new_optimizer_steps'] == receipt['optimizer_steps'] == receipt['nonzero_gradient_steps'] == len(receipt['trace']) == 480
    assert receipt['changed_tensors'] > 0 and receipt['adapter_reload_max_logit_delta'] <= 1e-4
    assert all(math.isfinite(x['loss']) and math.isfinite(x['gradient_norm_before_clip']) for x in receipt['trace'])
    assert receipt['effective_optimizer_recipe'] == config['arms'][0]['optimizer']
    assert config['training_precision'] == config['inference_precision'] == 'BF16'
    assert config['inference']['batch_size'] == 4 and config['inference']['max_new_tokens'] == 1024
    assert receipt['effective_optimizer_recipe']['epochs'] == 2 and receipt['TRAIN_presentations'] == 480
    assert s['TRAIN_rows'] == 240 and s['new_generations'] == 224
    assert len(s['DEV']['by_group']) == 12
    for arm in ['base', 'sft']:
        assert s['DEV'][arm]['rows'] == 72 and s['TRAIN_diagnostic'][arm]['rows'] == 16
        assert s['retention'][arm]['rows'] == 24 and s['retention'][arm]['previously_exposed_regression_panel']
        for field in ['correct', 'unsupported']:
            assert sum(g[arm + '_' + field] for g in s['DEV']['by_group'].values()) == s['DEV'][arm][field]
        assert s['formats'][arm]['rows'] == 112
    lower = s['DEV']['sft']['correct'] - s['DEV']['base']['correct'] - s['DEV']['base']['unsupported']
    groups = sum(g['sft_correct'] - g['base_correct'] - g['base_unsupported'] > 0 for g in s['DEV']['by_group'].values())
    assert s['development_gate']['conservative_DEV_gain_lower_bound'] == lower
    assert s['development_gate']['conservative_positive_DEV_groups'] == groups
    checks = {'DEV_conservative_gain_at_least4': lower >= 4,
        'conservative_positive_groups_at_least2': groups >= 2,
        'retention_strict_not_decreased': s['retention']['sft']['strict_correct'] >= s['retention']['base']['strict_correct'],
        'candidate_complete_outputs': s['formats']['sft']['complete_output_blocks'] == 112,
        'candidate_think_closure': s['formats']['sft']['think_closed'] == 112,
        'candidate_no_truncation': s['formats']['sft']['truncated'] == 0, 'valid_training_and_reload': True}
    assert checks == s['development_gate']['checks']
    assert s['development_gate']['passes_development_gate'] == all(checks.values())
    assert abs(s['TRAIN_NLL_relative_drop'] - (s['TRAIN_NLL_before'] - s['TRAIN_NLL_after']) / s['TRAIN_NLL_before']) < 1e-12
    assert not s['candidate_promoted'] and s['formal_default'] == 'original_base'
    assert s['official_TEST_calls'] == s['old_sealed_calls'] == s['new_confirmation_calls'] == s['external_teacher_calls'] == 0
    assert not s['new_ABA_search_executed'] and not s['independent_expert_or_official_generalization_proven']
    assert s['resources']['GPU_resources_remaining'] == s['resources']['CPU_scoring_resources_remaining'] == 0
    assert not s['resources']['cleanup_errors']
    cpu = read(D / 'CPU-preflight.json')
    assert cpu['TRAIN_DEV_group_overlap'] == cpu['TRAIN_DEV_exact_query_overlap'] == 0
    assert cpu['supervised_TRAIN_tokens'] == 6864 and cpu['max_TRAIN_sequence_tokens'] == 376
    assert cpu['protected_confirmation_bodies_opened'] == 0
    print(json.dumps({'status': 'PASS_PUBLIC_BF16_240_RESULT', 'files_verified': len(manifest['file_sha256']),
        'development_gate_passed': all(checks.values()), 'formal_default': 'original_base',
        'new_model_calls': 0, 'private_predictions_independently_recomputed': False}))


if __name__ == '__main__':
    main()
