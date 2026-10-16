#!/usr/bin/env python3
"""Train/reload a random tiny Qwen3 on synthetic echo examples, on CPU only."""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import time
import torch
from datasets import Dataset
from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM, set_seed
from peft import LoraConfig, PeftModel
from trl import SFTConfig, SFTTrainer

ROOT = Path(__file__).resolve().parents[1]


def main():
    start = time.monotonic()
    torch.set_num_threads(2)
    set_seed(42)
    if torch.cuda.is_available():
        raise RuntimeError('This engineering smoke is explicitly CPU-only')
    lock = json.loads((ROOT / 'configs/student-model.lock.json').read_text())
    template_lock = json.loads((ROOT / 'configs/training-template.lock.json').read_text())
    template_path = ROOT / 'configs/templates/qwen3_training.jinja'
    if hashlib.sha256(template_path.read_bytes()).hexdigest() != template_lock['templates'][template_path.name]['sha256']:
        raise RuntimeError('Training template checksum mismatch')
    tokenizer = AutoTokenizer.from_pretrained(ROOT / lock['local_tokenizer_dir'], local_files_only=True, trust_remote_code=False)
    tokenizer.chat_template = template_path.read_text()
    tokenizer.padding_side = 'right'
    tools = [{'type': 'function', 'function': {'name': 'echo_text', 'description': 'Return the supplied text.',
              'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}},
                             'required': ['text'], 'additionalProperties': False}}}]
    rows = []
    for i, extra in enumerate(['', ' This is an intentionally longer ordinary user request.' * 3]):
        rows.append({'tools': tools, 'messages': [
            {'role': 'system', 'content': 'Use the provided echo tool.'},
            {'role': 'user', 'content': 'Echo this ordinary text.' + extra},
            {'role': 'assistant', 'content': '', 'tool_calls': [{'type': 'function', 'id': f'echo_{i}',
              'function': {'name': 'echo_text', 'arguments': {'text': 'hello'}}}]},
            {'role': 'tool', 'tool_call_id': f'echo_{i}', 'content': 'hello'},
            {'role': 'assistant', 'content': 'The echo result is hello.'}]})
    out = ROOT / 'results/tiny-lora-smoke'
    out.mkdir(parents=True, exist_ok=True)
    config = Qwen3Config(vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1, head_dim=16,
        max_position_embeddings=1024, tie_word_embeddings=True,
        bos_token_id=tokenizer.bos_token_id, eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id, attention_dropout=0.0, use_cache=False)
    model = Qwen3ForCausalLM(config)
    base = out / 'random-base'
    model.save_pretrained(base)
    args = SFTConfig(output_dir=str(out / 'trainer'), use_cpu=True, max_steps=2,
        max_length=512, per_device_train_batch_size=1, gradient_accumulation_steps=1,
        learning_rate=0.001, assistant_only_loss=True, packing=False,
        gradient_checkpointing=False, bf16=False, fp16=False, optim='adamw_torch',
        dataloader_num_workers=0, dataset_num_proc=1, logging_steps=1,
        save_strategy='no', report_to='none', seed=42, disable_tqdm=True,
        eos_token='<|im_end|>')
    dataset = Dataset.from_list(rows)
    trainer = SFTTrainer(model=model, args=args, processing_class=tokenizer,
        train_dataset=dataset,
        peft_config=LoraConfig(r=4, lora_alpha=8, lora_dropout=0.0,
                              target_modules='all-linear', task_type='CAUSAL_LM'))
    features = [trainer.train_dataset[i] for i in range(2)]
    if any(len(x['input_ids']) >= 512 for x in features):
        raise RuntimeError('Smoke examples must fit without truncation')
    batch = trainer.data_collator(features)
    masked, learned, padding = 0, 0, 0
    for i, feature in enumerate(features):
        # TRL 1.16 folds assistant_masks into labels during preparation and drops
        # the mask column. Independently tokenize the same Arrow-normalized row.
        encoded = tokenizer.apply_chat_template(dataset[i]['messages'], tools=dataset[i]['tools'],
            tokenize=True, return_dict=True, return_assistant_tokens_mask=True,
            add_generation_prompt=False, enable_thinking=False)
        mask = encoded['assistant_masks']
        if feature['input_ids'] != encoded['input_ids'] or not any(mask):
            raise RuntimeError('Trainer tokenization differs from independently generated assistant masks')
        expected_labels = [token if bit else -100 for token, bit in zip(encoded['input_ids'], mask)]
        if feature.get('labels') != expected_labels:
            raise RuntimeError('Prepared Trainer labels do not match independent assistant masks')
        for j in range(batch['input_ids'].shape[1]):
            label = batch['labels'][i, j].item()
            if j >= len(feature['input_ids']):
                if label != -100:
                    raise RuntimeError('Padding is not masked')
                padding += 1
            elif mask[j] == 0:
                if label != -100:
                    raise RuntimeError('Non-assistant token is not masked')
                masked += 1
            else:
                if label != feature['input_ids'][j]:
                    raise RuntimeError('Assistant token label mismatch')
                learned += 1
    if padding == 0 or learned == 0 or masked == 0:
        raise RuntimeError('Collator test did not cover all expected token categories')
    before = {name: p.detach().clone() for name, p in trainer.model.named_parameters() if p.requires_grad}
    total_params = sum(p.numel() for p in trainer.model.parameters())
    trainable_params = sum(p.numel() for p in trainer.model.parameters() if p.requires_grad)
    train_result = trainer.train()
    loss = float(train_result.training_loss)
    if trainer.state.global_step != 2 or not math.isfinite(loss):
        raise RuntimeError('Two-step training failed or produced non-finite loss')
    changes = [name for name, p in trainer.model.named_parameters()
               if name in before and not torch.equal(before[name], p.detach())]
    if not changes:
        raise RuntimeError('No adapter parameters changed')
    adapter = out / 'adapter'
    trainer.model.save_pretrained(adapter)
    tokenizer.save_pretrained(adapter)
    trainer.model.eval()
    probe_ids = batch['input_ids'][:1]
    probe_attention = batch['attention_mask'][:1]
    with torch.no_grad():
        expected = trainer.model(input_ids=probe_ids, attention_mask=probe_attention).logits
    reloaded_base = Qwen3ForCausalLM.from_pretrained(base, local_files_only=True)
    reloaded = PeftModel.from_pretrained(reloaded_base, adapter, is_trainable=False, local_files_only=True)
    reloaded.eval()
    with torch.no_grad():
        actual = reloaded(input_ids=probe_ids, attention_mask=probe_attention).logits
    diff = float((expected - actual).abs().max())
    if not torch.allclose(expected, actual, atol=1e-5, rtol=1e-5):
        raise RuntimeError('Reloaded adapter logits do not match')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'PASSED',
              'scope': 'CPU_SYNTHETIC_RANDOM_TINY_MODEL_ONLY', 'model_weights_downloaded': False,
              'student_8b_model_trained': False, 'domain_training_executed': False,
              'benchmark_evaluated': False, 'gpu_used': False,
              'total_parameters': total_params, 'trainable_parameters': trainable_params,
              'synthetic_records': len(rows), 'global_steps': trainer.state.global_step,
              'training_loss': loss, 'adapter_tensors_changed': len(changes),
              'collator': {'masked_context_tokens': masked, 'assistant_loss_tokens': learned,
                           'masked_padding_tokens': padding},
              'adapter_reload_max_logit_difference': diff,
              'elapsed_seconds': round(time.monotonic() - start, 3),
              'versions': {name: version(name) for name in ['torch', 'transformers', 'trl', 'peft', 'datasets', 'accelerate']},
              'limitations': ['Random tiny model has no task-solving ability; this checks training mechanics only.',
                             'No CUDA, quantization, 8B memory use or domain improvement verified.']}
    path = ROOT / 'logs/tiny-lora-smoke.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print('ENGINEERING_SMOKE_RESULT=' + json.dumps(report))


if __name__ == '__main__':
    main()
