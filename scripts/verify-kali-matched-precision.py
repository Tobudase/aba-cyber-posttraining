#!/usr/bin/env python3
"""Verify public precision aggregates and frozen diagonal gates, no model calls."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results/kali-matched-precision-2026-10-26'


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(D / 'publication-manifest.json')
    for name, digest in manifest['file_sha256'].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
    summary, receipts, nll = [read(D / name) for name in ['summary.json', 'training-receipts.json', 'NLL.json']]
    config = read(ROOT / 'configs/kali-matched-precision-executed.json')
    frozen = read(D / 'evidence-provenance.json')
    assert hashlib.sha256((ROOT / 'configs/kali-matched-precision-executed.json').read_bytes()).hexdigest() == frozen['effective_config_sha256']
    assert hashlib.sha256((ROOT / 'scripts/check-kali-matched-precision.py').read_bytes()).hexdigest() == frozen['worker_sha256']
    assert hashlib.sha256((ROOT / 'scripts/kali_sft_recipe.py').read_bytes()).hexdigest() == frozen['optimizer_source_sha256']
    assert summary['new_optimizer_steps'] == sum(v['optimizer_steps'] for v in receipts.values()) == 256
    assert summary['new_generations'] == sum(v['rows'] for v in summary['sets'].values()) == 48
    assert set(receipts) == {'NF4_training', 'BF16_training'}
    assert len({v['initial_LoRA_sha256'] for v in receipts.values()}) == 1
    assert len({v['epoch_order_sha256'] for v in receipts.values()}) == 1
    assert len(summary['sets']) == 6 and all(v['rows'] == 8 for v in summary['sets'].values())
    assert config['inference']['batch_size'] == summary['inference_batch_size'] == 4
    assert not config['inference']['forced_prefix'] and not config['inference']['output_repair']
    passing = []
    for arm in config['arms']:
        name, mode = arm['name'], arm['training_precision']
        r = receipts[name]
        assert r['effective_optimizer_recipe'] == arm['optimizer']
        assert r['optimizer_steps'] == len(r['trace']) == 128
        before, after = [nll[name + suffix]['token_weighted_NLL'] for suffix in ['_before', '_after']]
        drop = (before - after) / before
        assert abs(summary['arms'][name]['relative_NLL_drop'] - drop) < 1e-12
        cell = summary['sets'][name + '_' + mode]
        passed = (cell['correct'] >= 7 and cell['format_complete'] == cell['think_closed'] == 8
            and cell['truncated'] == 0 and drop >= .5 and r['nonzero_gradient_steps'] == 128
            and r['changed_tensors'] > 0 and r['adapter_reload_max_logit_delta'] <= 1e-4
            and all(math.isfinite(t['loss']) and math.isfinite(t['gradient_norm_before_clip']) for t in r['trace']))
        assert summary['arms'][name]['matched_diagonal_gate_passed'] == passed
        passing.append(passed)
    assert summary['both_matched_diagonals_gate_passed'] == all(passing)
    assert summary['old_full_cross_precision_gate_remains'] == 'FAILED_UNCHANGED'
    assert summary['formal_default'] == 'original_base' and not summary['heldout_generalization_improvement_established']
    assert summary['official_or_confirmation_calls'] == summary['external_teacher_calls'] == 0
    assert not summary['new240_SFT_or_ABA_executed']
    assert summary['resources']['remaining_owned_resources'] == 0 and not summary['resources']['cleanup_errors']
    for check in read(D / 'loader-checks.json'):
        if check['mode'] == 'BF16':
            assert check['non_LoRA_FP32_parameters'] == 0
    assert read(D / 'CPU-preflight.json')['supervised_tokens'] == 248
    assert read(D / 'gate-checks.json')['cases'] == 10
    assert read(D / 'admission-dry-run.json')['created_objects'] == 0
    print(json.dumps({'status': 'PASS_PUBLIC_MATCHED_PRECISION',
        'files_verified': len(manifest['file_sha256']), 'both_matched_diagonal_gate_passed': all(passing),
        'new_model_calls': 0, 'private_inference_reproduced': False, 'formal_default': 'original_base'}))


if __name__ == '__main__':
    main()
