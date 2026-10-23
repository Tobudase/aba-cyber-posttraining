#!/usr/bin/env python3
"""Paired external-dev inference prefix ablation; zero training, no final tests."""
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import re
import signal
import time

from benchkit import ROOT, final_text, load_jsonl, load_manifest, load_tokenizer, score_predictions, sha, write_json, write_jsonl
from kali_prompt_policy import matched_final_only_prompt


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''): h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--execute', action='store_true')
    args = p.parse_args()
    manifest = ROOT / 'data/benchkit/kali-external-dev/manifest.json'
    _, rows = load_manifest(manifest, 'dev_search')
    native_tok = load_tokenizer('redsage')
    prompts = {r['id']: matched_final_only_prompt(native_tok, r['messages'])[1] for r in rows}
    verification = ROOT / 'docs/verification'
    conversion_path = verification / 'kali-mlx-convert.json'
    conversion = json.loads(conversion_path.read_text())
    model_dir = __import__('pathlib').Path(conversion['directory'])
    for filename, checksum in conversion['files'].items():
        if digest(model_dir / filename) != checksum: raise ValueError('Converted model changed')
    adapter_dir = verification / 'kali-mlx-e1-train-2026-10-22/adapter'
    train_receipt = json.loads((adapter_dir.parent / 'receipt.json').read_text())
    for filename, checksum in train_receipt['adapter_files'].items():
        if digest(adapter_dir / filename) != checksum: raise ValueError('Adapter changed')
    old = {}
    for phase, dirname in [('E0', 'kali-mlx-e0-2026-10-22'), ('E1', 'kali-mlx-e1-dev-2026-10-22')]:
        path = verification / dirname
        receipt = json.loads((path / 'receipt.json').read_text())
        if receipt['status'] != 'COMPLETE' or receipt['dev_manifest_sha256'] != sha(manifest.read_bytes()) or receipt['conversion_receipt_sha256'] != sha(conversion_path.read_bytes()):
            raise ValueError('Original experiment no longer matches')
        if digest(path / 'predictions.jsonl') != receipt['predictions_sha256']: raise ValueError('Original outputs changed')
        old[phase] = {'receipt': receipt, 'predictions': load_jsonl(path / 'predictions.jsonl')}
    protocol = {'schema': 'kali.prefix_ablation.v1', 'model_id': conversion['model_id'],
        'source_revision': conversion['revision'], 'conversion_receipt_sha256': sha(conversion_path.read_bytes()),
        'training_receipt_sha256': sha((adapter_dir.parent / 'receipt.json').read_bytes()),
        'dev_manifest_sha256': sha(manifest.read_bytes()), 'rows_per_phase': 72, 'maximum_generation_calls': 144,
        'changed_variable': 'Remove only opening<think> from native assistant generation prefix',
        'SFT_assistant_boundary_matches_all_rows': True, 'max_output_tokens': 1024, 'temperature': 0,
        'seed': 42, 'batch_size': 1, 'training_updates': 0, 'official_test_rows': 0,
        'confirmation_rows_queried': 0, 'scorer_changed': False,
        'limitations': ['External dev already exposed,12authored families, not independent test.',
            'Removing prefix is not a guarantee that reasoning is disabled.',
            'Does not replace thinking-prompt official evaluation or demonstrate ABA improvement.']}
    if not args.execute:
        print(json.dumps(protocol, indent=2)); return
    out = verification / 'kali-prefix-ablation-2026-10-22'; out.mkdir(exist_ok=False)
    write_json(out / 'protocol-before-generation.json', protocol)
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.set_memory_limit(9 * 1024**3); mx.set_cache_limit(256 * 1024**2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Prefix ablation40min deadline')))
    signal.alarm(2400)
    summaries = {}
    try:
        for phase in ['E0', 'E1']:
            stage = out / phase; stage.mkdir()
            started = time.monotonic()
            model, tokenizer = load(str(model_dir), adapter_path=str(adapter_dir) if phase == 'E1' else None,
                tokenizer_config={'trust_remote_code': False, 'fix_mistral_regex': False})
            model.eval(); predictions = []
            for row in rows:
                prompt = prompts[row['id']]; ids = native_tok.encode(prompt, add_special_tokens=False)
                if tokenizer.encode(prompt, add_special_tokens=False) != ids: raise ValueError('Tokenizer mismatch')
                mx.random.seed(42); started_row = time.monotonic(); pieces = []; tokens = []; last = None
                for response in stream_generate(model, tokenizer, prompt=ids, max_tokens=1024,
                    sampler=make_sampler(temp=0), prefill_step_size=256):
                    pieces.append(response.text); last = response
                    if response.finish_reason != 'stop': tokens.append(int(response.token))
                text = ''.join(pieces)
                if last is None or native_tok.decode(tokens, skip_special_tokens=False, clean_up_tokenization_spaces=False) != text:
                    raise ValueError('Raw-token/stream mismatch')
                predictions.append({'id': row['id'], 'response': text, 'generated_token_ids': tokens,
                    'prompt_sha256': sha(prompt.encode()), 'input_tokens': len(ids), 'output_tokens': last.generation_tokens,
                    'truncated': last.finish_reason == 'length', 'wall_seconds': time.monotonic() - started_row})
                write_jsonl(stage / 'predictions.jsonl', predictions)
                print(json.dumps({'phase': phase, 'completed': len(predictions), 'tokens': last.generation_tokens}), flush=True)
                mx.clear_cache()
            native_score = score_predictions(rows, old[phase]['predictions'], 'kali')
            score = score_predictions(rows, predictions, 'kali')
            write_json(stage / 'metrics.json', score)
            def stats(preds, scored):
                envelope = {r['id']: bool(re.fullmatch(r'<output>\s*.+?\s*</output>', final_text(r['response']), re.S)) for r in preds}
                return {'native_metrics': scored['summary'], 'complete_XML_rows': sum(envelope.values()),
                    'xml_and_option_correct': sum(envelope[r['id']] and bool(r['strict_option_value_correct']) for r in scored['details']),
                    'output_tokens': sum(r['output_tokens'] for r in preds)}
            summaries[phase] = {'native_prefix': stats(old[phase]['predictions'], native_score),
                'aligned_final_only_prefix': stats(predictions, score), 'rows': 72,
                'wall_seconds': time.monotonic() - started, 'predictions_sha256': digest(stage / 'predictions.jsonl')}
            write_json(stage / 'receipt.json', {'status': 'COMPLETE', **summaries[phase],
                'protocol_sha256': sha((out / 'protocol-before-generation.json').read_bytes())})
            del model, tokenizer; gc.collect(); mx.clear_cache()
        report = {'status': 'PAIRED_PREFIX_ABLATION_COMPLETE', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'protocol': protocol, 'comparison': summaries, 'new_training_updates': 0,
            'peak_metal_bytes': mx.get_peak_memory(), 'official_benchmark_result': False}
        write_json(out / 'comparison.json', report)
        print(json.dumps(report, indent=2))
    finally:
        signal.alarm(0)


if __name__ == '__main__': main()
