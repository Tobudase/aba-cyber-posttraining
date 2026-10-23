#!/usr/bin/env python3
"""Build documented Kali task candidates, never execute reference commands.

This is an authored source-silver engineering set, not independently reviewed
gold, an official benchmark subset, or proof of unseen pretraining content.
"""
import argparse
from collections import Counter
import json
import shlex
import ssl
import urllib.request

from benchkit import (ROOT, ARTIFACT, artifact_spec, kali_prompts, load_jsonl,
                      native_kali, row_fingerprint, sha, strict_option_values,
                      validate_dataset, verify_isolation, write_json, write_jsonl)

REV = '0b5bf54c9e343f94e113874b98ff5de815780328'
DOC_REL = 'KaliBench_data/Kali_Tool_Subtools_UsageCode.jsonl'
DOC_SHA = '4515fc581d624652297344f036cd7f429e8002356956b7b528220097a60254cd'
URL = f'https://raw.githubusercontent.com/RISys-Lab/KaliBench/{REV}/{DOC_REL}'
# Entire package families are reserved before any model generation.
RESERVED_PACKAGES = {'llvm-defaults', 'libewf', 'samba', 'vim'}


def validate_command(task, documentation):
    """Literal option/arity validation is a check, not a semantic execution oracle."""
    tokens = shlex.split(task['command'])
    if not tokens or tokens[0] != task['tool']:
        raise ValueError('Tool does not match command')
    if any(t in {';', '|', '&&', '||', '>', '>>', '<'} for t in tokens):
        raise ValueError('Only simple, non-executed command strings in this pilot')
    options = task['optional_args']; aliases = {a: k for k in options for a in k.split('|')}
    observed = Counter(); positional = []; i = 1
    while i < len(tokens):
        token = tokens[i]; flag, sep, value = token.partition('=')
        if flag.startswith('-'):
            if flag not in aliases: raise ValueError('Undeclared option: ' + flag)
            key = aliases[flag]; expected = options[key]
            if flag not in documentation: raise ValueError('Option absent from source: ' + flag)
            if expected is not None:
                if not sep:
                    i += 1
                    if i >= len(tokens): raise ValueError('Missing option value')
                    value = tokens[i]
                if value != expected: raise ValueError('Wrong reference option value')
            elif sep: raise ValueError('Unexpected flag value')
            observed[key] += 1
        else:
            positional.append(token)
        i += 1
    if set(observed) != set(options) or any(n != 1 for n in observed.values()):
        raise ValueError('Reference options missing/duplicated')
    if positional != task['positional_args']: raise ValueError('Reference positionals mismatch')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--fetch-docs', action='store_true')
    args = p.parse_args()
    docpath = ARTIFACT / 'kali' / DOC_REL
    if not docpath.exists() and args.fetch_docs:
        ctx = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
        with urllib.request.urlopen(URL, context=ctx, timeout=40) as r: raw = r.read(12_000_001)
        if sha(raw) != DOC_SHA: raise ValueError('Unexpected pinned document bytes')
        docpath.parent.mkdir(parents=True, exist_ok=True); docpath.write_bytes(raw)
    if sha(docpath.read_bytes()) != DOC_SHA: raise ValueError('Pinned usage docs mismatch')
    docs = load_jsonl(docpath)
    if len(docs) != 2809: raise ValueError('Unexpected usage-document row count')
    taskpath = ROOT / 'configs/kali-domain-dev-v1.tasks.json'
    tasks = json.loads(taskpath.read_text())['tasks']
    train = load_jsonl(ARTIFACT / 'kali/KaliBench_data/kalibench_verified_train_3504.jsonl')
    screened = load_jsonl(ROOT / 'data/benchkit/kali-screened/train.jsonl')
    train_tools = Counter(r['native_label']['tool_name'] for r in screened)
    norm = lambda s: ' '.join(shlex.split(s))
    train_cmds = {norm(r['ground_truth_command']) for r in train}
    train_queries = {' '.join(r['query'].lower().split()) for r in train}
    raw_rows = []; annotations = {}; audit = []
    for task in tasks:
        matches = [d for d in docs if d['subtool'] == task['tool'] and
                   d['title'] == task['package'] and d['source_row'] == task['source_row']]
        if len(matches) != 1: raise ValueError('Ambiguous document row for ' + task['id'])
        doc = matches[0]; validate_command(task, doc['usage_code'])
        if norm(task['command']) in train_cmds or ' '.join(task['query'].lower().split()) in train_queries:
            raise ValueError('Exact TRAIN overlap: ' + task['id'])
        identifier = 'kali-docdev-v1-' + task['id']
        raw_rows.append({'custom_id': identifier, 'query': task['query'], 'tool_name': task['tool'],
            'ground_truth_command': task['command'], 'optional_args': task['optional_args'],
            'positional_args': task['positional_args']})
        annotations[identifier] = task
        audit.append({'id': identifier, 'tool': task['tool'], 'category': task['category'],
            'package': task['package'], 'source_row': task['source_row'],
            'usage_sha256': sha(doc['usage_code'].encode()),
            'option_names_present_in_source': True,
            'literal_command_arity_and_values_consistent': True,
            'screened_train_tool_rows': train_tools[task['tool']],
            'independent_semantic_review': 'PENDING', 'terminal_execution': 'NOT_PERFORMED'})
    prompts, labels = kali_prompts(raw_rows); pools = {'dev_search': [], 'dev_confirm': []}
    scorer = native_kali(); echo_failures = []
    for identifier, task in annotations.items():
        split = 'dev_confirm' if task['package'] in RESERVED_PACKAGES else 'dev_search'
        target = '<output>' + task['command'] + '</output>'
        row = {'id': identifier, 'benchmark': 'kali', 'task': 'unrestricted',
            'messages': prompts[identifier], 'target': target, 'native_label': labels[identifier],
            'group_id': 'kali-doc-package:' + task['package'], 'split': split,
            'training_eligible': False, 'official_test': False, 'self_authored': True,
            'source_url': URL, 'source_sha256': DOC_SHA,
            'source_row': task['source_row'], 'tool_package': task['package'],
            'category': task['category'], 'template_family': task['id'],
            'quality': 'AUTHORED_SOURCE_SILVER_PENDING_INDEPENDENT_REVIEW',
            'screened_train_tool_rows': train_tools[task['tool']],
            'input_sha256': row_fingerprint(prompts[identifier])}
        result = scorer.score_one(labels[identifier], target)
        if result['exact_match'] != 1 or not strict_option_values(labels[identifier], target, scorer):
            echo_failures.append({'id': identifier, 'native': result})
        pools[split].append(row)
    verify_isolation(pools)
    directory = ROOT / 'data/benchkit/kali-domain-dev-v1'; directory.mkdir(exist_ok=True)
    specs = {}
    for split, rows in pools.items():
        validate_dataset(rows, split, 'kali'); path = directory / (split + '.jsonl')
        write_jsonl(path, rows); specs[split] = artifact_spec(path, rows)
    limitations = [
        '48 authored tasks cover24tools/6localcategories, not the full936screened tools or23official dimensions.',
        'Two distinct task intents per tool; no filename-only variant multiplication.',
        'Queries explicitly name the intended tool; measures argument/task composition rather than unrestricted tool discovery.',
        'Split by entire parent package;12confirmation rows remain unqueried.',
        'Pinned usage docs are part of upstream benchmark material; checkpoint exposure to these docs is unknown.',
        'Exact TRAIN command/query exclusion is not semantic independence or proof of no official TEST overlap.',
        'Reference commands are static data, never executed; independent review and Linux task verification remain pending.',
        'Native-score self-consistency does not prove reference correctness; this is engineering source-silver only.',
        'Not approved as sole ABA candidate-selection objective or official result.']
    manifest = {'schema': 'benchkit.dataset.v1', 'benchmark': 'kali', 'official_test': False,
        'self_authored': True, 'splits': specs, 'task_config_sha256': sha(taskpath.read_bytes()),
        'usage_document_sha256': DOC_SHA, 'sufficient_for_ABA_selection': False, 'limitations': limitations}
    write_json(directory / 'manifest.json', manifest)
    report = {'status': 'DOC_GROUNDED_ENGINEERING_CANDIDATES_REVIEW_PENDING',
        'manifest_sha256': sha((directory / 'manifest.json').read_bytes()),
        'splits': {s: {'rows': len(v), 'tools': len({r['native_label']['tool_name'] for r in v}),
            'packages': len({r['tool_package'] for r in v}), 'category_counts': dict(Counter(r['category'] for r in v)),
            'known_train_tool_rows': sum(bool(r['screened_train_tool_rows']) for r in v)} for s, v in pools.items()},
        'source': {'url': URL, 'sha256': DOC_SHA, 'rows': len(docs)},
        'exact_train_overlap_rows': 0, 'native_gold_echo_failures': echo_failures,
        'commands_executed': 0, 'official_test_rows_read': 0, 'independent_review_complete': False,
        'task_audits': audit, 'limitations': limitations}
    write_json(ROOT / 'docs/verification/kali-domain-dev-preparation-2026-10-22.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'task_audits'}, indent=2))


if __name__ == '__main__': main()
