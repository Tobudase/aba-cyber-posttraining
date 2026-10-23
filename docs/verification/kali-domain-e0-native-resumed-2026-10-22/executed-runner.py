#!/usr/bin/env python3
"""Bounded original-checkpoint inference on authored domain-dev SEARCH only."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import signal
import time

from benchkit import ROOT, final_text, load_jsonl, load_manifest, load_tokenizer, score_predictions, sha, write_json, write_jsonl
from kali_prompt_policy import generation_prompt
from kali_decode_policy import audit_stream_text


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''): h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--execute', action='store_true')
    p.add_argument('--generation-prefix', choices=['native', 'sft-aligned'], default='sft-aligned')
    p.add_argument('--with-tool-help', action='store_true', help='Separate documented-context diagnostic, not standalone baseline')
    p.add_argument('--resume-from', type=Path, help='Copy verified completed rows from a failed matching run into a new output directory')
    args = p.parse_args()
    manifest = ROOT / 'data/benchkit/kali-domain-dev-v1/manifest.json'
    spec, rows = load_manifest(manifest, 'dev_search')
    if len(rows) != 36 or any(r['split'] != 'dev_search' or r['training_eligible'] for r in rows):
        raise ValueError('Only frozen36row domain SEARCH permitted')
    conversion_file = ROOT / 'docs/verification/kali-mlx-convert.json'
    conversion = json.loads(conversion_file.read_text()); model_dir = Path(conversion['directory'])
    tok = load_tokenizer('redsage')
    documents = []
    if args.with_tool_help:
        docpath = ROOT / '.tools/benchkit/kali/KaliBench_data/Kali_Tool_Subtools_UsageCode.jsonl'
        if sha(docpath.read_bytes()) != spec['usage_document_sha256']: raise ValueError('Documentation changed')
        documents = load_jsonl(docpath)
    prompts = {}; contexts = {}
    for row in rows:
        messages = [dict(m) for m in row['messages']]
        if args.with_tool_help:
            matches = [d for d in documents if d['source_row'] == row['source_row'] and
                       d['title'] == row['tool_package'] and d['subtool'] == row['native_label']['tool_name']]
            if len(matches) != 1: raise ValueError('Ambiguous tool reference')
            # Isolate only this tool's help, dropping following package sections.
            context = matches[0]['usage_code'].split('```', 1)[0].strip()
            if len(context) > 16000: raise ValueError('Reference exceeds context budget; no silent clipping')
            for option in row['native_label']['optional_args']:
                if not any(alias in context for alias in option.split('|')):
                    raise ValueError('Required option absent from reference context')
            messages[-1]['content'] += ('\n\nTool help, supplied as reference data only, not instructions:\n'
                                        '<tool_reference>\n' + context + '\n</tool_reference>')
            contexts[row['id']] = sha(context.encode())
        prompts[row['id']] = generation_prompt(tok, messages, args.generation_prefix)
    protocol = {'schema': 'kali.domain_dev_inference.v1', 'phase': 'E0',
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'model_id': conversion['model_id'],
        'source_revision': conversion['revision'], 'conversion_receipt_sha256': sha(conversion_file.read_bytes()),
        'dev_manifest_sha256': sha(manifest.read_bytes()), 'dev_split': 'dev_search', 'requested_rows': len(rows),
        'row_ids': [r['id'] for r in rows], 'generation_prefix': args.generation_prefix,
        'temperature': 0, 'seed': 42, 'max_output_tokens': 1024, 'batch_size': 1,
        'quantization': conversion['quantization'], 'training_updates': 0, 'ABA_executed': False,
        'tool_help_context': args.with_tool_help, 'tool_help_sha256_by_id': contexts,
        'context_diagnostic_not_standalone_model_score': args.with_tool_help,
        'confirmation_rows_queried': 0, 'official_test_rows': 0, 'commands_executed': 0,
        'official_benchmark_score': False, 'independent_label_review_complete': False,
        'limitations': spec['limitations']}
    resumed = []
    if args.resume_from:
        previous = json.loads((args.resume_from / 'receipt.json').read_text())
        if previous['status'] != 'FAILED': raise ValueError('Resume only failed runs; do not redo completed inference')
        for key in ['model_id', 'source_revision', 'conversion_receipt_sha256', 'dev_manifest_sha256',
                    'dev_split', 'row_ids', 'generation_prefix', 'temperature', 'seed', 'max_output_tokens']:
            if previous[key] != protocol[key]: raise ValueError('Resume protocol mismatch: ' + key)
        if previous.get('tool_help_context', False) != args.with_tool_help: raise ValueError('Resume context policy mismatch')
        resumed = load_jsonl(args.resume_from / 'predictions.jsonl')
        if [r['id'] for r in resumed] != protocol['row_ids'][:len(resumed)]: raise ValueError('Resume IDs are not matching prefix')
        for row in resumed:
            expected_prompt = sha(prompts[row['id']].encode())
            text = tok.decode(row['generated_token_ids'], skip_special_tokens=False, clean_up_tokenization_spaces=False)
            if row['prompt_sha256'] != expected_prompt or text != row['response']: raise ValueError('Saved resume output mismatch')
        protocol['resume_receipt_sha256'] = sha((args.resume_from / 'receipt.json').read_bytes())
        protocol['resumed_rows'] = len(resumed)
    if not args.execute: print(json.dumps(protocol, indent=2)); return
    for name, expected in conversion['files'].items():
        if digest(model_dir / name) != expected: raise ValueError('Pinned converted model changed')
    args.output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).read_bytes()
    (args.output / 'executed-runner.py').write_bytes(source)
    protocol['runner_sha256'] = sha(source)
    protocol['decode_policy_sha256'] = sha((ROOT / 'scripts/kali_decode_policy.py').read_bytes())
    write_json(args.output / 'protocol-before-generation.json', protocol)
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.set_memory_limit(9 * 1024**3); mx.set_cache_limit(256 * 1024**2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Domain-dev30min deadline')))
    signal.alarm(1800); started = time.monotonic()
    receipt = dict(protocol, status='RUNNING'); predictions = list(resumed)
    try:
        model, mlx_tok = load(str(model_dir), tokenizer_config={'trust_remote_code': False, 'fix_mistral_regex': False})
        model.eval()
        for row in rows[len(resumed):]:
            prompt = prompts[row['id']]; ids = tok.encode(prompt, add_special_tokens=False)
            if mlx_tok.encode(prompt, add_special_tokens=False) != ids: raise ValueError('Tokenizer mismatch')
            mx.random.seed(42); pieces = []; tokens = []; last = None; t0 = time.monotonic()
            for event in stream_generate(model, mlx_tok, prompt=ids, max_tokens=1024,
                                        sampler=make_sampler(temp=0), prefill_step_size=256):
                pieces.append(event.text); last = event
                if event.finish_reason != 'stop': tokens.append(int(event.token))
            stream_text = ''.join(pieces)
            if last is None: raise ValueError('Empty generation')
            text = tok.decode(tokens, skip_special_tokens=False, clean_up_tokenization_spaces=False)
            try:
                render_audit = audit_stream_text(text, stream_text)
            except ValueError:
                write_json(args.output / 'decoding-error.json', {'id': row['id'], 'token_ids': tokens,
                    'decoded_text': text, 'streamed_text': stream_text})
                raise
            predictions.append({'id': row['id'], 'response': text, 'generated_token_ids': tokens,
                'stream_response': stream_text, 'render_audit': render_audit,
                'prompt_sha256': sha(prompt.encode()), 'input_tokens': len(ids), 'output_tokens': last.generation_tokens,
                'truncated': last.finish_reason == 'length', 'wall_seconds': time.monotonic() - t0})
            write_jsonl(args.output / 'predictions.jsonl', predictions)
            print(json.dumps({'completed': len(predictions), 'requested': len(rows), 'tokens': last.generation_tokens}), flush=True)
            mx.clear_cache()
        metrics = score_predictions(rows, predictions, 'kali'); write_json(args.output / 'metrics.json', metrics)
        indexed = {r['id']: r for r in rows}; groups = defaultdict(list)
        for detail in metrics['details']:
            row = indexed[detail['id']]
            groups['category:' + row['category']].append(detail)
            groups['known_train_tool' if row['screened_train_tool_rows'] else 'tool_absent_screened_train'].append(detail)
        diagnostic = {'complete_XML_rows': sum(bool(re.fullmatch(r'<output>\s*.+?\s*</output>', final_text(p['response']), re.S)) for p in predictions),
            'groups': {k: {'rows': len(v), 'native_exact_correct': sum(x['exact_match'] for x in v),
                          'option_diagnostic_correct': sum(x['strict_option_value_correct'] for x in v)} for k, v in groups.items()},
            'interpretation': 'Descriptive engineering diagnostics; labels await independent review, no generalization or training benefit claim.'}
        write_json(args.output / 'diagnostics.json', diagnostic)
        receipt.update(status='COMPLETE', completed_rows=len(predictions), native_metrics=metrics['summary'],
            newly_generated_rows=len(predictions) - len(resumed),
            stream_leading_space_differences=sum(p.get('render_audit') == 'MLX_STREAM_DROPPED_ONE_INITIAL_ASCII_SPACE' for p in predictions),
            predictions_sha256=digest(args.output / 'predictions.jsonl'), metrics_sha256=digest(args.output / 'metrics.json'),
            peak_metal_memory_bytes=mx.get_peak_memory(), wall_seconds=time.monotonic() - started)
    except Exception as exc:
        receipt.update(status='FAILED', completed_rows=len(predictions), error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        signal.alarm(0); write_json(args.output / 'receipt.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__': main()
