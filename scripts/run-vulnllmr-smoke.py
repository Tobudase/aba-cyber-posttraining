#!/usr/bin/env python3
"""Bounded single-GPU, four train-only samples; no training, tools, or code execution."""
import hashlib
import json
import os
import time
from pathlib import Path

from vulnllmr_metrics import parse_answer, score


def main():
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

    source = Path('/input')
    lock = json.loads((source / 'vulnllmr.lock.json').read_text())
    samples_bytes = (source / 'vulnllmr-development-smoke.json').read_bytes()
    assert hashlib.sha256(samples_bytes).hexdigest() == lock['sample_manifest_sha256']
    samples = json.loads(samples_bytes)['samples']
    assert len(samples) == 4 and all(x['role'] == 'development_smoke_only' for x in samples)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; refusing CPU fallback for full model')
    set_seed(42)
    started = time.monotonic()
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    print('STAGE=' + json.dumps({'stage': 'download', 'model': lock['model_id'], 'revision': lock['revision'],
                                 'gpu': torch.cuda.get_device_name(0), 'dtype': str(dtype)}), flush=True)
    # Only standard model tensors/config/tokenizer. No pickle or remote Python code.
    model_dir = snapshot_download(lock['model_id'], revision=lock['revision'], token=False, max_workers=2,
        allow_patterns=['*.safetensors', '*.json', 'merges.txt', 'vocab.json'],
        ignore_patterns=['trainer_state.json', 'all_results.json', 'train_results.json'])
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    print('STAGE=load', flush=True)
    model = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False,
        torch_dtype=dtype, device_map={'': 0}, attn_implementation='sdpa', low_cpu_mem_usage=True)
    model.eval()
    assert sum(p.numel() for p in model.parameters()) == lock['parameters']
    rows = []
    for sample in samples:
        text = tokenizer.apply_chat_template([{'role': 'user', 'content': sample['prompt']}],
                                             tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors='pt', add_special_tokens=False).to('cuda:0')
        length = inputs['input_ids'].shape[-1]
        if length > lock['inference']['max_input_tokens']:
            raise RuntimeError('Input exceeds fixed budget; never silently truncate')
        t0 = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=lock['inference']['max_new_tokens'],
                do_sample=False, temperature=None, top_p=None, top_k=None, use_cache=True,
                pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
        continuation = generated[0, length:]
        output = tokenizer.decode(continuation, skip_special_tokens=True)
        row = {'id': sample['id'], 'target': sample['target'], 'gold_cwes': sample['gold_cwes'],
               'output': output, 'parsed': parse_answer(output), 'input_tokens': length,
               'output_tokens': len(continuation), 'seconds': round(time.monotonic() - t0, 3),
               'budget_exhausted': len(continuation) >= lock['inference']['max_new_tokens']}
        rows.append(row)
        print('SMOKE_SAMPLE=' + json.dumps(row), flush=True)
    report = {'status': 'ENGINEERING_INFERENCE_COMPLETED', 'scope': '4 train-only development samples; not paper reproduction or held-out benchmark',
        'model_id': lock['model_id'], 'revision': lock['revision'], 'torch': torch.__version__,
        'transformers': transformers.__version__, 'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(0),
        'dtype': str(dtype), 'parameters': sum(p.numel() for p in model.parameters()),
        'max_gpu_allocated_bytes': torch.cuda.max_memory_allocated(), 'seconds': round(time.monotonic() - started, 3),
        'inference': lock['inference'], 'metrics': score(rows), 'rows': rows,
        'formal_test_used': False, 'training_executed': False}
    Path('/work/result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('VULNLLMR_SMOKE_RESULT=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
