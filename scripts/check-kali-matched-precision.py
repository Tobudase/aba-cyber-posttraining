#!/usr/bin/env python3
"""Frozen TRAIN-only 2x2 precision study, with explicit shared LoRA state."""
import concurrent.futures
import gc
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
    payload = json.loads(Path('/input/payload.json').read_text())
    config = payload['effective_config']
    started = time.monotonic()
    stop = threading.Event()
    result = {'status': 'RUNNING', 'effective_config': config, 'predictions': {},
              'training': {}, 'NLL': {}, 'samples': [], 'loader_checks': [],
              'worker_sha256': sha('/input/worker.py'),
              'optimizer_source_sha256': sha('/input/kali_sft_recipe.py'),
              'payload_sha256': sha('/input/payload.json'),
              'new_generations': 0, 'generated_tokens': 0,
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
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
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
        shared_initial = None

        def load_model(mode, training=False, adapter=None):
            nonlocal shared_initial, phase
            phase = f'load_{mode}'
            torch.manual_seed(config['initialization_seed'])
            kwargs = dict(local_files_only=True, device_map={'': 0},
                          torch_dtype=torch.bfloat16, attn_implementation='sdpa')
            if mode == 'NF4':
                kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
                    bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=False)
            base = AutoModelForCausalLM.from_pretrained(model_dir, **kwargs)
            if mode == 'NF4':
                base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=training,
                    gradient_checkpointing_kwargs={'use_reentrant': False})
            else:
                # Never call the k-bit helper here: it would upcast a BF16 base.
                base.requires_grad_(False)
                assert all(v.dtype == torch.bfloat16 for v in base.parameters() if v.is_floating_point())
                if training:
                    base.enable_input_require_grads()
                    base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
            if adapter:
                model = PeftModel.from_pretrained(base, adapter, is_trainable=False)
            else:
                model = get_peft_model(base, LoraConfig(**config['LoRA']))
                params = {name: value for name, value in model.named_parameters() if value.requires_grad}
                assert params and all('lora_' in name and v.dtype == torch.float32 for name, v in params.items())
                if shared_initial is None:
                    shared_initial = {name: v.detach().cpu().clone() for name, v in params.items()}
                    result['shared_initial_LoRA_sha256'] = fingerprint(shared_initial)
                assert set(params) == set(shared_initial)
                with torch.no_grad():
                    for name, value in params.items():
                        value.copy_(shared_initial[name].to(value.device))
                assert fingerprint(params) == result['shared_initial_LoRA_sha256']
            full_fp32 = sum(v.numel() for name, v in model.named_parameters()
                            if 'lora_' not in name and v.dtype == torch.float32)
            if mode == 'BF16':
                assert full_fp32 == 0
            result['loader_checks'].append({'mode': mode, 'training': training,
                    'adapter_loaded': bool(adapter), 'non_LoRA_FP32_parameters': full_fp32,
                    'shared_initial_copied': not bool(adapter)})
            return model

        def infer(model, key):
            nonlocal phase
            phase = 'inference_' + key
            model.eval()
            model.gradient_checkpointing_disable()
            model.config.use_cache = True
            policy = config['inference']
            predictions = []
            for offset in range(0, len(payload['TRAIN_diagnostic']), policy['batch_size']):
                batch_rows = payload['TRAIN_diagnostic'][offset:offset + policy['batch_size']]
                prompts = []
                for row in batch_rows:
                    assert row['set'] == 'TRAIN_diagnostic'
                    prompt = tokenizer.apply_chat_template(row['native_messages'], tokenize=False, add_generation_prompt=True)
                    assert prompt.endswith('<think>') and hashlib.sha256(prompt.encode()).hexdigest() == row['prompt_sha256']
                    prompts.append(prompt)
                inputs = tokenizer(prompts, padding=True, add_special_tokens=False, return_tensors='pt').to('cuda')
                for i, row in enumerate(batch_rows):
                    native_ids = inputs['input_ids'][i][inputs['attention_mask'][i].bool()].tolist()
                    encoded = next(x for x in rows if x['id'] == row['id'])
                    assert native_ids == encoded['input_ids'][:encoded['prompt_tokens']]
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

        for mode in ['NF4', 'BF16']:
            model = load_model(mode)
            infer(model, 'base_' + mode)
            del model
            gc.collect()
            torch.cuda.empty_cache()
        for arm in config['arms']:
            name, mode = arm['name'], arm['training_precision']
            model = load_model(mode, training=True)
            initial_sha = fingerprint({n: v for n, v in model.named_parameters() if v.requires_grad})
            nll(model, name + '_before')
            phase = 'train_' + name
            model.config.use_cache = False

            def progress(step):
                if step['step'] == 1 or step['step'] % 8 == 0:
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
            receipt.update({'training_precision': mode, 'initial_LoRA_sha256': initial_sha,
                            'adapter_reload_max_logit_delta': delta,
                            'adapter_sha256': sha(out / 'adapter/adapter_model.safetensors')})
            result['training'][name] = receipt
            (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            del ref, actual, state, probe
            nll(model, name + '_after')
            infer(model, name + '_' + mode)
            del model
            gc.collect()
            torch.cuda.empty_cache()
            other = 'BF16' if mode == 'NF4' else 'NF4'
            model = load_model(other, adapter=out / 'adapter')
            infer(model, name + '_' + other)
            del model
            gc.collect()
            torch.cuda.empty_cache()
        result['new_optimizer_steps'] = sum(x['optimizer_steps'] for x in result['training'].values())
        assert result['new_optimizer_steps'] == 256 and result['new_generations'] == 48
        assert len({x['initial_LoRA_sha256'] for x in result['training'].values()}) == 1
        result['status'] = 'COMPLETE'
        result['max_GPU_memory_allocated_bytes'] = torch.cuda.max_memory_allocated()
    except BaseException as exc:
        result.update(status='FAILED', error_type=type(exc).__name__, error=str(exc)[:300], failed_phase=phase)
        raise
    finally:
        stop.set()
        result['wall_seconds'] = time.monotonic() - started
        print('KALI_MATCHED_PRECISION=' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
