#!/usr/bin/env python3
"""Verify published aggregate counts and hashes without private examples."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/kali-targeted-intake-2026-10-28'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert manifest['schema']=='kali.targeted-intake.public.v1'
    for name,digest in manifest['file_sha256'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    s=json.loads((OUT/'summary.json').read_text())
    assert s['status']=='TARGETED_ENGINEERING_INTAKE_COMPLETE_HUMAN_REVIEW_PENDING'
    assert s['request_count']==3 and s['model_proposals']==s['frozen_intents']==6
    assert s['frozen_read_only_commands_admitted']+s['noncanonical_command_rejected_before_execution']==6
    assert s['local_jq_runs']==s['local_jq_oracle_passes']==15
    assert s['linux_tshark_runs']==s['linux_tshark_oracle_passes']==10
    assert s['independent_human_reviews']==s['training_eligible']==0
    assert s['GPU_count']==s['owned_cluster_objects_remaining']==s['official_TEST_calls']==s['new_model_training_steps']==0
    assert s['native_ABA_generation_complete'] is False
    assert s['independent_source_holdout_created'] is False
    assert s['private_raw_data_released'] is False
    assert s['formal_default']=='original_base' and s['previous_confirmation_gate_changed'] is False
    assert s['exact_prior_question_overlap']==s['exact_prior_command_overlap']==0
    assert s['semantic_independence_proven'] is False
    print(json.dumps({'status':'PASS_PUBLIC_TARGETED_INTAKE_AGGREGATES',
                      'model_proposals':6,'offline_oracle_passes':25,
                      'training_eligible':0,'private_rows_reproduced':False}))


if __name__=='__main__':main()
