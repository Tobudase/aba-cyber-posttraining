#!/usr/bin/env python3
"""Frozen BF16 240-row SFT with new DEV and historical retention readouts."""
import concurrent.futures
import gc
import gzip
import hashlib
import json
import math
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(parameters):
    h = hashlib.sha256()
    for name, value in sorted(parameters.items()):
        h.update(name.encode())
        h.update(value.detach().float().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def main():
    payload_bytes = gzip.decompress(Path('/input/payload.json.gz').read_bytes())
    payload = json.loads(payload_bytes)
    config = payload['effective_config']
    started = time.monotonic()
    stop = threading.Event()
    result = {'status': 'RUNNING', 'effective_config': config, 'predictions': {},
              'training': {}, 'NLL': {}, 'samples': [], 'loader_checks': [],
              'worker_sha256': sha('/input/worker.py'),
              'optimizer_source_sha256': sha('/input/kali_sft_recipe.py'),
              'payload_sha256': hashlib.sha256(payload_bytes).hexdigest(),
              'new_generations': 0, 'generated_tokens': 0, 'optimizer_steps_observed': 0,
              'official_or_confirmation_calls': 0, 'external_teacher_calls': 0}
    phase = 'staging'

    def monitor():
        while not stop.is_set():
            try:
                q = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                                    '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
                sample = {'seconds': round(time.monotonic() - started, 2),
                          'phase': phase, 'gpu': q.stdout.strip()}
                cpu = Path('/sys/fs/cgroup/cpu.stat')
                if cpu.exists():
                    sample['cpu_stat'] = dict(line.split() for line in cpu.read_text().splitlines())
                ram = Path('/sys/fs/cgroup/memory.current')
                if ram.exists():
                    sample['host_memory_bytes'] = int(ram.read_text())
                result['samples'].append(sample)
            except Exception as exc:
                result.setdefault('monitor_errors', []).append(type(exc).__name__)
            stop.wait(5)

    threading.Thread(target=monitor, daemon=True).start()
    try:
        model_dir = Path('/scratch/model')
        model_dir.mkdir()

        def stage(item):
            name, digest = item
            assert Path(name).name == name
            h = hashlib.sha256()
            with (Path('/cache/model') / name).open('rb') as src, (model_dir / name).open('wb') as dst:
                for block in iter(lambda: src.read(8 * 1024**2), b''):
                    h.update(block)
                    dst.write(block)
            assert h.hexdigest() == digest
            print('STAGED ' + name, flush=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(stage, payload['assets']['checkpoint_files'].items()))
        assert sha('/cache/runtime-deps.tar') == payload['assets']['runtime_archive_sha256']
        deps = Path('/scratch/deps')
        deps.mkdir()
        with tarfile.open('/cache/runtime-deps.tar') as archive:
            assert all(x.isfile() and (deps / x.name).resolve().is_relative_to(deps.resolve())
                       for x in archive.getmembers())
            archive.extractall(deps, filter='data')
        sys.path[:0] = [str(deps), '/input']
        result['staging_seconds'] = time.monotonic() - started
        import torch
        from importlib.metadata import version
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import LoraConfig, get_peft_model
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        from kali_sft_recipe import validate_recipe, train_fixed_sft
        result['packages'] = {name: version(name) for name in payload['expected_packages']}
        assert result['packages'] == payload['expected_packages']
        torch.set_num_threads(2)
        result['GPU'] = torch.cuda.get_device_name(0)
        assert result['GPU'] in config['allowed_GPU_models']
        assert torch.cuda.get_device_properties(0).total_memory >= 22 * 1024**3
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True,
                       trust_remote_code=False, fix_mistral_regex=False)
        tokenizer.padding_side = 'left'
        tokenizer.pad_token = tokenizer.eos_token
        rows = payload['train_rows']
        for arm in config['arms']:
            validate_recipe(arm['optimizer'], rows)
        def load_model():
            nonlocal phase
            phase = 'load_BF16'
            torch.manual_seed(config['initialization_seed'])
            base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                device_map={'': 0}, torch_dtype=torch.bfloat16, attn_implementation='sdpa')
            base.requires_grad_(False)
            assert all(v.dtype == torch.bfloat16 for v in base.parameters() if v.is_floating_point())
            base.enable_input_require_grads()
            model = get_peft_model(base, LoraConfig(**config['LoRA']))
            params = {n: v for n, v in model.named_parameters() if v.requires_grad}
            assert params and all('lora_' in n and v.dtype == torch.float32 for n, v in params.items())
            result['initial_LoRA_sha256'] = fingerprint(params)
            assert all(v.dtype == torch.bfloat16 for n, v in model.named_parameters() if 'lora_' not in n and v.is_floating_point())
            result['loader_checks'].append({'mode': 'BF16', 'non_LoRA_FP32_parameters': 0,
                                           'LoRA_dtype': 'float32', 'only_LoRA_trainable': True})
            return model

        def infer(model, records, key):
            nonlocal phase
            phase = 'inference_' + key
            model.eval()
            model.gradient_checkpointing_disable()
            model.config.use_cache = True
            policy = config['inference']
            predictions = []
            for offset in range(0, len(records), policy['batch_size']):
                batch_rows = records[offset:offset + policy['batch_size']]
                prompts = []
                for row in batch_rows:
                    assert row['set'] in ['TRAIN_diagnostic', 'DEV', 'retention']
                    prompt = tokenizer.apply_chat_template(row['native_messages'], tokenize=False, add_generation_prompt=True)
                    assert prompt.endswith('<think>') and hashlib.sha256(prompt.encode()).hexdigest() == row['prompt_sha256']
                    prompts.append(prompt)
                inputs = tokenizer(prompts, padding=True, add_special_tokens=False, return_tensors='pt').to('cuda')
                for i, row in enumerate(batch_rows):
                    native_ids = inputs['input_ids'][i][inputs['attention_mask'][i].bool()].tolist()
                    assert hashlib.sha256(json.dumps(native_ids).encode()).hexdigest() == row['input_ids_sha256']
                assert result['new_generations'] + len(batch_rows) <= config['budget']['max_generations']
                assert result['generated_tokens'] + len(batch_rows) * policy['max_new_tokens'] <= config['budget']['max_output_tokens']
                torch.manual_seed(policy['seed'])
                with torch.inference_mode():
                    generated = model.generate(**inputs, max_new_tokens=policy['max_new_tokens'],
                        do_sample=False, use_cache=True, pad_token_id=tokenizer.eos_token_id,
                        eos_token_id=tokenizer.eos_token_id, temperature=None, top_p=None, top_k=None)
                new_ids = generated[:, inputs['input_ids'].shape[1]:].tolist()
                for row, ids in zip(batch_rows, new_ids):
                    truncated = tokenizer.eos_token_id not in ids
                    effective_ids = ids if truncated else ids[:ids.index(tokenizer.eos_token_id)]
                    result['generated_tokens'] += len(effective_ids) + (not truncated)
                    result['new_generations'] += 1
                    predictions.append({'id': row['id'], 'set': row['set'],
                        'response': tokenizer.decode(effective_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False),
                        'truncated': truncated, 'generated_tokens': len(effective_ids), 'prompt_sha256': row['prompt_sha256']})
                print('PROGRESS=' + json.dumps({'phase': phase, 'rows': len(predictions),
                                              'generations': result['new_generations']}), flush=True)
                del inputs, generated
            result['predictions'][key] = predictions

        def nll(model, key):
            nonlocal phase
            phase = 'nll_' + key
            model.eval()
            values = []
            for row in rows:
                ids = torch.tensor([row['input_ids']], device='cuda')
                with torch.inference_mode():
                    loss = float(model(input_ids=ids, attention_mask=torch.ones_like(ids),
                          labels=torch.tensor([row['labels']], device='cuda'), use_cache=False).loss)
                assert math.isfinite(loss)
                values.append((loss, len(row['input_ids']) - row['prompt_tokens']))
            result['NLL'][key] = {'rows': len(values),
                'token_weighted_NLL': sum(v * n for v, n in values) / sum(n for _, n in values)}

        model = load_model()
        records = payload['TRAIN_diagnostic'] + payload['evaluation_rows']
        assert len(records) == 112
        infer(model, records, 'base')
        arm = config['arms'][0]
        name = arm['name']
        nll(model, 'before')
        phase = 'train_BF16'
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        model.config.use_cache = False

        def progress(step):
            result['optimizer_steps_observed'] = step['step']
            if step['step'] == 1 or step['step'] % 16 == 0:
                print('TRAIN=' + json.dumps({'arm': name, **step}), flush=True)

        receipt = train_fixed_sft(model, rows, arm['optimizer'], 'cuda', progress)
        out = Path('/cache') / payload['output_prefix'] / name
        assert out.resolve().is_relative_to(Path('/cache').resolve())
        out.mkdir(parents=True, exist_ok=False)
        model.eval()
        model.gradient_checkpointing_disable()
        model.save_pretrained(out / 'adapter')
        probe = torch.tensor([rows[0]['input_ids']], device='cuda')
        with torch.inference_mode():
            ref = model(input_ids=probe, use_cache=False).logits[:, -1, :].float().cpu()
        state = load_file(str(out / 'adapter/adapter_model.safetensors'))
        with torch.no_grad():
            for value in model.parameters():
                if value.requires_grad:
                    value.zero_()
        set_peft_model_state_dict(model, state, adapter_name='default')
        with torch.inference_mode():
            actual = model(input_ids=probe, use_cache=False).logits[:, -1, :].float().cpu()
        delta = float((ref - actual).abs().max())
        assert delta <= 1e-4
        receipt.update({'training_precision': 'BF16', 'initial_LoRA_sha256': result['initial_LoRA_sha256'],
                        'adapter_reload_max_logit_delta': delta,
                        'adapter_sha256': sha(out / 'adapter/adapter_model.safetensors')})
        result['training'][name] = receipt
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        del ref, actual, state, probe
        nll(model, 'after')
        infer(model, records, 'sft')
        del model
        gc.collect()
        torch.cuda.empty_cache()
        result['new_optimizer_steps'] = receipt['optimizer_steps']
        assert result['new_optimizer_steps'] == 480 and result['new_generations'] == 224
        result['status'] = 'COMPLETE'
        result['max_GPU_memory_allocated_bytes'] = torch.cuda.max_memory_allocated()
    except BaseException as exc:
        result.update(status='FAILED', error_type=type(exc).__name__, error=str(exc)[:300], failed_phase=phase)
        raise
    finally:
        stop.set()
        result['wall_seconds'] = time.monotonic() - started
        print('KALI_BF16_240_SFT=' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
