#!/usr/bin/env python3
"""Summarize bounded local checks without mixing cohorts or claiming a score."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(attempt):
    directory=ROOT/f'docs/verification/cti-local-pilot-{attempt}'
    result=json.loads((directory/'result.json').read_text())
    rows=[json.loads(x) for x in (directory/'responses.jsonl').read_text().splitlines()]
    assert result['status']=='COMPLETED' and result['private_service_stopped']
    assert len(rows)==result['completed_records']==result['requested_records']
    return result,rows
base,rows=read(2); follow,additional=read(3)
assert len(rows)==24 and len({r['group'] for r in rows})==24
assert len(additional)==3 and {r['id'] for r in additional}<={r['id'] for r in rows if not r['reasoning_completed']}
assert rows[0]['prompt_tokens']==rows[0]['canonical_prompt_tokens']
assert additional[0]['prompt_tokens']==additional[0]['canonical_prompt_tokens']
log=ROOT/'.tools/cti-review/cti-local-pilot-2-ollama.log'
assert 'check_double_bos_eos' not in log.read_text()
ids={r['id'] for r in additional}
earlier={r['id']:r for r in rows}
paired=[{'id':r['id'],'initial_reasoning_complete':earlier[r['id']]['reasoning_completed'],
         'followup_reasoning_complete':r['reasoning_completed'],
         'initial_output_tokens':earlier[r['id']]['output_tokens'],
         'followup_output_tokens':r['output_tokens'],'followup_truncated':r['truncated']}
        for r in additional]
summary={'checked_at_utc':datetime.now(timezone.utc).isoformat(),
    'status':'COMPLETED_ENGINEERING_CHECKS_FORMAL_PROTOCOL_NOT_FROZEN',
    'official_test_rows':0,'domain_training_performed':False,
    'benchmark_score':False,'weight_sha256':base['weight_sha256'],
    'initial_two_record_issue':'Duplicated BOS retained and disclosed in attempt1; excluded from canonical transport evidence.',
    'canonical_bos_fix_verified':True,
    'full_mechanism_check':{'records':24,'output_budget':512,
        'reasoning_completed':sum(r['reasoning_completed'] for r in rows),
        'max_token_hits':sum(r['truncated'] for r in rows),
        'valid_format':base['native_faith_metrics']['format_count']['proper'],
        'strict_label_matches':sum(r['strict_correct'] for r in base['graded_records']),
        'elapsed_seconds':base['elapsed_seconds_including_setup'],
        'latency_seconds':base['latency_seconds']},
    'disclosed_followup_subset':{'records':3,'output_budget':1024,
        'reasoning_completed':sum(r['reasoning_completed'] for r in additional),
        'max_token_hits':sum(r['truncated'] for r in additional),
        'valid_format':follow['native_faith_metrics']['format_count']['proper'],
        'strict_label_matches':sum(r['strict_correct'] for r in follow['graded_records']),
        'elapsed_seconds':follow['elapsed_seconds_including_setup'],
        'pairs':paired},
    'all_private_services_reported_stopped':True,
    'limitations':['Synthetic, author-labelled inputs; no independent gold review.',
                   'Follow-up was chosen after initial truncations; not an independent held-out evaluation.',
                   'Do not replace 24-record results with a mixed 512/1024 result.',
                   '1024 tokens helped this subset; adequacy for all development inputs remains unverified.',
                   'Mac Q4 timings do not establish NVIDIA BF16 throughput or paper-score reproduction.']}
dest=ROOT/'docs/verification/cti-local-checks-summary.json'
dest.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
