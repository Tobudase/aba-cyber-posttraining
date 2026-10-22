#!/usr/bin/env python3
"""Prepare actual external CTI pilot and Kali TRAIN-only manifests, plus fixtures."""
from collections import Counter
import json
from pathlib import Path

from benchkit import (ROOT, ARTIFACT, artifact_spec, kali_prompts, load_jsonl,
                      row_fingerprint, sha, validate_dataset, verify_isolation,
                      verify_sources, write_json, write_jsonl)
from cti_pilot_data import load_pilot


def emit(benchmark, pools, notes):
    directory = ROOT / 'data/benchkit' / benchmark
    directory.mkdir(parents=True, exist_ok=True)
    specs = {}
    for split, rows in pools.items():
        validate_dataset(rows, split, benchmark)
        p = directory / f'{split}.jsonl'
        write_jsonl(p, rows)
        specs[split] = artifact_spec(p, rows)
    verify_isolation(pools)
    manifest = {'schema': 'benchkit.dataset.v1', 'benchmark': benchmark,
                'official_test': False, 'splits': specs,
                'test_overlap_audit_complete': False, 'limitations': notes}
    write_json(directory / 'manifest.json', manifest)
    return manifest


def main():
    verify_sources()
    old, pools = load_pilot()
    athena = {}
    for split, rows in pools.items():
        athena[split] = []
        for r in rows:
            # Match the intended official task style; do not invent chain-of-thought.
            messages = [{'role': 'user', 'content':
                         'Analyze the following CVE description and map it to the appropriate CWE. '
                         'Ensure the last line of your response contains only the CWE ID.\n\n'
                         'CVE Description: ' + r['description']}]
            athena[split].append({'id': r['id'], 'benchmark': 'athena', 'task': 'RCM',
                'messages': messages, 'target': r['label'], 'group_id': r['group_id'],
                'split': split, 'training_eligible': split == 'train', 'official_test': False,
                'source_url': r['source_url'], 'source_sha256': r['source_sha256'],
                'quality': r['label_quality'], 'input_sha256': row_fingerprint(messages)})
    a = emit('athena', athena, old['limitations'] + ['Same frozen 47/16 pilot; not a full research train/dev set.'])
    native = load_jsonl(ARTIFACT / 'kali/KaliBench_data/kalibench_verified_train_3504.jsonl')
    if len(native) != 3504 or len({r['custom_id'] for r in native}) != 3504:
        raise ValueError('Kali TRAIN inventory mismatch')
    prompts, labels = kali_prompts(native)
    kali = []
    for r in native:
        identifier = r['custom_id']
        # Model already saw ALL official train: keep all as train, no fake held-out dev.
        messages = prompts[identifier]
        target = '<output>\n' + r['ground_truth_command'].strip() + '\n</output>'
        kali.append({'id': identifier, 'benchmark': 'kali', 'task': 'unrestricted',
            'messages': messages, 'target': target, 'native_label': labels[identifier],
            'group_id': 'tool:' + r['tool_name'].strip().lower(), 'split': 'train',
            'training_eligible': True, 'official_test': False,
            'source_url': 'https://github.com/RISys-Lab/KaliBench/blob/0b5bf54c9e343f94e113874b98ff5de815780328/KaliBench_data/kalibench_verified_train_3504.jsonl',
            'quality': 'OFFICIAL_TRAIN_PUBLISHER_LABEL_NOT_EXPERT_REAUDITED',
            'input_sha256': row_fingerprint(messages)})
    k = emit('kali', {'train': kali}, ['Official TRAIN only; RedSage-K already trained on all 3504 rows.',
            'No genuine external dev yet; ABA model selection must remain blocked.',
            'Generated commands are inert text, never executed.',
            'Model/data licensing review remains separate from public download accessibility.'])
    # A self-authored, harmless CLI fixture tests interfaces only, never reports benchmark accuracy.
    fixture = [
        {'custom_id': 'authored-wc-lines', 'query': 'Count lines in notes.txt using wc.',
         'tool_name': 'wc', 'ground_truth_command': 'wc -l notes.txt',
         'optional_args': {'--lines|-l': None}, 'positional_args': ['notes.txt']},
        {'custom_id': 'authored-head-lines', 'query': 'Print the first 5 lines of notes.txt.',
         'tool_name': 'head', 'ground_truth_command': 'head -n 5 notes.txt',
         'optional_args': {'--lines|-n': '5'}, 'positional_args': ['notes.txt']},
        {'custom_id': 'authored-printf-literal', 'query': 'Print hello followed by a newline.',
         'tool_name': 'printf', 'ground_truth_command': "printf 'hello\\n'",
         'optional_args': {}, 'positional_args': ['hello\\n']},
    ]
    pm, lm = kali_prompts(fixture)
    rows = [{'id': x['custom_id'], 'benchmark': 'kali', 'task': 'unrestricted',
             'messages': pm[x['custom_id']], 'target': '<output>' + x['ground_truth_command'] + '</output>',
             'native_label': lm[x['custom_id']], 'group_id': x['custom_id'], 'split': 'dev',
             'training_eligible': False, 'official_test': False, 'synthetic_only': True,
             'source_url': 'local:self-authored-engineering-fixture', 'quality': 'AUTHORED_INTERFACE_ONLY',
             'input_sha256': row_fingerprint(pm[x['custom_id']])} for x in fixture]
    directory = ROOT / 'data/benchkit/kali-fixture'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'dev.jsonl'
    write_jsonl(path, rows)
    write_json(directory / 'manifest.json', {'schema': 'benchkit.dataset.v1', 'benchmark': 'kali',
        'official_test': False, 'synthetic_only': True, 'splits': {'dev': artifact_spec(path, rows)},
        'limitations': ['Three harmless authored CLI cases; not cybersecurity research validation.']})
    report = {'status': 'PREPARED_WITH_RESEARCH_DATA_GAPS', 'athena_splits': {s: x['rows'] for s, x in a['splits'].items()},
              'kali_splits': {s: x['rows'] for s, x in k['splits'].items()},
              'kali_distinct_tools': len({r['tool_name'] for r in native}),
              'kali_fixture_rows': len(rows), 'official_test_files_downloaded': 0,
              'kali_external_dev_ready': False, 'formal_training_started': False}
    write_json(ROOT / 'docs/verification/benchkit-data-preparation.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
