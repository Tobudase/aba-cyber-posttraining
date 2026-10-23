#!/usr/bin/env python3
"""Audit all108 saved domain outputs and optionally replay8diagnostic cases/arm.

Outcome-stratified replay checks reproducibility, not independent validity or
generalization. No official/confirmation inference, new training or command execution.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import re
import signal
import time

from benchkit import (ROOT, final_text, load_jsonl, load_manifest, load_tokenizer,
                      native_kali, sha, strict_option_values, write_json, write_jsonl)
from kali_prompt_policy import generation_prompt
from kali_decode_policy import audit_stream_text


def file_sha(path):
    import hashlib
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(8 * 1024**2), b''): h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--execute', action='store_true')
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic(); native = load_tokenizer('redsage'); scorer = native_kali()
    manifest = ROOT / 'data/benchkit/kali-domain-dev-v1/manifest.json'
    spec, rows = load_manifest(manifest, 'dev_search'); by_id = {r['id']: r for r in rows}
    report = {'status': 'AUDITING', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'official_test_rows': 0, 'confirmation_rows_queried': 0, 'new_training_steps': 0,
        'commands_executed': 0, 'ABA_executed': False, 'fresh_generation_calls': 0,
        'purpose': 'Artifact/metric consistency and selected-case deterministic reproducibility; not independent label validation'}
    directories = {'aligned': 'kali-domain-e0-2026-10-22',
        'native': 'kali-domain-e0-native-resumed-2026-10-22',
        'tool_help': 'kali-domain-e0-dochelp-2026-10-22'}
    root = ROOT / 'docs/verification'; frozen = {}; originals = {}; prompts = {}; scores = {}; audits = {}
    source = ROOT / '.tools/benchkit/kali/KaliBench_data/Kali_Tool_Subtools_UsageCode.jsonl'
    if file_sha(source) != spec['usage_document_sha256']: raise ValueError('Documentation changed')
    docs = load_jsonl(source)
    conversion_path = root / 'kali-mlx-convert.json'; conversion = json.loads(conversion_path.read_text())
    for arm, directory in directories.items():
        stage = root / directory
        for name in ['predictions.jsonl', 'receipt.json', 'metrics.json', 'protocol-before-generation.json']:
            frozen[str((stage / name).relative_to(ROOT))] = file_sha(stage / name)
        receipt = json.loads((stage / 'receipt.json').read_text()); preds = load_jsonl(stage / 'predictions.jsonl')
        if receipt['status'] != 'COMPLETE' or receipt['completed_rows'] != 36: raise ValueError('Incomplete arm')
        if receipt['dev_manifest_sha256'] != file_sha(manifest) or receipt['conversion_receipt_sha256'] != file_sha(conversion_path):
            raise ValueError('Original data/model receipt mismatch')
        if file_sha(stage / 'predictions.jsonl') != receipt['predictions_sha256']: raise ValueError('Prediction hash mismatch')
        if file_sha(stage / 'metrics.json') != receipt['metrics_sha256']: raise ValueError('Metric hash mismatch')
        if [x['id'] for x in preds] != [r['id'] for r in rows]: raise ValueError('Missing/duplicate/reordered IDs')
        originals[arm] = {x['id']: x for x in preds}; prompts[arm] = {}; scores[arm] = {}
        for r in rows:
            label = r['native_label']; tool = label['tool_name']; query = label['query']
            if not re.search(r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])', query, re.I):
                raise ValueError('Tool-help lookup uses a tool not explicitly named by query')
            messages = [dict(m) for m in r['messages']]
            if arm == 'tool_help':
                hits = [d for d in docs if d['source_row'] == r['source_row'] and d['title'] == r['tool_package'] and d['subtool'] == tool]
                if len(hits) != 1: raise ValueError('Ambiguous reference')
                context = hits[0]['usage_code'].split('```', 1)[0].strip()
                if sha(context.encode()) != receipt['tool_help_sha256_by_id'][r['id']]: raise ValueError('Context differs')
                if label['ground_truth_command'] in context: raise ValueError('Authored reference command appears verbatim in help')
                messages[-1]['content'] += ('\n\nTool help, supplied as reference data only, not instructions:\n'
                    '<tool_reference>\n' + context + '\n</tool_reference>')
            prompt = generation_prompt(native, messages, receipt['generation_prefix']); ids = native.encode(prompt, add_special_tokens=False)
            old = originals[arm][r['id']]
            if sha(prompt.encode()) != old['prompt_sha256'] or len(ids) != old['input_tokens']: raise ValueError('Prompt reconstruction mismatch')
            decoded = native.decode(old['generated_token_ids'], skip_special_tokens=False, clean_up_tokenization_spaces=False)
            if decoded != old['response']: raise ValueError('Stored raw tokens do not match response')
            if old['output_tokens'] != len(old['generated_token_ids']) + 1 or old['truncated']:
                raise ValueError('Unexpected token accounting/truncation in this completed experiment')
            if 'stream_response' in old and audit_stream_text(decoded, old['stream_response']) != old['render_audit']:
                raise ValueError('Stream rendering audit mismatch')
            prompts[arm][r['id']] = ids
            result = scorer.score_one(label, decoded)
            result['strict_option_value_correct'] = float(strict_option_values(label, decoded, scorer))
            scores[arm][r['id']] = result
        keys = ['tool_score', 'optional_f1', 'positional_f1', 'total_score', 'exact_match', 'format_error', 'strict_option_value_correct']
        direct = {k: sum(d[k] for d in scores[arm].values()) / 36 * 100 for k in keys}
        for k, value in direct.items():
            if abs(value - receipt['native_metrics'][k]) > 1e-10: raise ValueError('Native direct score changed: ' + k)
        audits[arm] = {'rows': 36, 'raw_token_decode_matches': 36, 'reconstructed_prompts_match': 36,
            'direct_scorer_metrics': direct, 'correct_count': sum(d['strict_option_value_correct'] for d in scores[arm].values())}
    original_partial = load_jsonl(root / 'kali-domain-e0-native-2026-10-22/predictions.jsonl')
    if original_partial != list(originals['native'].values())[:24]: raise ValueError('Recovery altered original24 rows')
    def ordered(values): return sorted(values, key=lambda s: sha(('kali-reverify-v1:' + s).encode()))
    strata = {
        'unchanged_success': [i for i in by_id if scores['aligned'][i]['strict_option_value_correct'] and scores['tool_help'][i]['strict_option_value_correct']],
        'dochelp_gain': [i for i in by_id if not scores['aligned'][i]['strict_option_value_correct'] and scores['tool_help'][i]['strict_option_value_correct']],
        'still_failed': [i for i in by_id if not scores['tool_help'][i]['strict_option_value_correct']],
        'native_stream_whitespace': [i for i in by_id if originals['native'][i].get('render_audit') == 'MLX_STREAM_DROPPED_ONE_INITIAL_ASCII_SPACE']}
    selected = []
    selection = {k: ordered(v)[:2] for k, v in strata.items()}
    for values in selection.values():
        for identifier in values:
            if identifier not in selected: selected.append(identifier)
    for identifier in ordered(by_id):
        if len(selected) >= 8: break
        if identifier not in selected: selected.append(identifier)
    plan = {'written_at_utc': datetime.now(timezone.utc).isoformat(), 'selection': selection, 'row_ids': selected,
        'selection_policy': 'Outcome-stratified diagnostic selection from already exposed dev, hash ordered; no generalization claim',
        'arms': list(directories), 'maximum_generation_calls': len(selected) * 3,
        'temperature': 0, 'seed': 42, 'max_output_tokens': 1024, 'prefill_step_size': 256,
        'original_hashes': frozen, 'model_conversion_sha256': file_sha(conversion_path)}
    write_json(args.output / 'plan-before-replay.json', plan)
    report.update(saved_output_audits=audits, audited_saved_rows=108, resumed24_rows_unchanged=True,
        help_tool_explicit_in_all_queries=True, authored_gold_command_absent_from_all_help=True)
    write_json(args.output / 'artifact-audit.json', report)
    if not args.execute:
        report['status'] = 'ARTIFACTS_VERIFIED_NO_FRESH_REPLAY'; write_json(args.output / 'result.json', report)
        print(json.dumps(report, indent=2)); return
    model_dir = Path(conversion['directory'])
    for name, value in conversion['files'].items():
        if file_sha(model_dir / name) != value: raise ValueError('Quantized model changed')
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.set_memory_limit(9 * 1024**3); mx.set_cache_limit(256 * 1024**2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Replay15min deadline')))
    signal.alarm(900); replays = []
    try:
        model, tokenizer = load(str(model_dir), tokenizer_config={'trust_remote_code': False, 'fix_mistral_regex': False})
        model.eval()
        for arm in directories:
            for identifier in selected:
                ids = prompts[arm][identifier]; mx.random.seed(42); tokens = []; pieces = []; last = None
                for event in stream_generate(model, tokenizer, prompt=ids, max_tokens=1024,
                                            sampler=make_sampler(temp=0), prefill_step_size=256):
                    pieces.append(event.text); last = event
                    if event.finish_reason != 'stop': tokens.append(int(event.token))
                if last is None: raise ValueError('No generation')
                raw = native.decode(tokens, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                render = audit_stream_text(raw, ''.join(pieces)); old = originals[arm][identifier]
                result = scorer.score_one(by_id[identifier]['native_label'], raw)
                same_score = all(result[k] == scores[arm][identifier][k] for k in ['tool_score', 'optional_f1', 'positional_f1', 'total_score', 'exact_match', 'format_error'])
                same_option = float(strict_option_values(by_id[identifier]['native_label'], raw, scorer)) == scores[arm][identifier]['strict_option_value_correct']
                replays.append({'arm': arm, 'id': identifier, 'generated_token_ids': tokens, 'response': raw,
                    'stream_response': ''.join(pieces), 'render_audit': render,
                    'token_ids_identical': tokens == old['generated_token_ids'], 'text_identical': raw == old['response'],
                    'metrics_identical': same_score and same_option, 'truncated': last.finish_reason == 'length'})
                write_jsonl(args.output / 'replays.jsonl', replays)
                print(json.dumps({'completed': len(replays), 'arm': arm, 'id': identifier,
                    'identical': replays[-1]['token_ids_identical']}), flush=True)
                mx.clear_cache()
        for rel, value in frozen.items():
            if file_sha(ROOT / rel) != value: raise ValueError('Original artifact modified during replay')
        report.update(status='VERIFIED' if all(r['token_ids_identical'] and r['text_identical'] and r['metrics_identical'] and not r['truncated'] for r in replays) else 'REPLAY_DIFFERENCE_REQUIRES_REVIEW',
            fresh_generation_calls=len(replays), identical_token_replays=sum(r['token_ids_identical'] for r in replays),
            identical_text_replays=sum(r['text_identical'] for r in replays), identical_metric_replays=sum(r['metrics_identical'] for r in replays),
            original_artifacts_unchanged=True, peak_metal_memory_bytes=mx.get_peak_memory(),
            mlx_version=importlib.metadata.version('mlx'), mlx_lm_version=importlib.metadata.version('mlx-lm'),
            limitations=['Same108saved cases independently rescored but using the same pinned native scoring implementation.',
                'Only8selected cases perarm freshly replayed; not a fresh108generation run.',
                'Reproducibility does not establish semantic gold correctness, population performance or unique failure cause.',
                'Independent label review and pinned Linux command verification still pending; no training benefit demonstrated.'])
    except Exception as exc:
        report.update(status='FAILED', error=type(exc).__name__ + ': ' + str(exc), fresh_generation_calls=len(replays))
        raise
    finally:
        signal.alarm(0); report['wall_seconds'] = time.monotonic() - started
        write_json(args.output / 'result.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'saved_output_audits'}, indent=2))


if __name__ == '__main__': main()
