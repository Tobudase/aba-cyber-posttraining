#!/usr/bin/env python3
"""Check aggregate-only data-intake pilot publication, not private task bodies."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/kali-next-data-pilot-2026-10-27'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    m = json.loads((OUT / 'manifest.json').read_text())
    for name, digest in m['file_sha256'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert sha(path) == digest, name
    x = json.loads((OUT / 'summary.json').read_text())
    assert x['status'] == 'ENGINEERING_INTAKE_PILOT_COMPLETE_HUMAN_REVIEW_PENDING'
    g, c, v, p = (x[k] for k in ('generation', 'candidates', 'validation', 'provenance'))
    assert g['bounded_public_context_requests'] == 2 and g['responses_received'] == 0
    assert g['native_ABA_data_generation_executed'] is False and g['protected_examples_sent'] == 0
    assert c['total'] == c['positive'] + c['deliberate_negative_controls'] == 13
    assert c['positive'] == v['Mac_positive_gold_passed'] == v['Linux_positive_gold_passed'] == 9
    assert v['cross_platform_stdout_sha256_identical'] == 9
    assert v['negative_controls_rejected_before_execution'] == 4
    assert sum(v['negative_control_reasons'].values()) == 4
    assert c['new_independent_human_reviews'] == c['training_eligible'] == c['heldout_rows_created'] == 0
    assert p['independent_source_holdout_established'] is False
    assert x['scientific_decision']['eligible_for_training'] is False
    assert x['scientific_decision']['formal_default'] == 'original_base'
    assert x['private_task_bodies_or_commands_released'] is False
    print(json.dumps({'status': 'PASS_PUBLIC_INTAKE_AGGREGATES',
                      'verified_files': len(m['file_sha256']),
                      'training_eligible': 0, 'private_tasks_reproduced': False}))


if __name__ == '__main__':
    main()
