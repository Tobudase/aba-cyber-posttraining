#!/usr/bin/env python3
"""Validate observable agent JSONL records and reject cross-split training data."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
HEX = re.compile(r'^[0-9a-f]{64}$')


def validate_record(record, tasks, training_ready=False):
    errors = []
    required = ['schema_version', 'run_id', 'task_id', 'project_name', 'split', 'difficulty',
                'model', 'messages', 'source_versions', 'verification']
    if not isinstance(record, dict):
        return ['Record must be an object']
    if any(key not in record for key in required):
        return ['Missing required fields']
    task = tasks.get(record['task_id'])
    if not task:
        errors.append('Unknown task ID')
    elif record['split'] != task['split'] or record['project_name'] != task['project_name']:
        errors.append('Task/project/split mismatch')
    if record['schema_version'] != 1:
        errors.append('Unsupported schema version')
    if not isinstance(record['run_id'], str) or not record['run_id']:
        errors.append('Missing run ID')
    if record['difficulty'] not in ['level0', 'level1', 'level2', 'level3']:
        errors.append('Unknown difficulty')
    for section, keys in [('model', ['id', 'revision']), ('source_versions', ['cybergym_commit', 'dataset_revision', 'prompt_sha256', 'scaffold_commit'])]:
        obj = record[section]
        if not isinstance(obj, dict) or not all(isinstance(obj.get(key), str) and obj[key] for key in keys):
            errors.append('Missing provenance in ' + section)
    for key in ['hidden_chain_of_thought', 'api_key', 'authorization', 'reference_poc']:
        if key in record:
            errors.append('Disallowed credential/reference/hidden field')
    messages = record['messages']
    pending = set()
    seen = set()
    if not isinstance(messages, list) or not messages:
        errors.append('Messages must be a non-empty list')
        messages = []
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in ['system', 'user', 'assistant', 'tool']:
            errors.append('Invalid visible message')
            continue
        role = message['role']
        if message.get('content') is not None and not isinstance(message['content'], str):
            errors.append('This schema requires text content or null')
        if role == 'tool':
            call_id = message.get('tool_call_id')
            if call_id not in pending:
                errors.append('Tool result has no pending call')
            else:
                pending.remove(call_id)
        elif pending:
            errors.append('New message before pending tool results completed')
        calls = message.get('tool_calls', [])
        if not isinstance(calls, list) or (calls and role != 'assistant'):
            errors.append('Tool calls must be an assistant list')
            continue
        for call in calls:
            try:
                call_id = call['id']
                function = call['function']
                if not isinstance(call_id, str) or not call_id or call_id in seen or call.get('type') != 'function':
                    raise ValueError
                if not isinstance(function['name'], str) or not function['name']:
                    raise ValueError
                if not isinstance(json.loads(function['arguments']), dict):
                    raise ValueError
                pending.add(call_id)
                seen.add(call_id)
            except (KeyError, TypeError, ValueError):
                errors.append('Malformed/duplicate tool call')
    if pending:
        errors.append('Unresolved tool calls')
    verification = record['verification']
    if not isinstance(verification, dict) or verification.get('status') not in ['success', 'task_failure', 'infra_failure', 'not_run']:
        errors.append('Invalid verification status')
    if training_ready:
        if record['split'] != 'train':
            errors.append('Only train split may enter SFT export')
        if not isinstance(verification, dict) or verification.get('status') != 'success':
            errors.append('Success-only SFT requires verified final submission')
        else:
            vul, fix = verification.get('vul_exit_code'), verification.get('fix_exit_code')
            if type(vul) is not int or vul in [0, 300] or type(fix) is not int or fix != 0:
                errors.append('Final submission lacks valid vulnerable/patched verification')
        final = record.get('final_submission', {})
        path = final.get('relative_path', '') if isinstance(final, dict) else ''
        if not path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts:
            errors.append('Invalid final submission relative path')
        if not isinstance(final, dict) or not HEX.fullmatch(str(final.get('sha256', ''))) or final.get('selected_for_final') is not True:
            errors.append('Missing final selected artifact/hash')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path)
    parser.add_argument('--splits', type=Path, default=ROOT / 'data/manifests/splits-draft')
    parser.add_argument('--training-ready', action='store_true', help='Require FROZEN split and success-only train records')
    args = parser.parse_args()
    policy_path = ROOT / 'configs/evaluation-policy.json'
    if args.training_ready and policy_path.is_file() and json.loads(policy_path.read_text()).get('official_tasks_are_evaluation_only'):
        parser.error('Training export disabled for official CyberGym task records by Han instruction. External train/validation intake is required; changing an old split to FROZEN is insufficient.')
    manifest = json.loads((args.splits / 'manifest.json').read_text())
    if args.training_ready and manifest.get('status') != 'FROZEN':
        parser.error('Training export blocked: splits are not FROZEN after review')
    tasks = {}
    for split in ['train', 'dev', 'test', 'infra_only']:
        raw = (args.splits / f'{split}.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['file_sha256'][split]:
            parser.error('Split file hash mismatch')
        for row in json.loads(raw):
            if row['task_id'] in tasks:
                parser.error('Duplicate task across splits')
            tasks[row['task_id']] = row
    count, failures, seen = 0, [], set()
    with args.jsonl.open() as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            count += 1
            try:
                record = json.loads(line)
                errors = validate_record(record, tasks, args.training_ready)
                if isinstance(record, dict):
                    identity = (record.get('run_id'), record.get('task_id'))
                    if identity in seen:
                        errors.append('Duplicate run/task record')
                    seen.add(identity)
            except (ValueError, TypeError):
                errors = ['Invalid JSON or field types']
            if errors:
                failures.append({'line': number, 'errors': sorted(set(errors))})
    if count == 0:
        failures.append({'line': 0, 'errors': ['No records; empty data cannot pass']})
    print(json.dumps({'records': count, 'invalid_records': len(failures), 'errors': failures,
                      'training_ready_check': args.training_ready}, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
