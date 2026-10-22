"""Shared fail-closed data, native scorers and experiment receipts.

No command from any dataset/prediction is ever executed by this module.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / '.tools/benchkit'
ATHENA_SOURCE = ROOT / 'docs/verification/athenabench-2026-10-18/source'
TASKS = ('CKT', 'ATE', 'RCM', 'RMS', 'VSP', 'TAA')
MINI_COUNTS = dict(zip(TASKS, (300, 100, 200, 100, 200, 50)))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_jsonl(path):
    rows = []
    for num, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            raise ValueError(f'Blank record at {path}:{num}')
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError('Records must be JSON objects')
        rows.append(row)
    return rows


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows))


def verify_sources():
    report = json.loads((ROOT / 'docs/verification/benchkit-source-preparation.json').read_text())
    for entry in report['files']:
        path = (ROOT / entry['path']).resolve()
        if not path.is_relative_to(ARTIFACT.resolve()) or sha(path.read_bytes()) != entry['sha256']:
            raise ValueError('Pinned upstream artifact mismatch: ' + entry['path'])
    manifest = json.loads((ROOT / 'docs/verification/athenabench-2026-10-18/source-manifest.json').read_text())
    # The historical manifest has a distinct structure; verify only declared files.
    entries = manifest.get('files', [])
    if isinstance(entries, dict):
        entries = [dict(v, path=k) for k, v in entries.items()]
    for entry in entries:
        rel = entry.get('path', entry.get('file', ''))
        path = (ATHENA_SOURCE / rel).resolve()
        if not path.is_relative_to(ATHENA_SOURCE.resolve()):
            raise ValueError('Athena source path escapes pinned directory')
        if entry.get('sha256') and sha(path.read_bytes()) != entry['sha256']:
            raise ValueError('Athena pinned source mismatch')
    return report


def native_kali():
    verify_sources()
    path = ARTIFACT / 'kali/src/model_score.py'
    spec = importlib.util.spec_from_file_location('benchkit_native_kali', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def native_athena():
    verify_sources()
    sys.path.insert(0, str(ATHENA_SOURCE))
    from athena_eval.evaluate import score_record
    from athena_eval.answer_extractors import extract_answer
    return score_record, extract_answer


def kali_prompts(records, mode='unrestricted'):
    if mode != 'unrestricted':
        raise ValueError('Only unrestricted is frozen in initial adapter')
    verify_sources()
    sys.path.insert(0, str(ARTIFACT / 'kali/src'))
    from prompt_builder import build_prompts_and_labels
    prompts, labels = build_prompts_and_labels(records, mode, 20, {}, False, 0,
                                                candidate_seed=42, output_policy='strict')
    return {p.custom_id: p.messages for p in prompts}, {r['custom_id']: r for r in labels}


def unique_rows(rows, key='id'):
    ids = [r[key] for r in rows]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Duplicate, empty or non-string identifiers')
    return {r[key]: r for r in rows}


def validate_dataset(rows, split, benchmark):
    if not rows:
        raise ValueError('Empty dataset')
    unique_rows(rows)
    for row in rows:
        if row['split'] != split or row['benchmark'] != benchmark:
            raise ValueError('Split/benchmark mismatch')
        if row.get('official_test'):
            raise ValueError('Official test is not permitted in development loader')
        if row['training_eligible'] != (split == 'train'):
            raise ValueError('Training eligibility mismatch')
        if not row.get('group_id') or not row.get('source_url') or not row.get('quality'):
            raise ValueError('Missing provenance')
        if not row.get('messages') or not row.get('target'):
            raise ValueError('Missing messages or target')
        if any(m.get('role') not in {'system', 'user'} for m in row['messages']):
            raise ValueError('Input messages contain target/tool/assistant roles')
        if benchmark == 'athena' and row['task'] not in TASKS:
            raise ValueError('Invalid Athena task')
        if benchmark == 'kali' and row['task'] != 'unrestricted':
            raise ValueError('Unsupported Kali mode')
    return rows


def verify_isolation(pools):
    names = list(pools)
    for ix, a in enumerate(names):
        for b in names[ix + 1:]:
            for key in ('id', 'group_id', 'input_sha256'):
                left = {r[key] for r in pools[a]}
                right = {r[key] for r in pools[b]}
                if left & right:
                    raise ValueError(f'{a}/{b} overlap in {key}')
    return True


def load_manifest(path, required_split=None):
    path = Path(path).resolve()
    spec = json.loads(path.read_text())
    if spec.get('schema') != 'benchkit.dataset.v1':
        raise ValueError('Unsupported dataset manifest')
    if spec.get('official_test'):
        raise ValueError('Official test is protected; use separate final-evaluation process')
    pools = {}
    base = path.parent
    for split, item in spec['splits'].items():
        data = (base / item['file']).resolve()
        if not data.is_relative_to(base) or sha(data.read_bytes()) != item['sha256']:
            raise ValueError('Dataset path/checksum mismatch')
        rows = load_jsonl(data)
        if len(rows) != item['rows']:
            raise ValueError('Dataset count mismatch')
        pools[split] = validate_dataset(rows, split, spec['benchmark'])
    verify_isolation(pools)
    if required_split:
        if required_split not in pools:
            raise ValueError('Required split missing; no fallback permitted')
        return spec, pools[required_split]
    return spec, pools


def final_text(raw):
    if not isinstance(raw, str):
        raise ValueError('Response must be text')
    if '</think>' in raw:
        return raw.rsplit('</think>', 1)[1].strip()
    if '<think>' in raw:
        return ''
    return raw.strip()


def strict_option_values(label, prediction, scorer):
    """A separate diagnostic: compare GT-required value multisets; never replace native."""
    cmd = scorer.extract_command_from_output(prediction)
    if cmd == scorer.FORMAT_ERROR_TOKEN:
        return False
    optional = scorer.parse_optional_args(label.get('optional_args'))
    aliases = {a: key for key in optional for a in key.split('|')}

    def parse(text):
        tokens = shlex.split(text)
        groups = Counter()
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            flag, sep, value = tok.partition('=')
            if flag in aliases:
                key = aliases[flag]
                if optional[key] is not None:
                    if not sep:
                        i += 1
                        if i >= len(tokens):
                            raise ValueError('Missing option value')
                        value = tokens[i]
                else:
                    value = None
                groups[(key, value)] += 1
            i += 1
        return groups
    try:
        return bool(scorer.score_one(label, prediction)['exact_match']) and parse(cmd) == parse(label['ground_truth_command'])
    except ValueError:
        return False


def score_predictions(rows, predictions, benchmark, require_six=False):
    expected = unique_rows(rows)
    actual = unique_rows(predictions)
    if expected.keys() != actual.keys():
        raise ValueError('Prediction IDs missing/extra; silent subset scoring forbidden')
    if require_six and set(r['task'] for r in rows) != set(TASKS):
        raise ValueError('Six tasks required for Athena combined')
    grouped, details = {}, []
    if benchmark == 'athena':
        score_record, extract = native_athena()
        # TAA maps are public scoring resources, not test records.
        import csv
        maps = []
        for filename, key in [('aliases.csv', 'Alias'), ('related_groups.csv', 'RelatedGroup')]:
            result = {}
            p = ARTIFACT / 'athena/athena_eval/taa' / filename
            for r in csv.DictReader(p.open()):
                a, b = r['ThreatActor'].strip().lower(), r[key].strip().lower()
                result.setdefault(a, []).append(b)
                result.setdefault(b, []).append(a)
            maps.append(result)
        for identifier, r in expected.items():
            p = actual[identifier]
            raw = p.get('response', '')
            failed = bool(p.get('error')) or bool(p.get('truncated')) or not final_text(raw)
            answer = extract(r['task'], final_text(raw))
            value, success = score_record(r['task'], answer, r['target'], *maps)
            score = value.get('correct', 0) if isinstance(value, dict) else float(value)
            details.append({'id': identifier, 'task': r['task'], 'native_score': score,
                            'native_valid': bool(success), 'runtime_failed': failed,
                            'strict_score': 0.0 if failed or not success else score})
        for task in sorted({r['task'] for r in rows}):
            subset = [x for x in details if x['task'] == task]
            valid = [x for x in subset if x['native_valid']]
            avg = sum(x['native_score'] for x in valid) / len(valid) if valid else 0.0
            value = (1 - avg / 7.7) * 100 if task == 'VSP' else avg * 100
            grouped[task] = {'rows': len(subset), 'native_metric': value,
                             'native_valid_rows': len(valid),
                             'runtime_failed_rows': sum(x['runtime_failed'] for x in subset)}
            if task == 'VSP':
                grouped[task]['valid_only_MAE'] = avg if valid else None
                grouped[task]['coverage'] = len(valid) / len(subset)
            else:
                grouped[task]['all_requested_strict_metric'] = sum(x['strict_score'] for x in subset) / len(subset) * 100
        summary = {'tasks': grouped, 'combined_native': sum(v['native_metric'] for v in grouped.values()) / 6 if set(grouped) == set(TASKS) else None,
                   'warning': 'Native VSP excludes invalid outputs; inspect coverage. Not a benchmark score unless official full protocol is satisfied.'}
    elif benchmark == 'kali':
        scorer = native_kali()
        for identifier, r in expected.items():
            p = actual[identifier]
            raw = p.get('response', '')
            result = scorer.score_one(r['native_label'], raw)
            failed = bool(p.get('error')) or bool(p.get('truncated')) or not final_text(raw)
            details.append({'id': identifier, **result, 'runtime_failed': failed,
                            'strict_option_value_correct': float(not failed and strict_option_values(r['native_label'], raw, scorer))})
        summary = {k: sum(x[k] for x in details) / len(details) * 100 for k in
                   ['tool_score', 'optional_f1', 'positional_f1', 'total_score', 'exact_match', 'format_error', 'strict_option_value_correct']}
        summary['runtime_failed_rows'] = sum(x['runtime_failed'] for x in details)
        summary['all_requested_strict_exact'] = sum(x['exact_match'] for x in details if not x['runtime_failed']) / len(details) * 100
        summary['warning'] = 'Native exact/total may ignore incorrect option values; separate strict diagnostic is not official metric.'
    else:
        raise ValueError('Unknown benchmark')
    return {'schema': 'benchkit.score.v1', 'benchmark': benchmark, 'rows': len(rows),
            'summary': summary, 'details': details}


def encode_supervision(tokenizer, row, max_length=2048):
    """Mask input prefix using native full-chat offsets, without fabricated reasoning.

    A native generation prefix containing <think> can differ from gold final-only
    SFT; record this explicitly, never silently inject invented thoughts.
    """
    marker = 'BENCHKIT_TARGET_BOUNDARY_71963'
    if marker in row['target'] or any(marker in m['content'] for m in row['messages']):
        raise ValueError('Boundary marker collision')
    full = tokenizer.apply_chat_template(row['messages'] + [{'role': 'assistant', 'content': marker}], tokenize=False, add_generation_prompt=False)
    if full.count(marker) != 1:
        raise ValueError('Cannot identify assistant target boundary')
    prefix, suffix = full.split(marker)
    text = prefix + row['target'] + suffix
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids, offsets = encoded['input_ids'], encoded['offset_mapping']
    if len(ids) > max_length:
        raise ValueError('Sequence too long; silent truncation forbidden')
    boundary = len(prefix)
    # Do not supervise tokens crossing from the prompt into the answer.
    labels = [token if end > boundary and start >= boundary else -100 for token, (start, end) in zip(ids, offsets)]
    if not any(x != -100 for x in labels):
        raise ValueError('All target tokens masked')
    generation = tokenizer.apply_chat_template(row['messages'], tokenize=False, add_generation_prompt=True)
    return {'input_ids': ids, 'attention_mask': [1] * len(ids), 'labels': labels,
            'prompt_tokens': sum(x == -100 for x in labels),
            'native_generation_prefix_differs': generation != prefix}


def artifact_spec(path, rows):
    return {'file': Path(path).name, 'rows': len(rows), 'sha256': sha(Path(path).read_bytes()),
            'quality': dict(Counter(r['quality'] for r in rows))}


def row_fingerprint(messages):
    return sha(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode())


def load_tokenizer(alias):
    from transformers import AutoTokenizer
    # These checkpoints are Llama/Qwen, not Mistral. Preserve their pinned regex.
    # transformers 5 may otherwise warn for local configs lacking a version field.
    return AutoTokenizer.from_pretrained(ARTIFACT / 'models' / alias,
        local_files_only=True, trust_remote_code=False, fix_mistral_regex=False)
