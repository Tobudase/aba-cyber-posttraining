#!/usr/bin/env python3
"""Load the pinned checkpoint on one GPU using only a benign synthetic prompt."""

import hashlib
import json
from pathlib import Path
import time


def main():
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    lock = json.loads(Path('/input/feyospace-v1.1.candidate.lock.json').read_text())
    if (lock['model_id'], lock['revision']) != (
        'feyospace/feyospace-v1.1-small',
        'ab6a8372eceb18c10357e2683ce14808217bf5e9',
    ):
        raise RuntimeError('Unexpected model identity')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable')
    start = time.monotonic()
    report = {
        'scope': 'benign_full_weight_load_only',
        'model_id': lock['model_id'], 'revision': lock['revision'],
        'gpu': torch.cuda.get_device_name(0),
        'gpu_memory_bytes': torch.cuda.get_device_properties(0).total_memory,
        'official_benchmark_tasks_used': 0, 'domain_training': False,
    }
    if report['gpu_memory_bytes'] < 75 * (1024 ** 3):
        raise RuntimeError('Requires an 80-GB-class GPU for this BF16 load check')

    patterns = list(lock['files']) + ['*.safetensors', 'model.safetensors.index.json']
    print('STAGE=download_pinned_weights', flush=True)
    model_dir = Path(snapshot_download(
        lock['model_id'], revision=lock['revision'],
        allow_patterns=patterns, max_workers=4, token=False,
    ))
    for name, expected in lock['files'].items():
        raw = (model_dir / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise RuntimeError('Pinned metadata checksum mismatch: ' + name)
    report['metadata_checksums_verified'] = len(lock['files'])
    report['weight_shards_present'] = len(list(model_dir.glob('*.safetensors')))
    if report['weight_shards_present'] != 12:
        raise RuntimeError('Unexpected weight shard count')

    print('STAGE=load_bf16', flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False,
        dtype=torch.bfloat16, device_map={'': 0}, low_cpu_mem_usage=True,
        attn_implementation='sdpa',
    ).eval()
    report['loaded_parameters'] = model.num_parameters()
    if not 27_000_000_000 <= report['loaded_parameters'] <= 29_000_000_000:
        raise RuntimeError('Loaded parameter count is outside the expected 27B class')

    messages = [{'role': 'user', 'content': 'Reply with the word OK.'}]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
    )
    inputs = tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to('cuda')
    print('STAGE=benign_generation', flush=True)
    with torch.inference_mode():
        output = model.generate(
            **inputs, max_new_tokens=32, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output.shape[-1] - inputs['input_ids'].shape[-1]
    if new_tokens <= 0:
        raise RuntimeError('No tokens generated')
    report['generated_tokens'] = int(new_tokens)
    report['response'] = tokenizer.decode(output[0, -new_tokens:], skip_special_tokens=True)[:200]
    report['peak_gpu_allocated_bytes'] = torch.cuda.max_memory_allocated()
    report['elapsed_seconds'] = round(time.monotonic() - start, 2)
    report['status'] = 'PASSED_FULL_WEIGHT_BENIGN_GENERATION'
    output_path = Path('/work/feyospace-gpu-smoke-result.json')
    output_path.write_text(json.dumps(report, indent=2) + '\n')
    print('FEYOSPACE_GPU_SMOKE_RESULT=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
