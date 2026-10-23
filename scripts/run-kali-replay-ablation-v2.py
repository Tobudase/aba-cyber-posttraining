#!/usr/bin/env python3
"""Two predeclared manual MLX SFT arms, one per process and separate private-dev evaluation."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import random
import re
import signal
import time

from benchkit import (ROOT, encode_supervision, final_text, load_jsonl, load_manifest,
                      load_tokenizer, score_predictions, sha, write_json, write_jsonl)
from kali_prompt_policy import generation_prompt
from kali_decode_policy import audit_stream_text
from importlib.util import spec_from_file_location, module_from_spec

_spec = spec_from_file_location('domain_runner', ROOT / 'scripts/run-kali-domain-dev.py')
_domain = module_from_spec(_spec); _spec.loader.exec_module(_domain)
digest = _domain.digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm', choices=['domain_control','domain_plus_replay'], required=True)
    p.add_argument('--phase', choices=['train', 'evaluate'], required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--adapter', type=Path)
    p.add_argument('--execute', action='store_true'); args = p.parse_args()
    if not args.execute: p.error('Actual local experiment requires --execute')
    protocol_file = ROOT / f'configs/kali-replay-v2-{args.arm}.protocol.json'
    protocol = json.loads(protocol_file.read_text()); config = protocol['training']
    if protocol['runner_sha256'] != digest(Path(__file__)): raise ValueError('Frozen runner changed')
    train_manifest = ROOT / protocol['train_manifest']
    if digest(train_manifest) != protocol['train_manifest_sha256']: raise ValueError('Training manifest changed')
    conversion_file = ROOT / 'docs/verification/kali-mlx-convert.json'
    if digest(conversion_file) != protocol['conversion_receipt_sha256']: raise ValueError('Model receipt changed')
    conversion = json.loads(conversion_file.read_text()); model_dir = Path(conversion['directory'])
    for name, checksum in conversion['files'].items():
        if digest(model_dir / name) != checksum: raise ValueError('Base model changed')
    if args.phase == 'train' and args.adapter: raise ValueError('Fresh base only; no prior adapter initialization')
    if args.phase == 'evaluate':
        if not args.adapter: p.error('Evaluation needs the persisted candidate adapter')
        previous = json.loads((args.adapter.parent / 'receipt.json').read_text())
        if previous['status'] != 'COMPLETE' or previous['phase'] != 'train' or previous['protocol_sha256'] != digest(protocol_file):
            raise ValueError('Training receipt does not match frozen protocol')
        for name, checksum in previous['adapter_files'].items():
            if digest(args.adapter / name) != checksum: raise ValueError('Adapter changed')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    write_json(args.output / 'frozen-protocol.json', protocol)
    receipt = {'status': 'RUNNING', 'phase': args.phase, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'protocol_sha256': digest(protocol_file), 'conversion_receipt_sha256': digest(conversion_file),
        'train_manifest_sha256': digest(train_manifest), 'model_id': protocol['model_id'], 'revision': protocol['revision'],
        'actual_pretrained_weights_used': True, 'source_silver_pilot': True, 'ABA_executed': False,
        'official_test_rows': 0, 'confirmation_rows_queried': 0, 'dataset_commands_executed': 0,
        'tool_help_context_in_model_input': False, 'runner_sha256': digest(args.output / 'executed-runner.py'),
        'mlx': importlib.metadata.version('mlx'), 'mlx_lm': importlib.metadata.version('mlx-lm')}
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    from mlx_lm.tuner.utils import linear_to_lora_layers
    mx.set_memory_limit(protocol['budget']['metal_memory_limit_bytes'])
    mx.set_cache_limit(protocol['budget']['metal_cache_limit_bytes']); mx.random.seed(42)
    start = time.monotonic(); signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Fixed local pilot deadline')))
    signal.alarm(protocol['budget']['train_deadline_seconds' if args.phase == 'train' else 'eval_deadline_seconds'])
    try:
        native = load_tokenizer('redsage')
        model, tokenizer = load(str(model_dir), adapter_path=str(args.adapter) if args.adapter else None,
            tokenizer_config={'trust_remote_code': False, 'fix_mistral_regex': False})
        model.eval()
        if args.phase == 'train':
            # This branch loads TRAIN only, no development/confirmation row bodies.
            _, rows = load_manifest(train_manifest, 'train')
            if len(rows) != config['steps'] or len(rows) != 128: raise ValueError('Frozen one-epoch step budget changed')
            order = list(range(len(rows))); random.Random(config['seed']).shuffle(order)
            chosen = [rows[i] for i in order]
            encodings = [encode_supervision(native, r, config['max_sequence_tokens']) for r in chosen]
            model.freeze(); linear_to_lora_layers(model, config['last_layers'], config['lora'])
            parameters = dict(tree_flatten(model.trainable_parameters()))
            if len(parameters) != 16: raise ValueError('Expected16 q/v LoRA tensors')
            mx.eval(parameters); before = {k: mx.array(v) for k, v in parameters.items()}
            optimizer = optim.AdamW(learning_rate=config['learning_rate'], weight_decay=0.0)
            def loss_fn(net, inputs, labels):
                logits = net(inputs); valid = labels != -100
                ce = nn.losses.cross_entropy(logits, mx.maximum(labels, 0), reduction='none')
                return (ce * valid).sum() / valid.sum()
            def probe_loss():
                values = []
                for encoding in encodings[:8]:
                    value = loss_fn(model, mx.array([encoding['input_ids'][:-1]], dtype=mx.int32),
                                    mx.array([encoding['labels'][1:]], dtype=mx.int32))
                    mx.eval(value); values.append(float(value.item())); mx.clear_cache()
                return values
            initial_probe = probe_loss(); losses = []; value_grad = nn.value_and_grad(model, loss_fn); model.train()
            for step, encoding in enumerate(encodings, 1):
                inputs = mx.array([encoding['input_ids'][:-1]], dtype=mx.int32)
                labels = mx.array([encoding['labels'][1:]], dtype=mx.int32)
                value, grads = value_grad(model, inputs, labels); optimizer.update(model, grads)
                mx.eval(model.trainable_parameters(), optimizer.state, value)
                loss = float(value.item())
                if not math.isfinite(loss): raise ValueError('Nonfinite loss')
                if mx.get_peak_memory() > 10 * 1024**3: raise MemoryError('10GiB local hard stop')
                losses.append(loss); print(json.dumps({'step': step, 'total': len(encodings), 'loss': loss}), flush=True)
                write_json(args.output / 'training-progress.json', {'completed_steps': step, 'losses': losses})
                mx.clear_cache()
            model.eval(); final_probe = probe_loss()
            parameters = dict(tree_flatten(model.trainable_parameters()))
            changed = [k for k, v in parameters.items() if not bool(mx.array_equal(before[k], v).item())]
            if not changed: raise ValueError('No learned tensor change')
            adapter = args.output / 'adapter'; adapter.mkdir()
            mx.save_safetensors(str(adapter / 'adapters.safetensors'), parameters)
            write_json(adapter / 'adapter_config.json', {'fine_tune_type': 'lora', 'num_layers': config['last_layers'],
                                                       'lora_parameters': config['lora']})
            x = mx.array([encodings[0]['input_ids'][:-1]], dtype=mx.int32)
            ref = model(x)[:, -1, :].astype(mx.float32); mx.eval(ref)
            saved = mx.load(str(adapter / 'adapters.safetensors'))
            model.load_weights([(k, mx.zeros_like(v)) for k, v in parameters.items()], strict=False)
            mx.eval(model.trainable_parameters()); model.load_weights(list(saved.items()), strict=False)
            actual = model(x)[:, -1, :].astype(mx.float32); mx.eval(actual)
            delta = float(mx.max(mx.abs(ref - actual)).item())
            if delta > 1e-5: raise ValueError('Adapter persistence changed logits')
            receipt.update(optimizer_steps=len(losses), training_rows=len(chosen), train_ids=[r['id'] for r in chosen],
                losses=losses, changed_parameter_tensors=len(changed), trainable_parameters=sum(v.size for v in parameters.values()),
                fixed_train_probe_ids=[r['id'] for r in chosen[:8]], fixed_train_probe_loss_before=initial_probe,
                fixed_train_probe_loss_after=final_probe, adapter_reload_max_abs_logit_delta=delta,
                dev_rows_loaded_by_training_branch=0, dev_rows_used_for_optimization=0,
                adapter_files={p.name: digest(p) for p in adapter.iterdir()}, learning_rate=config['learning_rate'])
        else:
            receipt['training_receipt_sha256'] = digest(args.adapter.parent / 'receipt.json')
            receipt['adapter_files'] = previous['adapter_files']; evaluations = {}
            for name, check in protocol['evaluation'].items():
                manifest = ROOT / check['manifest']
                if digest(manifest) != check['manifest_sha256']: raise ValueError('Dev manifest changed')
                # Load only search split, rather than load_manifest's all-split reader.
                spec = json.loads(manifest.read_text()); part = spec['splits'][check['split']]
                data_path = manifest.parent / part['file']
                if digest(data_path) != part['sha256']: raise ValueError('Search row bytes changed')
                rows = load_jsonl(data_path)
                baseline_dir = ROOT / check['baseline_directory']
                if digest(baseline_dir / 'receipt.json') != check['baseline_receipt_sha256'] or digest(baseline_dir / 'predictions.jsonl') != check['baseline_predictions_sha256']:
                    raise ValueError('Baseline evidence changed')
                baseline = {r['id']: r for r in load_jsonl(baseline_dir / 'predictions.jsonl')}
                if len(rows) != check['rows'] or set(baseline) != {r['id'] for r in rows}: raise ValueError('Matched set mismatch')
                stage = args.output / name; stage.mkdir(); predictions = []
                for row in rows:
                    if row['split'] != 'dev_search' or row['training_eligible']: raise ValueError('Only development search permitted')
                    prompt = generation_prompt(native, row['messages'], 'sft-aligned')
                    if sha(prompt.encode()) != baseline[row['id']]['prompt_sha256']: raise ValueError('Baseline prompt differs')
                    ids = native.encode(prompt, add_special_tokens=False)
                    if tokenizer.encode(prompt, add_special_tokens=False) != ids: raise ValueError('Tokenizer differs')
                    mx.random.seed(42); pieces = []; tokens = []; last = None
                    for event in stream_generate(model, tokenizer, prompt=ids, max_tokens=1024,
                        sampler=make_sampler(temp=0), prefill_step_size=256):
                        pieces.append(event.text); last = event
                        if event.finish_reason != 'stop': tokens.append(int(event.token))
                    if last is None: raise ValueError('No model output')
                    text = native.decode(tokens, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                    rendering = audit_stream_text(text, ''.join(pieces))
                    predictions.append({'id': row['id'], 'response': text, 'generated_token_ids': tokens,
                        'stream_response': ''.join(pieces), 'render_audit': rendering,
                        'prompt_sha256': sha(prompt.encode()), 'input_tokens': len(ids), 'output_tokens': last.generation_tokens,
                        'truncated': last.finish_reason == 'length'})
                    write_jsonl(stage / 'predictions.jsonl', predictions)
                    print(json.dumps({'evaluation': name, 'completed': len(predictions), 'total': len(rows)}), flush=True)
                    mx.clear_cache()
                score = score_predictions(rows, predictions, 'kali'); write_json(stage / 'metrics.json', score)
                base_score = score_predictions(rows, list(baseline.values()), 'kali')
                evaluations[name] = {'rows': len(rows), 'baseline': base_score['summary'], 'post': score['summary'],
                    'complete_XML_rows': sum(bool(re.fullmatch(r'<output>\s*.+?\s*</output>', final_text(p['response']), re.S)) for p in predictions),
                    'truncated_rows': sum(p['truncated'] for p in predictions),
                    'predictions_sha256': digest(stage / 'predictions.jsonl'), 'metrics_sha256': digest(stage / 'metrics.json')}
            for path, checksum in protocol['protected_files_sha256'].items():
                if digest(ROOT / path) != checksum: raise ValueError('Protected authored data changed')
            receipt['evaluations'] = evaluations
        receipt['status'] = 'COMPLETE'
    except Exception as exc:
        receipt.update(status='FAILED', error=type(exc).__name__ + ': ' + str(exc)); raise
    finally:
        signal.alarm(0); receipt.update(wall_seconds=time.monotonic() - start, peak_metal_memory_bytes=mx.get_peak_memory())
        write_json(args.output / 'receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in {'losses', 'train_ids'}}, indent=2))


if __name__ == '__main__': main()
