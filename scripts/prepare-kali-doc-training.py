#!/usr/bin/env python3
"""Source-check new authored training rows and audit protected-dev boundaries."""
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
import re
import shlex

from benchkit import (ROOT, ARTIFACT, artifact_spec, kali_prompts, load_jsonl,
                      native_kali, row_fingerprint, sha, strict_option_values,
                      validate_dataset, write_json, write_jsonl)
from kali_doc_training_tasks import recipes

loader = importlib.util.spec_from_file_location('domain_prep', ROOT / 'scripts/prepare-kali-domain-dev.py')
domain = importlib.util.module_from_spec(loader); loader.loader.exec_module(domain)


def operation_signature(tool, optional, positional):
    # Ignore values/filenames and alias/key ordering: changing only these must
    # not turn an existing development operation into a new training family.
    canonical = lambda k: tuple(sorted(k.split('|')))
    return tool, tuple(sorted(canonical(k) for k in optional)), len(positional)


def check_boundary(task, blocked_signatures):
    if task['package'] in domain.RESERVED_PACKAGES:
        raise ValueError('Reserved confirmation package cannot enter new TRAIN')
    if operation_signature(task['tool'], task['optional_args'], task['positional_args']) in blocked_signatures:
        raise ValueError('Training task repeats a protected development operation')


def main():
    source_path = ARTIFACT / 'kali' / domain.DOC_REL
    if sha(source_path.read_bytes()) != domain.DOC_SHA: raise ValueError('Pinned documentation changed')
    docs = load_jsonl(source_path)
    # Boundary auditor only: protected body reads are for static exclusion/review,
    # not generation, optimization, candidate ranking, or confirmation scoring.
    protected_paths = [ROOT / f'data/benchkit/{name}/{split}.jsonl'
        for name in ['kali-domain-dev-v1', 'kali-external-dev'] for split in ['dev_search', 'dev_confirm']]
    protected = [r for p in protected_paths for r in load_jsonl(p)]
    blocked = {operation_signature(r['native_label']['tool_name'], r['native_label']['optional_args'],
                                   r['native_label']['positional_args']) for r in protected}
    norm = lambda s: ' '.join(shlex.split(s))
    commands = {norm(r['native_label']['ground_truth_command']) for r in protected}
    queries = {' '.join(r['native_label']['query'].lower().split()) for r in protected}
    raw_train = load_jsonl(ARTIFACT / 'kali/KaliBench_data/kalibench_verified_train_3504.jsonl')
    original_commands = {norm(r['ground_truth_command']) for r in raw_train}
    original_queries = {' '.join(r['query'].lower().split()) for r in raw_train}
    generated = []; reviews = []; duplicates = 0; seen = set()
    for recipe in recipes():
        matches = [d for d in docs if d['subtool'] == recipe['tool']]
        # readpe is duplicated under legacy pev; use the explicit readpe package.
        matches = [d for d in matches if d['title'] != 'pev']
        if len(matches) != 1: raise ValueError('Ambiguous tool documentation: ' + recipe['tool'])
        doc = matches[0]; help_text = doc['usage_code'].split('```', 1)[0]
        for variant in [0, 1]:
            values = dict(f='train_' + recipe['family'].replace('-', '_') + '_' + ('a' if variant == 0 else 'b'),
                n=str([17, 29][variant]), offset=['0x6000', '0xA000'][variant], index=str(variant + 2),
                class_name=['RecordDecoder', 'PacketReader'][variant], rule=['AuditRecordRule', 'AuditPacketRule'][variant],
                threads=str(variant + 2), timeout=str([11, 23][variant]), page=str([3, 9][variant]),
                segment=['pagesize', 'imagesize'][variant], snaplen=str([96, 160][variant]),
                minlen=str([7, 9][variant]), maxlen=str([55, 77][variant]), sector=str([2048, 8192][variant]),
                inode=str([17, 73][variant]), seconds=str([120, 240][variant]), level=str([2, 4][variant]),
                bytes=str([1024, 4096][variant]))
            fmt = lambda s: s.format(**values)
            task = dict(recipe, package=doc['title'], source_row=doc['source_row'],
                query=fmt(recipe['query']), command=fmt(recipe['command']),
                optional_args={k: fmt(v) if v is not None else None for k, v in recipe['optional_args'].items()},
                positional_args=[fmt(v) for v in recipe['positional_args']])
            domain.validate_command(task, help_text)
            for key in task['optional_args']:
                for alias in key.split('|'):
                    if not re.search(r'(?<![\w-])' + re.escape(alias) + r'(?![\w-])', help_text):
                        raise ValueError('Alias lacks an exact source witness: ' + alias)
            check_boundary(task, blocked)
            q = ' '.join(task['query'].lower().split()); c = norm(task['command'])
            if q in queries or c in commands: raise ValueError('Protected development text overlap')
            if q in original_queries or c in original_commands: raise ValueError('Exact original TRAIN overlap')
            if (q, c) in seen:
                duplicates += 1; continue
            seen.add((q, c))
            identifier = f'kali-doc-train-v1-{recipe["family"]}-{variant + 1}'
            generated.append({'custom_id': identifier, 'query': task['query'], 'tool_name': task['tool'],
                'ground_truth_command': task['command'], 'optional_args': task['optional_args'],
                'positional_args': task['positional_args']})
            reviews.append({'id': identifier, 'family': recipe['family'], 'tool': task['tool'], 'package': task['package'],
                'source_row': task['source_row'], 'usage_sha256': sha(help_text.encode()),
                'AI_source_assisted_semantic_rationale': recipe['semantic_review'],
                'source_options_aliases_values_positionals_checked': True,
                'independent_expert_review': False, 'terminal_execution': False})
    prompts, labels = kali_prompts(generated); metadata = {r['id']: r for r in reviews}
    scorer = native_kali(); rows = []
    for item in generated:
        identifier = item['custom_id']; m = metadata[identifier]
        target = '<output>' + item['ground_truth_command'] + '</output>'
        if scorer.score_one(labels[identifier], target)['exact_match'] != 1 or not strict_option_values(labels[identifier], target, scorer):
            raise ValueError('Native roundtrip mismatch; do not silently relabel: ' + identifier)
        rows.append({'id': identifier, 'benchmark': 'kali', 'task': 'unrestricted', 'split': 'train',
            'training_eligible': True, 'official_test': False, 'self_authored': True,
            'messages': prompts[identifier], 'target': target, 'native_label': labels[identifier],
            'group_id': 'train-only-intent:' + m['family'], 'template_family': m['family'], 'tool_package': m['package'],
            'source_row': m['source_row'], 'source_url': domain.URL, 'source_sha256': domain.DOC_SHA,
            'quality': 'AI_DOC_REVIEWED_SOURCE_SILVER_NOT_EXPERT_GOLD', 'input_sha256': row_fingerprint(prompts[identifier])})
    validate_dataset(rows, 'train', 'kali')
    directory = ROOT / 'data/benchkit/kali-doc-train-v1'; directory.mkdir(exist_ok=True)
    write_jsonl(directory / 'train.jsonl', rows)
    limitations = ['AI-authored and source-assisted reviewed; not independently expert-reviewed or terminal-verified.',
        'Two scenarios per intent are correlated; does not establish108independent task skills.',
        'Known tools/packages overlap search-dev, but operation signatures, query/command text and authored scenarios are excluded.',
        'Source docs may have been seen in original checkpoint training; new authored rows do not prove unseen tool knowledge.',
        'No confirmation/official test inference or optimization; separate boundary auditor reads authored protected rows only for exclusion.',
        'All commands remain inert strings. Fixed local source-silver pilot, not actual ABA or official benchmark validation.']
    manifest = {'schema': 'benchkit.dataset.v1', 'benchmark': 'kali', 'official_test': False,
        'splits': {'train': artifact_spec(directory / 'train.jsonl', rows)}, 'usage_document_sha256': domain.DOC_SHA,
        'recipe_source_sha256': sha((ROOT / 'scripts/kali_doc_training_tasks.py').read_bytes()), 'limitations': limitations}
    write_json(directory / 'manifest.json', manifest)
    report = {'status': 'SOURCE_SILVER_READY_FOR_FIXED_LOCAL_ENGINEERING_PILOT', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'rows': len(rows), 'families': len({r['template_family'] for r in rows}),
        'tools': dict(Counter(r['native_label']['tool_name'] for r in rows)),
        'packages': sorted({r['tool_package'] for r in rows}), 'identical_variant_pairs_deduplicated': duplicates,
        'train_manifest_sha256': sha((directory / 'manifest.json').read_bytes()),
        'protected_artifacts': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in protected_paths},
        'protected_operation_signature_overlap': 0, 'protected_query_command_overlap': 0,
        'reserved_confirmation_package_overlap': 0, 'exact_original_train_overlap': 0,
        'native_gold_echo_failures': 0, 'commands_executed': 0, 'confirmation_rows_queried': 0,
        'official_test_rows_read': 0, 'independent_expert_review': False, 'reviews': reviews, 'limitations': limitations}
    write_json(ROOT / 'docs/verification/kali-doc-training-preparation-2026-10-22.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'reviews'}, indent=2))


if __name__ == '__main__': main()
