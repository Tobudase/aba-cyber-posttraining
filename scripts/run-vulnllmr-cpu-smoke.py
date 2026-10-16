#!/usr/bin/env python3
"""Full public 7B checkpoint on CPU; short constrained decoding, no training."""
import hashlib
import ctypes
import gc
import json
import time
from pathlib import Path
from vulnllmr_metrics import parse_answer, score


def main():
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    set_seed(42)
    lock = json.loads(Path('/input/runtime.lock.json').read_text())
    raw = Path('/input/samples.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == lock['sample_sha256']
    samples = json.loads(raw)
    assert len(samples) == 4
    started = time.monotonic()
    print('STAGE=download_cpu', flush=True)
    model_dir = snapshot_download(lock['model_id'], revision=lock['revision'], token=False, max_workers=2,
        allow_patterns=['*.safetensors', '*.json', 'merges.txt', 'vocab.json'],
        ignore_patterns=['trainer_state.json', 'all_results.json', 'train_results.json'])
    print('STAGE=load_cpu_bf16', flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.bfloat16, device_map={'': 'cpu'}, low_cpu_mem_usage=True, attn_implementation='sdpa')
    model.eval()
    parameters = sum(p.numel() for p in model.parameters())
    assert parameters == lock['parameters']
    print('STAGE=' + json.dumps({'stage': 'loaded', 'parameters': parameters,
                                 'load_seconds': round(time.monotonic() - started, 3)}), flush=True)
    converted = 0
    if lock.get('quantization') == 'torch_dynamic_qint8_linear':
        # Convert one layer at a time, avoiding a full FP32 30GB intermediate.
        def quantize_linears(module):
            nonlocal converted
            for name, child in list(module.named_children()):
                if isinstance(child, torch.nn.Linear):
                    wrapper = torch.nn.Sequential(child.float())
                    torch.ao.quantization.quantize_dynamic(wrapper, {torch.nn.Linear},
                        dtype=torch.qint8, inplace=True)
                    setattr(module, name, wrapper[0])
                    converted += 1
                    if converted % 14 == 0:
                        gc.collect()
                        ctypes.CDLL('libc.so.6').malloc_trim(0)
                        print('STAGE=' + json.dumps({'stage': 'quantizing', 'layers': converted,
                            'seconds': round(time.monotonic() - started, 3)}), flush=True)
                else:
                    quantize_linears(child)
        quantize_linears(model)
        model.float()  # Remaining embeddings/norms feed FP32 activations to dynamic INT8 linear layers.
        assert converted > 0
        print('STAGE=' + json.dumps({'stage': 'int8_converted', 'linear_layers': converted,
                                     'seconds': round(time.monotonic() - started, 3)}), flush=True)
    rows = []
    for sample in samples:
        assert sample['assignment'] == 'proposal_train' and not sample['human_marker']
        messages = [{'role': 'user', 'content': sample['prompt']},
                    {'role': 'assistant', 'content': '## Final Answer\n#judge:'}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, continue_final_message=True)
        inputs = tokenizer(text, return_tensors='pt', add_special_tokens=False)
        assert inputs['input_ids'].shape[-1] <= 1024
        t0 = time.monotonic()
        generation_kwargs = {}
        if lock.get('output_grammar') == 'binary_judge_and_task_cwe':
            # Fixed task-level answer grammar, constructed without sample target labels.
            # The same two choices are supplied for every sample of a task CWE.
            task_cwe = sample['source_path'].rsplit('/', 1)[-1].removesuffix('.json')
            if task_cwe not in {'CWE-295', 'CWE-400'}:
                raise RuntimeError('Unexpected engineering task scope')
            endings = [' yes\n#type: ' + task_cwe, ' no\n#type: N/A']
            prefix_ids = inputs['input_ids'][0].tolist()
            options = []
            for ending in endings:
                encoded = tokenizer(text + ending, add_special_tokens=False)['input_ids']
                assert encoded[:len(prefix_ids)] == prefix_ids
                options.append(encoded[len(prefix_ids):] + [tokenizer.eos_token_id])
            def allowed_tokens(batch_id, input_ids):
                suffix = input_ids[len(prefix_ids):].tolist()
                next_ids = {option[len(suffix)] for option in options
                            if len(suffix) < len(option) and option[:len(suffix)] == suffix}
                if not next_ids:
                    raise RuntimeError('Generation left the fixed answer grammar')
                return sorted(next_ids)
            generation_kwargs['prefix_allowed_tokens_fn'] = allowed_tokens
        with torch.inference_mode():
            logits = model(**inputs, use_cache=False).logits[:, -1, :]
            assert torch.isfinite(logits).all().item()
            generated = model.generate(**inputs, do_sample=False, temperature=None, top_p=None, top_k=None,
                max_new_tokens=32, use_cache=True, pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id, **generation_kwargs)
        continuation = generated[0, inputs['input_ids'].shape[-1]:]
        output = '## Final Answer\n#judge:' + tokenizer.decode(continuation, skip_special_tokens=True)
        row = {'id': sample['id'], 'target': sample['target'], 'gold_cwes': sample['cwes'],
               'output': output, 'parsed': parse_answer(output), 'output_tokens': len(continuation),
               'seconds': round(time.monotonic() - t0, 3), 'budget_exhausted': len(continuation) == 32}
        rows.append(row)
        print('SMOKE_SAMPLE=' + json.dumps(row), flush=True)
    report = {'status': 'FULL_CHECKPOINT_CPU_INFERENCE_COMPLETED', 'device': 'cpu',
        'dtype': 'qint8 linear weights / fp32 activations' if converted else 'bfloat16',
        'quantization': lock.get('quantization'), 'quantized_linear_layers': converted,
        'output_grammar': lock.get('output_grammar'),
        'scope': 'engineering only: 4 train-source samples, 32 tokens each, assistant final-answer prefill; no benchmark reproduction',
        'model_id': lock['model_id'], 'revision': lock['revision'], 'parameters': parameters,
        'torch': torch.__version__, 'transformers': transformers.__version__, 'cpu_threads': torch.get_num_threads(),
        'seconds': round(time.monotonic() - started, 3), 'rows': rows, 'metrics': score(rows),
        'formal_test_used': False, 'training_executed': False, 'gpu_verified': False}
    Path('/work/result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('VULNLLMR_SMOKE_RESULT=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
