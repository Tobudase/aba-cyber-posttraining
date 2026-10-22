#!/usr/bin/env python3
"""Pinned HF dev inference with receipts; real 8B requires CUDA before any weights fetch."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import time

from benchkit import (ROOT, load_manifest, load_tokenizer, sha, verify_sources, write_json, write_jsonl)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['cisco', 'redsage'], required=True)
    p.add_argument('--dataset', required=True); p.add_argument('--split', required=True)
    p.add_argument('--output', required=True); p.add_argument('--adapter', type=Path)
    p.add_argument('--random-base', type=Path, help='Previously saved tiny random base; engineering only')
    p.add_argument('--max-output-tokens', type=int, default=2048)
    p.add_argument('--execute', action='store_true')
    args = p.parse_args()
    if args.split == 'train': p.error('This entrypoint is for dev inference, not train scoring')
    if not 1 <= args.max_output_tokens <= 8192: p.error('Generation budget out of bounds')
    source = verify_sources(); spec, rows = load_manifest(args.dataset, args.split)
    expected = 'athena' if args.model == 'cisco' else 'kali'
    if spec['benchmark'] != expected: p.error('Model/benchmark mismatch')
    import torch
    from transformers import AutoModelForCausalLM
    from peft import PeftModel
    tiny = args.random_base is not None
    if not tiny and (not args.execute or not torch.cuda.is_available()):
        p.error('Real inference requires --execute and CUDA; no weights fetched')
    if tiny:
        cfg = json.loads((args.random_base / 'config.json').read_text())
        if cfg.get('hidden_size') != 32 or cfg.get('num_hidden_layers') != 1:
            p.error('Only the saved bounded tiny model is accepted on CPU')
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(42); torch.set_num_threads(2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Inference hard deadline')))
    signal.alarm(240 if tiny else 7200)
    lock = source['models'][args.model]
    tokenizer = load_tokenizer(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.random_base, local_files_only=True, trust_remote_code=False) if tiny else AutoModelForCausalLM.from_pretrained(
        lock['id'], revision=lock['revision'], trust_remote_code=False, local_files_only=True, torch_dtype=torch.bfloat16, device_map={'': 0})
    if args.adapter:
        receipt = json.loads((args.adapter.parent / 'result.json').read_text())
        if receipt['model_id'] != lock['id'] or receipt['random_tiny'] != tiny or receipt['intended_model_revision'] != lock['revision']:
            p.error('Adapter belongs to different base model or engineering scope')
        for name, checksum in receipt.get('adapter_files', {}).items():
            if sha((args.adapter / name).read_bytes()) != checksum:
                p.error('Saved adapter/tokenizer artifact changed')
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    device = next(model.parameters()).device
    selected = rows[:2] if tiny else rows
    records = []
    start = time.monotonic()
    for r in selected:
        prompt = tokenizer.apply_chat_template(r['messages'], tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(prompt, add_special_tokens=False, return_tensors='pt')
        length = encoded['input_ids'].shape[-1]
        if length + args.max_output_tokens > model.config.max_position_embeddings:
            raise ValueError('Input+output context exceeds model capacity; no silent truncation')
        before = time.monotonic()
        with torch.no_grad():
            result = model.generate(**{k: v.to(device) for k, v in encoded.items()},
                max_new_tokens=args.max_output_tokens, do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
        new = result[0, length:]
        # Preserve delimiters/EOS for auditable parsing. Labels never passed to generate().
        text = tokenizer.decode(new, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        records.append({'id': r['id'], 'response': text,
            'raw_response_with_special_tokens': tokenizer.decode(new, skip_special_tokens=False, clean_up_tokenization_spaces=False),
            'prompt_sha256': sha(prompt.encode()),
            'input_tokens': length, 'output_tokens': len(new),
            'truncated': len(new) >= args.max_output_tokens, 'wall_seconds': time.monotonic() - before,
            'actual_pretrained_weights_used': not tiny})
        write_jsonl(out / 'predictions.jsonl', records)
    elapsed = time.monotonic() - start
    receipt = {'status': 'RANDOM_TINY_GENERATION_ENGINEERING_ONLY' if tiny else 'PRETRAINED_DEV_INFERENCE_COMPLETED',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'model_id': lock['id'], 'revision': lock['revision'],
        'actual_pretrained_weights_used': not tiny, 'adapter': str(args.adapter) if args.adapter else None,
        'dataset_manifest_sha256': sha(Path(args.dataset).read_bytes()), 'split': args.split,
        'expected_rows': len(selected), 'actual_rows': len(records), 'full_split': not tiny,
        'max_output_tokens': args.max_output_tokens, 'temperature': 0, 'seed': 42,
        'dtype': str(next(model.parameters()).dtype), 'batch_size': 1,
        'prompt_template_sha256': sha(tokenizer.chat_template.encode()), 'fix_mistral_regex': False,
        'answer_labels_exposed_to_generate': False, 'official_test_rows': 0,
        'generation_wall_seconds': elapsed, 'samples_per_second': len(records) / elapsed,
        'cuda_peak_memory_bytes': torch.cuda.max_memory_allocated() if not tiny else 0,
        'predictions_sha256': sha((out / 'predictions.jsonl').read_bytes()),
        'limitations': ['Tiny generation is not an 8B model baseline and not throughput evidence for the full model.'] if tiny else ['Local frozen dev protocol; not directly a leaderboard reproduction.']}
    write_json(out / 'receipt.json', receipt)
    signal.alarm(0)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__': main()
