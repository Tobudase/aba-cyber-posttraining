#!/usr/bin/env python3
"""Real pinned8B local quantized E0/E1 pilot; no official test or shell execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import signal
import time

from benchkit import (ROOT, encode_supervision, load_jsonl, load_manifest, load_tokenizer,
                      score_predictions, sha, write_json, write_jsonl)
from kali_prompt_policy import generation_prompt

TRAIN = ROOT / 'data/benchkit/kali-screened/manifest.json'
DEV = ROOT / 'data/benchkit/kali-external-dev/manifest.json'


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def round_robin_families(rows):
    groups = {}
    for row in rows: groups.setdefault(row['group_id'], []).append(row)
    return [group[index] for index in range(max(map(len, groups.values())))
            for _, group in sorted(groups.items()) if index < len(group)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['baseline', 'train', 'post'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--adapter', type=Path)
    parser.add_argument('--resume-from', type=Path)
    parser.add_argument('--limit', type=int, default=72)
    parser.add_argument('--steps', type=int, default=20)
    parser.add_argument('--generation-prefix', choices=['native', 'sft-aligned'], default='native',
                        help='Explicit local policy; retain native default for historical reproducibility')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute: parser.error('Local real-model experiment requires --execute')
    if not 1 <= args.limit <= 72 or not 1 <= args.steps <= 20: parser.error('Pilot budget exceeded')
    if args.phase == 'baseline' and args.adapter: parser.error('Baseline cannot load an adapter')
    conversion = json.loads((ROOT / 'docs/verification/kali-mlx-convert.json').read_text())
    directory = Path(conversion['directory'])
    for name, expected in conversion['files'].items():
        if file_sha(directory / name) != expected: raise ValueError('Quantized model bytes changed')
    # Fixed-SFT training needs no dev row bodies, including tokenizer probes.
    # Original completed run used no dev gradients; this also removes needless reads.
    train, dev = [], []
    if args.phase == 'train':
        _, train = load_manifest(TRAIN, 'train')
    else:
        _, dev = load_manifest(DEV, 'dev_search')
        dev = round_robin_families(dev)[:args.limit]
    baseline = None
    if args.phase in {'train', 'post'}:
        if not args.baseline: parser.error('Matched baseline receipt required before continued SFT/post evaluation')
        baseline = json.loads((args.baseline / 'receipt.json').read_text())
        if baseline['phase'] != 'baseline' or baseline['status'] != 'COMPLETE' or baseline['actual_rows'] != 72:
            raise ValueError('Complete72-row baseline required')
        if baseline['conversion_receipt_sha256'] != sha((ROOT / 'docs/verification/kali-mlx-convert.json').read_bytes()):
            raise ValueError('Different quantized base')
        if baseline.get('generation_prefix_policy', 'native') != args.generation_prefix:
            raise ValueError('Baseline/post prefix policy mismatch; obtain a matched baseline first')
    if args.phase == 'post':
        if not args.adapter: parser.error('Post phase requires persisted adapter')
        training = json.loads((args.adapter.parent / 'receipt.json').read_text())
        if training['phase'] != 'train' or training['status'] != 'COMPLETE' or training['train_manifest_sha256'] != sha(TRAIN.read_bytes()):
            raise ValueError('Training receipt mismatch')
        if training['baseline_receipt_sha256'] != sha((args.baseline / 'receipt.json').read_bytes()):
            raise ValueError('Adapter trained after a different baseline')
        for name, expected in training['adapter_files'].items():
            if file_sha(args.adapter / name) != expected: raise ValueError('Adapter changed')
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    from mlx_lm.tuner.utils import linear_to_lora_layers
    mx.set_memory_limit(9 * 1024**3)
    mx.set_cache_limit(256 * 1024**2)
    mx.random.seed(42)
    start = time.monotonic()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Local pilot deadline')))
    signal.alarm(2400)
    receipt = {'phase': args.phase, 'status': 'RUNNING', 'model_id': conversion['model_id'],
        'source_revision': conversion['revision'], 'actual_pretrained_8b_weights_used': True,
        'conversion_receipt_sha256': sha((ROOT / 'docs/verification/kali-mlx-convert.json').read_bytes()),
        'quantization': conversion['quantization'], 'mlx': importlib.metadata.version('mlx'),
        'mlx_lm': importlib.metadata.version('mlx-lm'), 'device': mx.device_info()['device_name'],
        'train_manifest_sha256': sha(TRAIN.read_bytes()), 'dev_manifest_sha256': sha(DEV.read_bytes()),
        'max_output_tokens': 1024, 'temperature': 0, 'seed': 42, 'official_test_rows': 0,
        'generation_prefix_policy': args.generation_prefix,
        'confirmation_rows_queried': 0, 'dataset_commands_executed': 0,
        'official_benchmark_score': False, 'ABA_executed': False,
        'limitations': ['External72dev is18 authored families split into12search/6confirm; six variants per family are correlated.',
            'Already cyber/Kali-trained checkpoint; continuing on official TRAIN is not first exposure or new-data adaptation.',
            'Local affine4/greedy/strict-prompt pilot, not BF16/temperature0.2/thinking8192-token official reproduction.']}
    if baseline:
        receipt['baseline_receipt_sha256'] = sha((args.baseline / 'receipt.json').read_bytes())
    try:
        model, tokenizer = load(str(directory),
            tokenizer_config={'trust_remote_code': False, 'fix_mistral_regex': False},
            adapter_path=str(args.adapter) if args.adapter else None)
        native = load_tokenizer('redsage')
        for row in dev:
            canonical = generation_prompt(native, row['messages'], args.generation_prefix)
            if native.encode(canonical, add_special_tokens=False) != tokenizer.encode(canonical, add_special_tokens=False):
                raise ValueError('MLX/native tokenizer differs')
        if args.phase == 'train':
            # Actual supervised updates on domain TRAIN; no dev gradients/labels.
            model.freeze()
            lora = {'rank': 8, 'scale': 2.0, 'dropout': 0.0, 'keys': ['self_attn.q_proj', 'self_attn.v_proj']}
            linear_to_lora_layers(model, 4, lora)
            parameters = dict(tree_flatten(model.trainable_parameters()))
            if len(parameters) != 16: raise ValueError('Expected q/v LoRA on last4layers only')
            mx.eval(parameters)
            before = {name: mx.array(value) for name, value in parameters.items()}
            optimizer = optim.AdamW(learning_rate=5e-5, weight_decay=0.0)
            order = list(range(len(train))); random.Random(42).shuffle(order)
            chosen = [train[i] for i in order[:args.steps]]
            encodings = [encode_supervision(native, r, 2048) for r in chosen]
            def loss_fn(net, inputs, labels):
                logits = net(inputs)
                valid = labels != -100
                targets = mx.maximum(labels, 0)
                ce = nn.losses.cross_entropy(logits, targets, reduction='none')
                return (ce * valid).sum() / valid.sum()
            loss_grad = nn.value_and_grad(model, loss_fn)
            model.train()
            losses = []
            for step, encoding in enumerate(encodings, 1):
                inputs = mx.array([encoding['input_ids'][:-1]], dtype=mx.int32)
                labels = mx.array([encoding['labels'][1:]], dtype=mx.int32)
                value, grads = loss_grad(model, inputs, labels)
                optimizer.update(model, grads)
                mx.eval(model.trainable_parameters(), optimizer.state, value)
                number = float(value.item())
                if not __import__('math').isfinite(number): raise ValueError('Nonfinite training loss')
                losses.append(number)
                if mx.get_peak_memory() > 10 * 1024**3: raise MemoryError('Local10GiB Metal pilot cap exceeded')
                print(json.dumps({'step': step, 'loss': number, 'peak_GB': mx.get_peak_memory() / 1e9}), flush=True)
                mx.clear_cache()
            parameters = dict(tree_flatten(model.trainable_parameters()))
            changed = [n for n, v in parameters.items() if not bool(mx.array_equal(v, before[n]).item())]
            if not changed: raise ValueError('No real adapter change')
            adapter = out / 'adapter'; adapter.mkdir()
            mx.save_safetensors(str(adapter / 'adapters.safetensors'), parameters)
            write_json(adapter / 'adapter_config.json', {'fine_tune_type': 'lora', 'num_layers': 4, 'lora_parameters': lora})
            model.eval()
            probe = mx.array([encodings[0]['input_ids'][:-1]], dtype=mx.int32)
            reference = model(probe)[:, -1, :].astype(mx.float32); mx.eval(reference)
            saved = mx.load(str(adapter / 'adapters.safetensors'))
            model.load_weights([(n, mx.zeros_like(v)) for n, v in parameters.items()], strict=False)
            mx.eval(model.trainable_parameters())
            model.load_weights(list(saved.items()), strict=False)
            actual = model(probe)[:, -1, :].astype(mx.float32); mx.eval(actual)
            delta = float(mx.max(mx.abs(reference - actual)).item())
            if delta > 1e-5: raise ValueError('Persisted adapter reload changes logits')
            receipt.update(optimizer_steps=len(losses), records_used=len(chosen), losses=losses,
                train_ids=[r['id'] for r in chosen], changed_parameter_tensors=len(changed),
                trainable_parameters=sum(x.size for x in parameters.values()),
                adapter_reload_max_abs_logit_delta=delta, dev_rows_used_for_optimization=0,
                adapter_files={p.name: file_sha(p) for p in adapter.iterdir()},
                supervision='Assistant-only native full-chat final-only targets, no fabricated reasoning',
                lora=lora, trainable_last_layers=4, learning_rate=5e-5)
        else:
            model.eval()
            results = []
            if args.resume_from:
                prior = json.loads((args.resume_from / 'receipt.json').read_text())
                for key in ['phase', 'conversion_receipt_sha256', 'dev_manifest_sha256', 'max_output_tokens', 'temperature', 'seed']:
                    if prior[key] != receipt[key]: raise ValueError('Resume protocol mismatch')
                if prior.get('generation_prefix_policy', 'native') != args.generation_prefix:
                    raise ValueError('Resume prefix policy mismatch')
                if args.phase != 'baseline': raise ValueError('Only unchanged baseline can reuse previous records')
                results = load_jsonl(args.resume_from / 'predictions.jsonl')
                if len({r['id'] for r in results}) != len(results) or not {r['id'] for r in results} <= {r['id'] for r in dev}:
                    raise ValueError('Resume IDs mismatch')
                write_jsonl(out / 'predictions.jsonl', results)
            for row in dev:
                if row['id'] in {r['id'] for r in results}: continue
                prompt = generation_prompt(native, row['messages'], args.generation_prefix)
                ids = native.encode(prompt, add_special_tokens=False)
                mx.random.seed(42)
                began = time.monotonic(); segments = []; last = None
                for response in stream_generate(model, tokenizer, prompt=ids, max_tokens=1024,
                    sampler=make_sampler(temp=0), prefill_step_size=256):
                    segments.append(response.text); last = response
                if last is None: raise ValueError('Empty generation stream')
                result = {'id': row['id'], 'response': ''.join(segments), 'prompt_sha256': sha(prompt.encode()),
                    'input_tokens': len(ids), 'output_tokens': last.generation_tokens,
                    'truncated': last.finish_reason == 'length', 'finish_reason': last.finish_reason,
                    'wall_seconds': time.monotonic() - began, 'actual_pretrained_weights_used': True}
                results.append(result); write_jsonl(out / 'predictions.jsonl', results)
                print(json.dumps({'completed': len(results), 'id': row['id'], 'tokens': result['output_tokens'],
                    'truncated': result['truncated'], 'seconds': round(result['wall_seconds'], 2)}), flush=True)
                mx.clear_cache()
            scored = score_predictions(dev, results, 'kali'); write_json(out / 'metrics.json', scored)
            receipt.update(actual_rows=len(results), requested_rows=len(dev), full_search_split=len(dev) == 72,
                prompt_policy=('Pinned strict messages, native opening<think>, greedy' if args.generation_prefix == 'native'
                               else 'Pinned strict messages, SFT-aligned assistant boundary, greedy'), metrics=scored['summary'],
                predictions_sha256=sha((out / 'predictions.jsonl').read_bytes()))
        receipt['status'] = 'COMPLETE'
    except Exception as exc:
        receipt.update(status='FAILED_PARTIAL', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        signal.alarm(0)
        receipt.update(checked_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic() - start,
            peak_metal_memory_bytes=mx.get_peak_memory())
        write_json(out / 'receipt.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__': main()
