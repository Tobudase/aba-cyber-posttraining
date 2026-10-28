#!/usr/bin/env python3
"""Verify aggregate-only proposal publication without private task bodies."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/kali-model-proposal-pilot-2026-10-28'


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    assert manifest['schema'] == 'kali.model-proposal.public.v1'
    for name, digest in manifest['file_sha256'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    s = json.loads((OUT / 'summary.json').read_text())
    assert s['status'] == 'MODEL_PROPOSAL_ENGINEERING_PILOT_COMPLETE_HUMAN_REVIEW_PENDING'
    assert s['requests_this_round'] == 2
    assert s['text_response_rejected'] + s['structured_tool_responses'] == 2
    assert s['model_proposals'] == s['local_engineering_pass'] + s['semantic_mismatch_rejected_before_execution'] == 3
    assert s['independent_human_reviews'] == s['training_eligible'] == 0
    assert s['official_test_calls_this_round'] == s['gpu_jobs_this_round'] == s['model_training_steps_this_round'] == 0
    assert s['native_ABA_generation_complete'] is False
    assert s['private_candidate_bodies_released'] is False
    assert s['formal_default'] == 'original_base' and s['previous_confirmation_gate_changed'] is False
    print(json.dumps({'status': 'PASS_PUBLIC_MODEL_PROPOSAL_AGGREGATES',
                      'proposals': 3, 'local_pass': 2, 'training_eligible': 0}))


if __name__ == '__main__':
    main()
