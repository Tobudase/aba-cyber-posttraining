#!/usr/bin/env python3
"""Verify a numerical-only public release offline; no inference or cluster use.

Private source artifacts are not released. Their recorded hashes and prior host
verification are evidence, not a fresh public reproduction of those artifacts.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'results/kali-cuda-2026-10-24/'


def load(name):
    return json.loads((ROOT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = load(PREFIX + 'publication-manifest.json')
    for name, expected in manifest['file_sha256'].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink(), name
        assert sha(path) == expected, name
    p = load('configs/kali-cuda-cycle-v1.protocol.json')
    phash = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False).encode()).hexdigest()
    assert phash == manifest['protocol_sha256']
    assert sha(ROOT / 'scripts/run-kali-cuda-cycle.py') == p['runner_sha256']
    assert not p['official_test_enabled'] and not p['confirmation_enabled']
    receipts = load(PREFIX + 'numerical-receipts.json')['phases']
    for phase, record in receipts.items():
        r = record['numerical_receipt']
        assert r['status'] == 'COMPLETE' and r['protocol_sha256'] == phash
        assert r['runner_sha256'] == p['runner_sha256']
        assert r['GPU'] == p['GPU_model'] == 'NVIDIA RTX A6000'
        assert r['official_test_rows'] == r['confirmation_rows'] == 0
        assert record['source_receipt_sha256'] == record['host_recorded_receipt_sha256']
        assert record['host_verification_status'] == 'HOST_COLLECTION_VERIFIED'
        assert record['host_recorded_job_succeeded']
        if phase.endswith('infer'):
            assert r['inference_rows'] == 108 and r['truncated_rows'] == 0
    train = receipts['E2/train']['numerical_receipt']
    assert train['optimizer_steps'] == 128 and train['changed_parameter_tensors'] == 144
    assert train['trainable_parameters'] == 7667712
    assert train['adapter_reload_max_logit_delta'] <= 1e-4
    assert train['development_rows_used_for_optimization'] == 0
    assert len(train['losses']) == 128
    assert receipts['E2/infer']['numerical_receipt']['training_receipt_sha256'] == receipts['E2/train']['source_receipt_sha256']
    host = load(PREFIX + 'host-verification.json')
    assert all(host['native'].values())
    assert host['setup_failed'] is False
    assert host['deterministic_setup_verifier_passed'] and host['semantic_setup_review_passed']
    assert host['supervisor_completed'] and host['native_client_returncode'] == 0
    assert not host['cleanup_errors']
    cleanup = host['final_resource_cleanup']
    assert cleanup['passed'] and cleanup['owned_CPU_VM_stopped']
    assert cleanup['owned_GPU_jobs_pods_configmaps_remaining'] == 0
    c = load(PREFIX + 'comparison.json')
    assert c['protocol_sha256'] == phash and not c['adoption_passed']
    assert c['decision'] == 'KEEP_ORIGINAL_BASE_DO_NOT_PROMOTE_ADAPTER'
    assert not c['adoption_checks']['retention_strict_not_decreased']
    for group, count, before, after in [('domain', 36, 2, 3), ('retention', 72, 52, 36)]:
        v = c['comparisons'][group]
        assert v['rows'] == count
        for which, expected in [('baseline', before), ('post', after)]:
            assert round(v[which]['strict_option_value_correct'] * count / 100) == expected
    print(json.dumps({'status': 'PASS_PUBLIC_NUMERICAL_RELEASE',
        'files_verified': len(manifest['file_sha256']), 'optimizer_steps': 128,
        'adoption_passed': False, 'official_test_rows': 0,
        'confirmation_rows': 0, 'fresh_private_artifact_or_score_reproduction': False}, indent=2))


if __name__ == '__main__':
    main()
