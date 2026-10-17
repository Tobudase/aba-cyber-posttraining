#!/usr/bin/env python3
"""Two real optimizer steps on source-silver rows with RANDOM TINY weights only."""
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
from pathlib import Path
import signal
import time

from cti_pilot_data import ROOT,encode_row,load_pilot,sha

def main():
    def timeout(*_): raise TimeoutError('Engineering check exceeded 180 seconds')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(180)
    started=time.monotonic()
    import torch
    from peft import LoraConfig,PeftModel,get_peft_model
    from transformers import AutoTokenizer,Qwen3_5ForCausalLM,Qwen3_5TextConfig
    torch.set_num_threads(2);torch.manual_seed(17)
    manifest,rows=load_pilot()
    directory=ROOT/'.tools/cti-review/qwen38_model'
    source_lock=json.loads((ROOT/'configs/cti-reviewed-files.lock.json').read_text())
    for name in ['tokenizer.json','tokenizer_config.json','chat_template.jinja']:
        assert sha((directory/name).read_bytes())==source_lock['qwen38_model/'+name]['sha256']
    tokenizer=AutoTokenizer.from_pretrained(directory,trust_remote_code=False,local_files_only=True)
    packed={s:[(r,encode_row(tokenizer,r)) for r in rs] for s,rs in rows.items()}
    assert all(all(v==-100 for v in e['labels'][:e['prompt_tokens']]) and any(v!=-100 for v in e['labels']) for rs in packed.values() for r,e in rs)
    guards={}
    try: encode_row(tokenizer,rows['train'][0],max_tokens=1)
    except ValueError: guards['no_silent_truncation']=True
    else: raise AssertionError('Truncation guard failed')
    # Different real training descriptions, selected by length only to bound CPU cost.
    examples=sorted(packed['train'],key=lambda p:(len(p[1]['input_ids']),p[0]['id']))[:2]
    cfg=Qwen3_5TextConfig(vocab_size=len(tokenizer),hidden_size=64,intermediate_size=128,
       num_hidden_layers=4,num_attention_heads=4,num_key_value_heads=2,head_dim=16,
       linear_num_key_heads=2,linear_num_value_heads=4,linear_key_head_dim=16,
       linear_value_head_dim=16,max_position_embeddings=1024,
       layer_types=['linear_attention','linear_attention','linear_attention','full_attention'],partial_rotary_factor=0.5)
    base=Qwen3_5ForCausalLM(cfg);base.config.use_cache=False
    model=get_peft_model(base,LoraConfig(task_type='CAUSAL_LM',r=4,lora_alpha=8,
       target_modules=['q_proj','v_proj'],lora_dropout=0.0))
    trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    initial={n:p.detach().clone() for n,p in trainable}
    optimizer=torch.optim.AdamW([p for _,p in trainable],lr=1e-3)
    losses=[];training_ids=[]
    for row,encoded in examples:
        print('OPTIMIZER_STEP '+row['id'],flush=True)
        assert row['training_eligible'] and row['split']=='train'
        batch={k:torch.tensor([encoded[k]],dtype=torch.long) for k in ['input_ids','attention_mask','labels']}
        model.train();optimizer.zero_grad(set_to_none=True)
        loss=model(**batch).loss
        assert math.isfinite(float(loss.detach()))
        loss.backward()
        assert all(p.grad is None or torch.isfinite(p.grad).all() for _,p in trainable)
        optimizer.step();losses.append(float(loss.detach()));training_ids.append(row['id'])
    changed=sum(not torch.equal(initial[n],p.detach()) for n,p in trainable)
    assert changed>0
    out=ROOT/'artifacts/cti-source-pilot-tiny-adapter';out.mkdir(parents=True,exist_ok=True)
    model.save_pretrained(out,safe_serialization=True)
    model.eval();batch.pop('labels')
    with torch.no_grad(): expected=model(**batch).logits[:,-1].float()
    base=model.unload();reloaded=PeftModel.from_pretrained(base,out).eval()
    with torch.no_grad(): actual=reloaded(**batch).logits[:,-1].float()
    diff=float((expected-actual).abs().max());assert diff<=1e-6
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASSED_ENGINEERING_ONLY',
       'weights':'RANDOM TINY Qwen3.5 architecture; NOT pretrained Qwen3.8-27B',
       'domain_model_posttraining_completed':False,'official_test_rows':0,
       'data_quality':'Assistant-reviewed SOURCE-SILVER, not expert gold',
       'frozen_pilot_sha256':{s:manifest['artifacts'][s]['sha256'] for s in rows},
       'packed_counts':{s:len(v) for s,v in packed.items()},
       'max_sequence_tokens':max(len(e['input_ids']) for rs in packed.values() for r,e in rs),
       'assistant_only_loss':True,'silent_truncation':False,'guards':guards,
       'optimizer_steps':2,'training_ids':training_ids,'dev_optimizer_steps':0,
       'losses_different_examples_not_learning_curve':losses,'changed_adapter_tensors':changed,
       'adapter_reload_max_logit_difference':diff,
       'adapter_sha256':sha((out/'adapter_model.safetensors').read_bytes()),
       'versions':{n:version(n) for n in ['torch','transformers','peft','accelerate']},
       'elapsed_seconds':round(time.monotonic()-started,3),
       'limitations':['No trained-model accuracy is claimed.','Tiny random architecture verifies data/loss/adapter mechanics only.',
         'No official benchmark evaluation or full pretrained-model training occurred.']}
    (ROOT/'docs/verification/cti-source-pilot-training-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));signal.alarm(0)

if __name__=='__main__':main()
