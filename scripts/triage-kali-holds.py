#!/usr/bin/env python3
"""Explain128 native gold-roundtrip holds with static schema/parser diagnostics.

Dataset commands are strings passed ONLY to shlex/native scoring, never a shell.
These categories are observed incompatibilities, not independent semantic verdicts.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import re
import shlex

from benchkit import ROOT, load_jsonl, native_kali, sha, write_json


def diagnose(label, scorer):
    command = label['ground_truth_command']
    reply = '<output>' + command + '</output>'
    native = scorer.score_one(label, reply)
    optional = scorer.parse_optional_args(label.get('optional_args'))
    declared_pos = scorer.parse_positional_args(label.get('positional_args'))
    flags = scorer.get_flags_with_values(optional)
    parsed_tool, parsed_options, parsed_pos = scorer.parse_command(command, flags)
    features = []
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = []
        features.append('UNBALANCED_SHELL_QUOTING')
    if label['tool_name'] != parsed_tool:
        features.append('METADATA_TOOL_DIFFERS_FROM_EXECUTABLE')
        if '/' in label['tool_name']: features.append('PACKAGE_QUALIFIED_TOOL_NAME')
        if parsed_tool in {'python', 'python2', 'python3', 'java', 'perl', 'ruby', 'bash', 'sh'}:
            features.append('INTERPRETER_OR_LAUNCHER_WRAPPER')
    if any(t in {'|', '||', '&&', ';', '&'} or re.match(r'^\d*(?:>>?|<<|[<>]&)', t) for t in tokens):
        features.append('SHELL_COMPOSITION_OR_REDIRECTION')
    if any('[' in key or ']' in key for key in optional):
        features.append('MANPAGE_OPTION_GRAMMAR_NOT_EXPANDED')
    if any(key.startswith('+') or key.startswith('/') for key in optional):
        features.append('NON_DASH_OPTION_PREFIX')
    if any(v is not None and isinstance(v, str) and v.startswith('-') for v in optional.values()):
        features.append('OPTION_VALUE_STARTS_WITH_DASH')
    if any(isinstance(v, list) or isinstance(v, tuple) for v in optional.values()):
        features.append('LIST_VALUED_OR_REPEATED_OPTION_SCHEMA')
    if any(isinstance(v, str) and len(v.split()) > 1 for v in optional.values()):
        features.append('MULTIWORD_OPTION_VALUE_SCHEMA')
    if any(count > 1 for count in Counter(parsed_options).values()):
        features.append('REPEATED_FLAG_COUNT_VS_ALIAS_GROUP_COUNT')
    aliases = {a for key in optional for a in key.split('|')}
    unexplained = sorted(set(parsed_options) - aliases)
    if unexplained:
        features.append('COMMAND_FLAGS_NOT_IN_DECLARED_OPTION_SCHEMA')
    if parsed_pos != declared_pos:
        features.append('PARSED_POSITIONALS_DIFFER_FROM_DECLARED_SCHEMA')
        if len(tokens) > 1 and not tokens[1].startswith(('-', '+', '/')) and tokens[1] not in declared_pos:
            features.append('SUBCOMMAND_OR_ACTION_IN_POSITIONAL_PARSE')
        if '\\' in command:
            features.append('SHELL_BACKSLASH_TOKENIZATION')
    priority = ['METADATA_TOOL_DIFFERS_FROM_EXECUTABLE', 'SHELL_COMPOSITION_OR_REDIRECTION',
        'MANPAGE_OPTION_GRAMMAR_NOT_EXPANDED', 'NON_DASH_OPTION_PREFIX', 'OPTION_VALUE_STARTS_WITH_DASH',
        'LIST_VALUED_OR_REPEATED_OPTION_SCHEMA', 'MULTIWORD_OPTION_VALUE_SCHEMA',
        'REPEATED_FLAG_COUNT_VS_ALIAS_GROUP_COUNT', 'COMMAND_FLAGS_NOT_IN_DECLARED_OPTION_SCHEMA',
        'SUBCOMMAND_OR_ACTION_IN_POSITIONAL_PARSE', 'PARSED_POSITIONALS_DIFFER_FROM_DECLARED_SCHEMA',
        'UNBALANCED_SHELL_QUOTING']
    primary = next((x for x in priority if x in features), 'REQUIRES_MANUAL_SCHEMA_REVIEW')
    return {'primary_bucket': primary, 'features': features,
        'metadata_tool': label['tool_name'], 'parsed_executable': parsed_tool,
        'declared_positionals': declared_pos, 'native_parsed_positionals': parsed_pos,
        'unexplained_parsed_flags': unexplained,
        'native_metrics': {k: native[k] for k in ['tool_score', 'optional_f1', 'positional_f1', 'total_score', 'exact_match']},
        'training_eligible': False, 'disposition': 'KEEP_HOLD_NO_AUTOMATIC_RELABEL'}


def main():
    path = ROOT / 'data/benchkit/kali-screened/hold.jsonl'
    rows = load_jsonl(path)
    if len(rows) != 128: raise ValueError('Expected frozen128-row hold inventory')
    scorer = native_kali()
    records = [{'id': r['id'], 'source_row_sha256': sha(json.dumps(r['native_label'], sort_keys=True).encode()),
                **diagnose(r['native_label'], scorer)} for r in rows]
    if any(r['native_metrics']['total_score'] == 1 and r['native_metrics']['exact_match'] == 1 for r in records):
        raise ValueError('Hold record now scores perfectly; source/scorer version changed')
    # Safe authored unit fixtures cover several mechanisms independently of official rows.
    fixtures = [
        ('duplicate-flag', {'tool_name': 'grep', 'ground_truth_command': 'grep -n -n ERROR report.log',
             'optional_args': {'-n': None}, 'positional_args': ['ERROR', 'report.log']}),
        ('negative-value', {'tool_name': 'demo', 'ground_truth_command': 'demo --offset -1 report.txt',
             'optional_args': {'--offset': '-1'}, 'positional_args': ['report.txt']}),
        ('action-not-listed', {'tool_name': 'demo', 'ground_truth_command': 'demo inspect report.txt',
             'optional_args': {}, 'positional_args': ['report.txt']}),
        ('qualified-tool', {'tool_name': 'package/tool', 'ground_truth_command': 'tool report.txt',
             'optional_args': {}, 'positional_args': ['report.txt']}),
        ('slash-option', {'tool_name': 'demo', 'ground_truth_command': 'demo /out report.txt',
             'optional_args': {'/out': None}, 'positional_args': ['report.txt']}),
    ]
    reproduced = [{'name': name, 'label': label, 'diagnosis': diagnose(label, scorer)} for name, label in fixtures]
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'ALL128_STATICALLY_TRIAGED_NO_SOURCE_EDITS', 'hold_sha256': sha(path.read_bytes()),
        'rows': len(records), 'primary_bucket_counts': dict(Counter(r['primary_bucket'] for r in records)),
        'feature_counts_nonexclusive': dict(Counter(f for r in records for f in r['features'])),
        'native_exact_failed_rows': sum(r['native_metrics']['exact_match'] != 1 for r in records),
        'authored_reproductions': reproduced, 'records': records,
        'commands_executed': 0, 'official_test_rows_used': 0, 'source_labels_modified': False,
        'limitations': ['Static parser/schema incompatibility is not proof a command is semantically valid or a label wrong.',
                       'Primary buckets use explicit precedence; multiple causes can coexist.',
                       'All128remain held; no rows restored solely to improve native metrics.']}
    write_json(ROOT / 'docs/verification/kali-hold-triage.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ['records', 'authored_reproductions']}, indent=2))


if __name__ == '__main__': main()
