#!/usr/bin/env python3
"""Native-tokenizer LoRA runner. Tiny is actual optimizer engineering, not 8B SFT."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import signal
import subprocess
import threading
import time

from benchkit import ROOT, ARTIFACT, encode_supervision, load_manifest, load_tokenizer, sha, verify_sources, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['cisco', 'redsage'], required=True)
    p.add_argument('--dataset', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--steps', type=int, default=2)
    p.add_argument('--max-length', type=int, default=2048)
    p.add_argument('--learning-rate', type=float, default=1e-4)
    p.add_argument('--tiny', action='store_true')
    p.add_argument('--execute', action='store_true', help='Explicit real GPU research training')
    p.add_argument('--rights-record', type=Path, help='Optional model-specific usage record; not inferred from public download')
    args = p.parse_args()
    if not 1 <= args.steps <= 2000 or not 128 <= args.max_length <= 8192 or not 0 < args.learning_rate <= 1e-3:
        p.error('Training budget out of bounds')
    source = verify_sources()
    model_lock = source['models'][args.model]
    spec, rows = load_manifest(args.dataset, 'train')
    expected = 'athena' if args.model == 'cisco' else 'kali'
    if spec['benchmark'] != expected:
        p.error('Model/benchmark mismatch')
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if not args.tiny:
        if not args.execute or not torch.cuda.is_available():
            p.error('Real training requires --execute and CUDA; no weights downloaded')
        if args.rights_record:
            rights = json.loads(args.rights_record.read_text())
            if rights.get('model_id') != model_lock['id'] or rights.get('revision') != model_lock['revision']:
                p.error('Usage record does not match pinned checkpoint')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Hard training deadline')))
    signal.alarm(240 if args.tiny else 7200)
    torch.manual_seed(42)
    torch.set_num_threads(2)
    tokenizer = load_tokenizer(args.model)
    # Engineering selects two records; full training uses whole locked train file.
    selected = rows[:2] if args.tiny else rows
    encoded = [encode_supervision(tokenizer, row, args.max_length) for row in selected]
    order = list(range(len(encoded)))
    random.Random(42).shuffle(order)
    generation_differences = sum(r['native_generation_prefix_differs'] for r in encoded)
    if args.tiny:
        if args.model == 'cisco':
            from transformers import LlamaConfig, LlamaForCausalLM
            cfg = LlamaConfig(vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
                num_hidden_layers=1, num_attention_heads=4, num_key_value_heads=2, head_dim=8,
                max_position_embeddings=8192, tie_word_embeddings=True)
            base = LlamaForCausalLM(cfg)
        else:
            from transformers import Qwen3Config, Qwen3ForCausalLM
            cfg = Qwen3Config(vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
                num_hidden_layers=1, num_attention_heads=4, num_key_value_heads=2, head_dim=8,
                max_position_embeddings=8192, tie_word_embeddings=True)
            base = Qwen3ForCausalLM(cfg)
        base.save_pretrained(out / 'random-base')
    else:
        from transformers import BitsAndBytesConfig
        from peft import prepare_model_for_kbit_training
        base = AutoModelForCausalLM.from_pretrained(model_lock['id'], revision=model_lock['revision'],
            trust_remote_code=False, local_files_only=True, device_map={'': 0}, torch_dtype=torch.bfloat16,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16))
        base = prepare_model_for_kbit_training(base)
    model = get_peft_model(base, LoraConfig(r=4 if args.tiny else 16, lora_alpha=8 if args.tiny else 32,
        target_modules=['q_proj', 'v_proj'], lora_dropout=0.0, task_type='CAUSAL_LM'))
    model.config.use_cache = False
    trainable = {n: x for n, x in model.named_parameters() if x.requires_grad}
    before = {n: x.detach().cpu().clone() for n, x in trainable.items()}
    optimizer = torch.optim.AdamW(trainable.values(), lr=args.learning_rate)
    device = next(model.parameters()).device
    losses = []
    supervised_tokens = 0
    model.train()
    telemetry_stop = threading.Event()
    if not args.tiny:
        def monitor():
            while not telemetry_stop.is_set():
                try:
                    usage = subprocess.run(['nvidia-smi', '--query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
                    with (out / 'gpu-usage.jsonl').open('a') as f:
                        f.write(json.dumps({'time_utc': datetime.now(timezone.utc).isoformat(),
                                            'returncode': usage.returncode, 'gpu': usage.stdout.strip()}) + '\n')
                except Exception:
                    pass
                telemetry_stop.wait(60)
        threading.Thread(target=monitor, daemon=True).start()
    for step in range(args.steps):
        row = encoded[order[step % len(order)]]
        batch = {k: torch.tensor([row[k]], dtype=torch.long, device=device) for k in ['input_ids', 'attention_mask', 'labels']}
        optimizer.zero_grad()
        loss = model(**batch).loss
        if not torch.isfinite(loss):
            raise ValueError('Nonfinite training loss')
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable.values(), 1.0)
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
        supervised_tokens += sum(v != -100 for v in row['labels'])
    telemetry_stop.set()
    changed = [n for n, x in trainable.items() if not torch.equal(before[n], x.detach().cpu())]
    if not changed:
        raise ValueError('No trainable weights changed')
    model.save_pretrained(out / 'adapter')
    tokenizer.save_pretrained(out / 'adapter')
    model.eval()
    batch = {k: torch.tensor([encoded[0][k]], dtype=torch.long, device=device) for k in ['input_ids', 'attention_mask']}
    with torch.no_grad():
        reference = model(**batch).logits[:, -1, :].float().cpu()
    # unload() restores an unwrapped base; reload the exact persisted adapter.
    unwrapped = model.unload()
    reloaded = PeftModel.from_pretrained(unwrapped, out / 'adapter')
    reloaded.eval()
    with torch.no_grad():
        actual = reloaded(**batch).logits[:, -1, :].float().cpu()
    delta = float((reference - actual).abs().max())
    if delta > 1e-5:
        raise ValueError('Adapter reload changes logits')
    report = {'status': 'PASSED_RANDOM_TINY_ENGINEERING_ONLY' if args.tiny else 'PRETRAINED_GPU_TRAINING_COMPLETED',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'model_id': model_lock['id'],
        'intended_model_revision': model_lock['revision'], 'actual_pretrained_weights_used': not args.tiny,
        'architecture': base.config.model_type, 'random_tiny': args.tiny, 'benchmark': spec['benchmark'],
        'dataset_manifest_sha256': sha(Path(args.dataset).read_bytes()), 'records_encoded': len(encoded),
        'records_used': min(args.steps, len(encoded)), 'shuffle_seed': 42,
        'optimizer_steps': len(losses), 'losses': losses, 'supervised_tokens_processed': supervised_tokens,
        'changed_parameter_tensors': len(changed), 'adapter_reload_max_abs_logit_delta': delta,
        'generation_prefix_differs_from_final_only_training_rows': generation_differences,
        'supervision': 'Native full-chat final-answer-only; no fabricated reasoning. Generation-prefix difference is disclosed.',
        'cuda_used': not args.tiny, 'official_test_rows': 0, 'official_benchmark_score': None,
        'wall_seconds': time.monotonic() - start,
        'adapter_files': {str(p.relative_to(out / 'adapter')): sha(p.read_bytes()) for p in (out / 'adapter').iterdir() if p.is_file()},
        'torch': torch.__version__, 'limitations': ['Tiny random-model checks establish optimizer/masking/reload plumbing only.'] if args.tiny else ['Check fixed inference protocol and held-out evaluation separately.']}
    write_json(out / 'result.json', report)
    signal.alarm(0)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
