#!/usr/bin/env python3
"""Check aggregate-only Kali task quality release."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/kali-task-quality-gate-2026-10-28'


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    assert manifest['schema'] == 'kali.task-quality.public.v1'
    for name, digest in manifest['file_sha256'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    s = json.loads((OUT / 'summary.json').read_text())
    assert s['status'] == 'TASK_QUALITY_ENGINEERING_CHECK_COMPLETE_HUMAN_REVIEW_PENDING'
    assert s['model_proposals'] == s['accepted_for_local_engineering_checks'] + s['semantic_mismatch_rejected_before_execution'] == 3
    assert s['metamorphic_command_runs'] == s['metamorphic_oracle_passes'] == s['accepted_for_local_engineering_checks'] * s['synthetic_input_variants_per_accepted_proposal'] == 10
    assert s['independent_human_reviews'] == s['training_eligible'] == 0
    assert s['native_ABA_data_generation_complete'] is False
    assert s['new_gpu_jobs'] == s['new_linux_jobs'] == s['new_training_steps'] == s['official_test_calls'] == 0
    assert s['previous_confirmation_gate_changed'] is False and s['formal_default'] == 'original_base'
    assert s['raw_candidate_bodies_released'] is False
    print(json.dumps({'status': 'PASS_PUBLIC_TASK_QUALITY_AGGREGATES',
                      'metamorphic_passes': 10, 'training_eligible': 0}))


if __name__ == '__main__':
    main()
