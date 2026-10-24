#!/usr/bin/env python3
"""Check public V3 evidence offline; this does not re-execute private artifacts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'results/kali-replay-v3-2026-10-24/'
V1 = 'results/kali-cuda-2026-10-24/'


def load(name):
    return json.loads((ROOT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False).encode()).hexdigest()


def main():
    manifest = load(PREFIX + 'publication-manifest.json')
    for name, expected in manifest['file_sha256'].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink(), name
        assert sha(path) == expected, name
    protocol = load('configs/kali-replay-v3.protocol.json')
    phash = canonical_sha(protocol)
    assert phash == manifest['protocol_sha256']
    assert sha(ROOT / 'scripts/run-kali-cuda-cycle.py') == protocol['runner_sha256']
    assert not protocol['official_test_enabled'] and not protocol['confirmation_enabled']
    previous_protocol = load('configs/kali-cuda-cycle-v1.protocol.json')
    changed = {key for key in protocol.keys() | previous_protocol.keys()
               if protocol.get(key) != previous_protocol.get(key)}
    assert changed == {'frozen_at_utc', 'storage_prefix', 'train_manifest',
                       'train_manifest_sha256', 'train_rows_sha256'}

    receipts = load(PREFIX + 'numerical-receipts.json')['phases']
    assert set(receipts) == {'E0/infer', 'E2/train', 'E2/infer'}
    for phase, record in receipts.items():
        r = record['numerical_receipt']
        assert r['status'] == 'COMPLETE' and r['protocol_sha256'] == phash
        assert r['runner_sha256'] == protocol['runner_sha256']
        assert r['GPU'] == protocol['GPU_model'] == 'NVIDIA RTX A6000'
        assert r['official_test_rows'] == r['confirmation_rows'] == 0
        assert r['labels_in_inference_input'] is False
        assert record['source_receipt_sha256'] == record['host_recorded_receipt_sha256']
        assert record['host_verification_status'] == 'HOST_COLLECTION_VERIFIED'
        assert record['host_recorded_job_succeeded']
        u = record['GPU_utilization_after_copying_and_dependency_preparation']
        assert u['samples'] > 0 and 0 <= u['mean_percent'] <= u['peak_percent'] <= 100
        assert u['includes_model_loading'] and not u['whole_allocation_measurement']
        if phase.endswith('infer'):
            assert r['inference_rows'] == 108 and r['truncated_rows'] == 0
    train = receipts['E2/train']['numerical_receipt']
    assert train['optimizer_steps'] == 128 and len(train['losses']) == 128
    assert train['changed_parameter_tensors'] == 144 and train['trainable_parameters'] == 7667712
    assert train['adapter_reload_max_logit_delta'] <= 1e-4
    assert train['development_rows_used_for_optimization'] == 0
    assert receipts['E2/infer']['numerical_receipt']['training_receipt_sha256'] == receipts['E2/train']['source_receipt_sha256']

    checks = load(PREFIX + 'study-checks.json')
    frozen = checks['freeze']
    assert frozen['protocol_sha256'] == phash
    assert frozen['previous_protocol_sha256'] == canonical_sha(previous_protocol)
    assert frozen['domain_rows_unchanged'] == 96 and frozen['train_rows'] == 128
    assert frozen['model_worker_optimizer_GPU_prompt_generation_scoring_and_adoption_gate_unchanged']
    assert frozen['prior_adapter_not_used'] and frozen['fresh_matching_E0_required']
    assert frozen['max_candidates'] == 1 and frozen['official_test_rows'] == frozen['confirmation_rows'] == 0
    assert checks['pretraining']['status'] == 'PASS' and all(checks['pretraining']['checks'].values())
    audit = checks['token_boundaries']
    assert audit['status'] == 'PASS' and not audit['token_budgets_equal']
    for version, total, target in [('previous', 52180, 3105), ('v3', 52420, 3222)]:
        a = audit['results'][version]
        assert a['rows'] == a['assistant_only_boundary_passed_rows'] == 128
        assert a['total_full_tokens'] == total and a['assistant_target_tokens'] == target
        assert a['max_full_tokens'] <= protocol['training']['max_sequence_tokens']
    fixtures = checks['new_utility_fixtures']
    assert fixtures['status'] == 'PASS' and fixtures['passed_rows'] == fixtures['rows'] == 32
    assert fixtures['families'] == 16 and len(fixtures['tools']) == 8
    use = checks['data_use']
    assert use['new_utility_training_ids'] == 32 and use['domain_training_ids'] == 96
    assert use['adapter_bytes_differ'] and use['V3_adapter_sha256'] == train['adapter_sha256']
    previous_train = load(V1 + 'numerical-receipts.json')['phases']['E2/train']['numerical_receipt']
    assert use['V1_adapter_sha256'] == previous_train['adapter_sha256'] != train['adapter_sha256']
    differences = [i + 1 for i, (a, b) in enumerate(zip(previous_train['losses'], train['losses'])) if a != b]
    assert len(differences) == use['changed_loss_steps'] == 126
    assert differences[0] == use['first_changed_training_loss_step'] == use['first_new_utility_step'] == 3
    baseline = checks['matched_baseline']
    assert baseline['rows'] == baseline['response_identical_to_previous_A6000_baseline'] == 108
    previous_base = load(V1 + 'numerical-receipts.json')['phases']['E0/infer']['numerical_receipt']
    assert receipts['E0/infer']['numerical_receipt']['predictions_sha256'] == previous_base['predictions_sha256']
    commands = checks['paired_command_comparison']
    assert commands['retention_same_as_V1'] == commands['retention_rows'] == 72
    assert commands['domain_same_as_V1'] == 33 and commands['domain_changed_commands'] == 3
    sem = checks['semantic_diagnosis']
    assert sem['tshark_extra_n_same_selected_packets_cases'] == 12
    assert sem['wrong_filename_failures_verified'] == 6 and sem['netstat_bundled_options_identical_output']
    assert sem['task_network_targets_contacted'] == 0 and not sem['scorer_or_historical_score_modified']

    host = load(PREFIX + 'host-verification.json')
    assert all(host['native'].values()) and not host['setup_failed']
    assert host['required_metric_name'] == 'frozen_adoption_gate' and host['required_metric_direction'] == 'max'
    assert host['deterministic_setup_verifier_passed'] and host['semantic_setup_review_passed']
    assert host['supervisor_completed'] and host['native_client_returncode'] == 0 and not host['cleanup_errors']
    assert host['prior_control_failure_optimizer_steps'] == 0 and host['actual_optimization_candidates'] == 1
    assert host['native_delivery_file_sha256']['train_metrics.json'] == receipts['E2/train']['source_receipt_sha256']
    cleanup = host['final_resource_cleanup']
    assert cleanup['passed'] and cleanup['owned_CPU_VM_stopped']
    assert cleanup['owned_GPU_jobs_pods_configmaps_remaining'] == 0
    comparison = load(PREFIX + 'comparison.json')
    assert comparison['protocol_sha256'] == phash and not comparison['adoption_passed']
    assert comparison['decision'] == 'KEEP_ORIGINAL_BASE_DO_NOT_PROMOTE_ADAPTER'
    assert not comparison['adoption_checks']['retention_strict_not_decreased']
    for group, rows, before, after in [('domain', 36, 2, 3), ('retention', 72, 52, 36)]:
        c = comparison['comparisons'][group]
        assert c['rows'] == rows
        for arm, count in [('baseline', before), ('post', after)]:
            assert round(c[arm]['strict_option_value_correct'] * rows / 100) == count
    assert comparison['official_test_rows'] == comparison['confirmation_rows'] == 0

    # Keep the original release manifest auditable while allowing current README/code maintenance.
    current = load(V1 + 'publication-manifest.json')
    archived = load(current['original_manifest_file'])
    assert sha(ROOT / current['original_manifest_file']) == current['original_manifest_sha256']
    changed_hashes = {key for key in archived['file_sha256']
                      if archived['file_sha256'][key] != current['file_sha256'][key]}
    assert changed_hashes == {'README.md', 'scripts/kali_native_scaffold.py', 'tests/test_kali_native_scaffold.py'}
    print(json.dumps({'status': 'PASS_PUBLIC_V3_NUMERICAL_RELEASE',
        'files_verified': len(manifest['file_sha256']), 'optimizer_steps': 128,
        'new_utility_rows': 32, 'adoption_passed': False, 'official_test_rows': 0,
        'confirmation_rows': 0, 'fresh_private_artifact_or_score_reproduction': False}, indent=2))


if __name__ == '__main__':
    main()
