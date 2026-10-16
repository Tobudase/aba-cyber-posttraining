#!/usr/bin/env python3
"""Bounded synthetic compatibility/LoRA smoke; never reads CyberGym tasks."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['cpu', 'gpu'], required=True)
    args = parser.parse_args()
    import torch
    from huggingface_hub import snapshot_download
    from importlib.metadata import version
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForCausalLM,
                              Qwen3_5ForConditionalGeneration, Qwen3_5TextConfig)

    torch.set_num_threads(2)
    torch.manual_seed(17)
    root = Path('/work')
    lock = json.loads(Path('/input/selected-model.lock.json').read_text())
    start = time.monotonic()
    report = {'scope': 'synthetic_engineering_only', 'mode': args.mode,
              'selected_model': lock['model_id'], 'revision': lock['revision'],
              'official_tasks_used': 0, 'domain_training': False,
              'versions': {n: version(n) for n in ['torch', 'transformers', 'peft', 'accelerate']}}
    patterns = list(lock['files'])
    if args.mode == 'gpu':
        if not torch.cuda.is_available():
            raise RuntimeError('GPU requested but CUDA unavailable')
        report['gpu'] = torch.cuda.get_device_name(0)
        report['gpu_memory_bytes'] = torch.cuda.get_device_properties(0).total_memory
        patterns += ['*.safetensors', 'model.safetensors.index.json', 'preprocessor_config.json', 'processor_config.json']
    print('STAGE=download_' + args.mode, flush=True)
    model_dir = Path(snapshot_download(lock['model_id'], revision=lock['revision'],
                                      allow_patterns=patterns, max_workers=4, token=False))
    for name, item in lock['files'].items():
        if hashlib.sha256((model_dir / name).read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError('Pinned metadata checksum mismatch: ' + name)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=False)
    prompt = [{'role': 'user', 'content': 'Reply with TEST_OK.'}]
    complete = prompt + [{'role': 'assistant', 'content': 'TEST_OK'}]
    prefix = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full = tokenizer.apply_chat_template(complete, tokenize=False, add_generation_prompt=False, enable_thinking=False)
    if not full.startswith(prefix):
        raise RuntimeError('Assistant completion is not a prefix-preserving extension')
    encoded = tokenizer(full, return_tensors='pt', add_special_tokens=False)
    prefix_ids = tokenizer(prefix, add_special_tokens=False)['input_ids']
    if encoded['input_ids'][0, :len(prefix_ids)].tolist() != prefix_ids:
        raise RuntimeError('Token prefix not preserved')
    if encoded['input_ids'].shape[1] > 128:
        raise RuntimeError('Synthetic sequence exceeded 128-token bound')
    labels = encoded['input_ids'].clone()
    labels[:, :len(prefix_ids)] = -100
    assert (labels != -100).any()
    tool = {'type': 'function', 'function': {'name': 'add_numbers', 'description': 'Add two integers.',
            'parameters': {'type': 'object', 'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
                           'required': ['a', 'b'], 'additionalProperties': False}}}
    tool_messages = [prompt[0], {'role': 'assistant', 'content': '', 'tool_calls': [
        {'type': 'function', 'function': {'name': 'add_numbers', 'arguments': {'a': 7, 'b': 8}}}]},
        {'role': 'tool', 'content': '{"sum":15}'}, {'role': 'assistant', 'content': '15'}]
    rendered = tokenizer.apply_chat_template(tool_messages, tools=[tool], tokenize=False,
                                              add_generation_prompt=False, enable_thinking=False)
    assert '<function=add_numbers>' in rendered and '<tool_response>' in rendered
    report['template'] = {'token_prefix_preserved': True, 'tool_serialization_passed': True,
                          'masked_prompt_tokens': len(prefix_ids),
                          'supervised_tokens': int((labels != -100).sum()),
                          'official_generation_tags': any(tag in tokenizer.chat_template for tag in ('{% generation', '{%- generation'))}
    print('STAGE=load_' + args.mode, flush=True)
    if args.mode == 'cpu':
        cfg = Qwen3_5TextConfig(vocab_size=len(tokenizer), hidden_size=64, intermediate_size=128,
            num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2, head_dim=16,
            linear_num_key_heads=2, linear_num_value_heads=4, linear_key_head_dim=16,
            linear_value_head_dim=16, max_position_embeddings=1024,
            layer_types=['linear_attention', 'linear_attention', 'linear_attention', 'full_attention'],
            partial_rotary_factor=0.5)
        base = Qwen3_5ForCausalLM(cfg)
        report['weights'] = 'random tiny architecture; NOT pretrained 27B weights'
    else:
        base = Qwen3_5ForConditionalGeneration.from_pretrained(model_dir, trust_remote_code=False,
            dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='eager',
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
        report['weights'] = 'actual pinned pretrained 27B, NF4 quantization'
        base.eval()
        generation_input = tokenizer(prefix, return_tensors='pt', add_special_tokens=False).to('cuda')
        with torch.no_grad():
            out = base.generate(**generation_input, max_new_tokens=24, do_sample=False,
                                pad_token_id=tokenizer.eos_token_id)
        response = tokenizer.decode(out[0, generation_input['input_ids'].shape[1]:], skip_special_tokens=True)
        report['generation'] = {'expected': 'TEST_OK', 'response': response,
                                'passed': response.strip() == 'TEST_OK'}
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=False)
    base.config.use_cache = False
    report['base_parameters'] = base.num_parameters()
    model = get_peft_model(base, LoraConfig(task_type='CAUSAL_LM', r=4, lora_alpha=8,
                                           target_modules=['q_proj', 'v_proj'], lora_dropout=0.0))
    model.train()
    trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    before = {n: p.detach().cpu().clone() for n, p in trainable}
    opt = torch.optim.AdamW([p for _, p in trainable], lr=1e-3)
    dev = next(model.parameters()).device
    batch = {k: v.to(dev) for k, v in encoded.items()}
    losses = []
    print('STAGE=two_synthetic_lora_steps', flush=True)
    for _ in range(2):
        opt.zero_grad(set_to_none=True)
        loss = model(**batch, labels=labels.to(dev)).loss
        value = float(loss.detach())
        if not math.isfinite(value):
            raise RuntimeError('Nonfinite loss')
        loss.backward()
        if not all(p.grad is None or torch.isfinite(p.grad).all() for _, p in trainable):
            raise RuntimeError('Nonfinite gradient')
        opt.step()
        losses.append(value)
    changed = sum(not torch.equal(before[n], p.detach().cpu()) for n, p in trainable)
    if not changed:
        raise RuntimeError('No adapter parameter changed')
    save_dir = root / 'selected-model-smoke-adapter'
    model.save_pretrained(save_dir, safe_serialization=True)
    model.eval()
    with torch.no_grad():
        expected = model(**batch).logits[:, -1].float().cpu()
    # Unload/reload the same adapter; no second base-model allocation.
    base_after = model.unload()
    reloaded = PeftModel.from_pretrained(base_after, save_dir).eval()
    with torch.no_grad():
        actual = reloaded(**batch).logits[:, -1].float().cpu()
    diff = float((actual - expected).abs().max())
    if diff > 1e-3:
        raise RuntimeError('Adapter reload changed logits')
    report['lora'] = {'steps': 2, 'losses': losses, 'changed_tensors': changed,
                      'trainable_parameters': sum(p.numel() for _, p in trainable),
                      'reload_max_logit_difference': diff}
    if args.mode == 'gpu':
        report['peak_allocated_bytes'] = torch.cuda.max_memory_allocated()
    report['elapsed_seconds'] = round(time.monotonic() - start, 3)
    report['status'] = 'PASSED'
    (root / 'selected-model-test-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('SELECTED_MODEL_TEST_RESULT=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
