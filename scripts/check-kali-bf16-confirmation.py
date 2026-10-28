#!/usr/bin/env python3
"""Frozen inference-only confirmation of an exact persisted BF16 adapter."""
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
              'adapter_sha256': None,
              'payload_sha256': hashlib.sha256(payload_bytes).hexdigest(),
              'new_generations': 0, 'generated_tokens': 0, 'optimizer_steps_observed': 0,
              'official_TEST_calls': 0, 'confirmation_calls': 0, 'external_teacher_calls': 0}
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
        adapter = Path(config['adapter_path'])
        assert adapter.resolve().is_relative_to(Path('/cache').resolve())
        assert sha(adapter / 'adapter_model.safetensors') == config['adapter_sha256']
        result['adapter_sha256'] = config['adapter_sha256']
        ac = json.loads((adapter / 'adapter_config.json').read_text())
        for key in ['r', 'lora_alpha', 'lora_dropout']:
            assert ac[key] == config['LoRA'][key]
        assert set(ac['target_modules']) == set(config['LoRA']['target_modules'])
        def load_model():
            nonlocal phase
            phase = 'load_BF16'
            torch.manual_seed(config['initialization_seed'])
            base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                device_map={'': 0}, torch_dtype=torch.bfloat16, attn_implementation='sdpa')
            base.requires_grad_(False)
            assert all(v.dtype == torch.bfloat16 for v in base.parameters() if v.is_floating_point())
            model = get_peft_model(base, LoraConfig(**config['LoRA']))
            params = {n: v for n, v in model.named_parameters() if v.requires_grad}
            assert params and all('lora_' in n and v.dtype == torch.float32 for n, v in params.items())
            result['initial_LoRA_sha256'] = fingerprint(params)
            assert all(v.dtype == torch.bfloat16 for n, v in model.named_parameters() if 'lora_' not in n and v.is_floating_point())
            result['loader_checks'].append({'mode': 'BF16', 'non_LoRA_FP32_parameters': 0,
                                           'LoRA_dtype': 'float32', 'only_LoRA_trainable': True})
            assert all(not value.detach().count_nonzero().item() for name, value in params.items() if 'lora_B' in name)
            model.requires_grad_(False)
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
                    assert row['set'] in ['CONFIRMATION', 'retention']
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
                    result['confirmation_calls'] += int(row['set'] == 'CONFIRMATION')
                    predictions.append({'id': row['id'], 'set': row['set'],
                        'response': tokenizer.decode(effective_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False),
                        'truncated': truncated, 'generated_tokens': len(effective_ids), 'prompt_sha256': row['prompt_sha256']})
                print('PROGRESS=' + json.dumps({'phase': phase, 'rows': len(predictions),
                                              'generations': result['new_generations']}), flush=True)
                del inputs, generated
            result['predictions'][key] = predictions

        model = load_model()
        records = payload['evaluation_rows']
        assert len(records) == 96
        infer(model, records, 'base')
        phase = 'load_existing_adapter'
        state = load_file(str(adapter / 'adapter_model.safetensors'))
        receipt = set_peft_model_state_dict(model, state, adapter_name='default')
        assert not receipt.unexpected_keys
        assert not any('lora_' in k for k in receipt.missing_keys)
        from peft import get_peft_model_state_dict
        actual = get_peft_model_state_dict(model, adapter_name='default')
        assert set(actual) == set(state)
        assert all(torch.equal(actual[k].detach().cpu(), value) for k, value in state.items())
        result['adapter_loaded_tensor_count'] = len(state)
        result['adapter_tensor_exact_match'] = True
        del state, actual
        infer(model, records, 'sft')
        assert sha(adapter / 'adapter_model.safetensors') == result['adapter_sha256']
        del model
        gc.collect()
        torch.cuda.empty_cache()
        result['new_optimizer_steps'] = 0
        assert result['new_generations'] == 192 and result['confirmation_calls'] == 144
        result['status'] = 'COMPLETE'
        result['max_GPU_memory_allocated_bytes'] = torch.cuda.max_memory_allocated()
    except BaseException as exc:
        result.update(status='FAILED', error_type=type(exc).__name__, error=str(exc)[:300], failed_phase=phase)
        raise
    finally:
        stop.set()
        result['wall_seconds'] = time.monotonic() - started
        print('KALI_BF16_CONFIRMATION=' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
