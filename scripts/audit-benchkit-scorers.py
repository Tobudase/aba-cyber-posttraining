#!/usr/bin/env python3
"""Run upstream scorers on authored cases and TRAIN gold echoes; never run CLI commands."""
from datetime import datetime, timezone
import json

from benchkit import (ROOT, ARTIFACT, load_jsonl, native_kali,
                      score_predictions, strict_option_values, write_json)


def main():
    scorer = native_kali()
    head = {'tool_name': 'head', 'ground_truth_command': 'head -n 5 notes.txt',
            'optional_args': {'--lines|-n': '5'}, 'positional_args': ['notes.txt']}
    cases = []
    for name, command in [('correct', 'head -n 5 notes.txt'), ('wrong_value', 'head -n 99 notes.txt'),
                          ('wrong_alias_value', 'head --lines=99 notes.txt'),
                          ('missing_option_value', 'head -n notes.txt'), ('wrong_filename', 'head -n 5 other.txt')]:
        reply = '<output>' + command + '</output>'
        cases.append({'name': name, 'label': head, 'response': reply,
                      'native': scorer.score_one(head, reply),
                      'strict_option_value_correct': strict_option_values(head, reply, scorer)})
    if cases[1]['native']['exact_match'] != 1 or cases[1]['strict_option_value_correct']:
        raise ValueError('Expected pinned native boundary behavior changed')
    data = load_jsonl(ARTIFACT / 'kali/KaliBench_data/kalibench_verified_train_3504.jsonl')
    failures = []
    for r in data:
        score = scorer.score_one(r, '<output>' + r['ground_truth_command'] + '</output>')
        if score['exact_match'] != 1 or score['total_score'] != 1:
            failures.append({'id': r['custom_id'], 'native': {k: score[k] for k in ['tool_score', 'optional_f1', 'positional_f1', 'exact_match', 'total_score']}})
    vector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'
    fixtures = [{'id': task, 'task': task, 'target': answer} for task, answer in
                [('CKT', 'A'), ('ATE', 'T1059.001'), ('RCM', 'CWE-79'), ('RMS', 'M1030'), ('VSP', vector), ('TAA', 'AuthoredActor')]]
    predictions = [{'id': x['id'], 'response': x['target']} for x in fixtures]
    good = score_predictions(fixtures, predictions, 'athena', require_six=True)
    invalid = score_predictions([fixtures[4]], [{'id': 'VSP', 'response': 'not a vector'}], 'athena')
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'AUDIT_COMPLETE_NATIVE_SCORING_LIMITATIONS_CONFIRMED',
        'kali_authored_cases': cases, 'kali_train_gold_echo_rows': len(data),
        'kali_train_gold_echo_nonperfect_rows': len(failures), 'kali_train_gold_echo_failures': failures,
        'athena_authored_six_task_summary': good['summary'],
        'athena_invalid_vsp_summary': invalid['summary'],
        'commands_executed': 0, 'model_generation_calls': 0, 'official_test_files_downloaded': 0,
        'published_scores_proven_affected': False,
        'warning': 'These are scorer/interface audits, not model baseline results. Strict option-value diagnostic is separately named, not a silent official scorer patch.'}
    write_json(ROOT / 'docs/verification/benchkit-scorer-audit.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ['kali_authored_cases', 'kali_train_gold_echo_failures']}, indent=2))


if __name__ == '__main__':
    main()
