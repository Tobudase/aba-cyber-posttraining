#!/usr/bin/env python3
"""Aggregate a completed confirmation's unsupported cases without exporting rows."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'docs/verification/kali-bf16-confirmation-2026-10-26'


def read(name):
    return json.loads((D / name).read_text())


def digest(name):
    return sha256((D / name).read_bytes()).hexdigest()


def main():
    source = read('semantic-input-private.json')
    result = read('semantic-results.json')
    host = read('semantic-host-run.json')
    summary = read('summary.json')
    assert source['records'] and len(source['records']) == len(result['records']) == 144
    assert digest('semantic-input-private.json') == host['semantic_payload_sha256']
    assert host['status'] == 'COLLECTED' and result['status'] == 'COMPLETE'
    assert summary['confirmation_gate']['passes_confirmation_gate'] is False

    before = {(r['arm'], r['row']['id']): r for r in source['records']}
    after = {(r['arm'], r['id']): r for r in result['records']}
    assert len(before) == len(after) == 144 and before.keys() == after.keys()
    reason = {}
    by_tool = {}
    status = {}
    for arm in ('base', 'sft'):
        rows = [r for (a, _), r in before.items() if a == arm]
        assert len(rows) == 72
        reason[arm] = dict(sorted(Counter(
            r['pre_review'].get('reason', 'REVIEWED') for r in rows).items()))
        by_tool[arm] = dict(sorted(Counter(
            r['row']['tool'] for r in rows
            if r['pre_review']['status'] == 'UNSUPPORTED_NOT_EXECUTED').items()))
        unknown = [r for r in rows if r['pre_review']['status'] == 'UNSUPPORTED_NOT_EXECUTED']
        assert len(unknown) == summary['CONFIRMATION'][arm]['unsupported']
        assert all(after[(arm, r['row']['id'])]['unsupported'] and
                   not after[(arm, r['row']['id'])]['executed'] for r in unknown)
        status[arm] = {'rows': len(rows), 'unsupported_not_executed': len(unknown),
                       'reviewed': len(rows) - len(unknown),
                       'verified_correct': summary['CONFIRMATION'][arm]['correct']}

    base = {i: r for (arm, i), r in after.items() if arm == 'base'}
    sft = {i: r for (arm, i), r in after.items() if arm == 'sft'}
    assert base.keys() == sft.keys()
    transitions = Counter()
    for i, r in base.items():
        if not r['unsupported']:
            continue
        x = sft[i]
        category = 'sft_verified_correct' if x['correct'] else (
            'sft_unsupported' if x['unsupported'] else 'sft_other_not_correct')
        transitions[category] += 1
    assert sum(transitions.values()) == 47
    assert summary['paired']['new_verified_passes'] == 41
    audit = {
        'status': 'POSTHOC_DIAGNOSTIC_ONLY',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'private_input_sha256': digest('semantic-input-private.json'),
        'private_result_sha256': digest('semantic-results.json'),
        'predeclared_summary_sha256': digest('summary.json'),
        'model_calls': 0, 'optimizer_steps': 0, 'official_test_calls': 0,
        'arms': status, 'review_reason_counts': reason,
        'unsupported_by_tool': by_tool,
        'base_unsupported_to_sft': dict(sorted(transitions.items())),
        'gate_recomputed_or_changed': False,
        'candidate_promoted': False,
        'interpretation': (
            'Unsupported means the allowlisted reviewer did not execute the command. '
            'Its explicit_constraint_failure flag is set automatically by the reviewer '
            'and does not prove the command would fail its task. The 36 transitions '
            'from base-unsupported to SFT-verified cannot be called 36 confirmed gains.'),
        'private_commands_or_task_ids_released': False,
    }
    out = D / 'posthoc-unsupported-audit.json'
    out.write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'status': audit['status'], 'base_unsupported': 47,
                      'sft_unsupported': 6, 'transitions': audit['base_unsupported_to_sft']}))


if __name__ == '__main__':
    main()
