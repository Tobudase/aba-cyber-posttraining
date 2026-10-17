#!/usr/bin/env python3
"""Bounded, real-weight NF4 baseline/SFT pilot; GPU execution not yet validated."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import signal
import time
from cti_pilot_data import ROOT,PROMPT,encode_row,load_pilot,sha

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-key',choices=['qwen8_model','qwen14_model','qwen38_model'],default='qwen14_model')
    p.add_argument('--phase',choices=['baseline','sft'],required=True)
    p.add_argument('--max-seconds',type=int,default=1800,choices=range(120,3601),metavar='120..3600')
    p.add_argument('--steps',type=int,default=8,choices=range(1,33),metavar='1..32')
    args=p.parse_args()
    def timeout(*_):raise TimeoutError('Bounded pretrained pilot timed out')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(args.max_seconds)
    import torch
    from huggingface_hub import snapshot_download
    from peft import LoraConfig,PeftModel,get_peft_model,prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig,Qwen3_5ForConditionalGeneration
    from importlib.metadata import version
    started=time.monotonic();torch.manual_seed(17)
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; CPU fallback is forbidden')
    if torch.cuda.device_count()!=1:raise RuntimeError('Expose exactly one GPU for this pilot')
    spec=json.loads((ROOT/'configs/cti-candidates.lock.json').read_text())['models'][args.model_key]
    min_gib={'qwen8_model':12,'qwen14_model':16,'qwen38_model':24}[args.model_key]
    if torch.cuda.get_device_properties(0).total_memory<min_gib*1024**3:
        raise RuntimeError(f'Conservative minimum {min_gib}GiB not met; do not silently switch models')
    # A second SFT phase reuses the baseline's cache instead of requiring another
    # entire checkpoint's free space. Still validate all hashes before loading.
    cache=ROOT/'.tools/cti-gpu-hf-cache'
    cached=cache/('models--'+spec['id'].replace('/','--'))/'snapshots'/spec['revision']
    missing_bytes=sum(r['size'] for r in spec['weight_files']
        if not (cached/r['rfilename']).is_file() or (cached/r['rfilename']).stat().st_size!=r['size'])
    if shutil.disk_usage(ROOT).free < missing_bytes*1.2+5*1024**3:
        raise RuntimeError('Insufficient disk headroom for missing pinned weights/cache')
    manifest,rows=load_pilot()
    output=ROOT/'artifacts/cti-pretrained-pilot'/args.model_key;output.mkdir(parents=True,exist_ok=True)
    dest=output/(args.phase+'.json')
    if dest.exists():raise RuntimeError('Result exists: preserve it; do not overwrite a previous experiment')
    contract={'model':spec['id'],'revision':spec['revision'],'precision':'NF4-double-quant',
       'compute_dtype':'bfloat16' if torch.cuda.is_bf16_supported() else 'float16',
       'data':{s:manifest['artifacts'][s]['sha256'] for s in rows},
       'prompt_sha256':sha(PROMPT.encode()),'enable_thinking':False,'max_new_tokens':32,
       'do_sample':False,'seed':17,'max_input_tokens':1024,
       'label_quality':'SOURCE_SILVER_ASSISTANT_REVIEWED','official_test_rows':0,
       'versions':{n:version(n) for n in ['torch','transformers','peft','accelerate','bitsandbytes']}}
    if args.phase=='sft':
        if not (output/'baseline.json').is_file():raise RuntimeError('Save the unchanged-model baseline first')
        baseline=json.loads((output/'baseline.json').read_text())
        if baseline['status']!='COMPLETED' or baseline['contract']!=contract:
            raise RuntimeError('Baseline failed or protocol/model/data mismatch')
    dtype=torch.bfloat16 if contract['compute_dtype']=='bfloat16' else torch.float16
    print('STAGE=download_pinned_public_weights',flush=True)
    directory=Path(snapshot_download(spec['id'],revision=spec['revision'],token=False,
        cache_dir=cache,max_workers=2,
        allow_patterns=['*.json','*.jinja','*.safetensors','tokenizer.model','merges.txt','vocab.json','LICENSE*']))
    # Verify every published weight hash before loading; cache alone is not evidence.
    for record in spec['weight_files']:
        f=directory/record['rfilename'];h=hashlib.sha256()
        with f.open('rb') as stream:
            while chunk:=stream.read(8*1024**2):h.update(chunk)
        if h.hexdigest()!=record['lfs']['sha256']:raise RuntimeError('Weight checksum mismatch')
    metadata_lock=json.loads((ROOT/'configs/cti-reviewed-files.lock.json').read_text())
    for name in ['config.json','generation_config.json','tokenizer.json','tokenizer_config.json','chat_template.jinja']:
        entry=metadata_lock.get(args.model_key+'/'+name)
        if entry and sha((directory/name).read_bytes())!=entry['sha256']:
            raise RuntimeError('Pinned runtime metadata checksum mismatch: '+name)
    tokenizer_hashes={name:sha((directory/name).read_bytes()) for name in ['tokenizer.json','tokenizer_config.json','chat_template.jinja'] if (directory/name).is_file()}
    if args.phase=='sft' and tokenizer_hashes!=baseline['tokenizer_sha256']:
        raise RuntimeError('Tokenizer changed since baseline')
    tok=AutoTokenizer.from_pretrained(directory,trust_remote_code=False,local_files_only=True)
    loader=Qwen3_5ForConditionalGeneration if args.model_key=='qwen38_model' else AutoModelForCausalLM
    model=loader.from_pretrained(directory,trust_remote_code=False,local_files_only=True,
       dtype=dtype,device_map={'':0},attn_implementation='eager',
       quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
          bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype))
    losses=[];train_ids=[];changed=0
    if args.phase=='sft':
        # Interleave the class-blocked file so eight steps cover eight classes.
        labels=sorted({r['label'] for r in rows['train']})
        buckets={label:sorted([r for r in rows['train'] if r['label']==label],key=lambda r:r['id']) for label in labels}
        schedule=[buckets[label][i] for i in range(max(map(len,buckets.values())))
                  for label in labels if i<len(buckets[label])]
        model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
        model.config.use_cache=False
        model=get_peft_model(model,LoraConfig(task_type='CAUSAL_LM',r=8,lora_alpha=16,
                target_modules=['q_proj','v_proj'],lora_dropout=0.0))
        params=[(n,v) for n,v in model.named_parameters() if v.requires_grad]
        before={n:v.detach().cpu().clone() for n,v in params}
        optimizer=torch.optim.AdamW([v for _,v in params],lr=2e-5)
        for index in range(args.steps):
            row=schedule[index%len(schedule)]
            if not row['training_eligible']:raise RuntimeError('Training eligibility violated')
            e=encode_row(tok,row);batch={k:torch.tensor([e[k]],device='cuda') for k in ['input_ids','attention_mask','labels']}
            model.train();optimizer.zero_grad(set_to_none=True)
            loss=model(**batch).loss
            if not math.isfinite(float(loss.detach())):raise RuntimeError('Nonfinite loss')
            loss.backward()
            if not all(v.grad is None or torch.isfinite(v.grad).all() for _,v in params):raise RuntimeError('Nonfinite gradient')
            torch.nn.utils.clip_grad_norm_([v for _,v in params],1.0)
            optimizer.step();losses.append(float(loss.detach()));train_ids.append(row['id'])
            print(f'OPTIMIZER_STEP={index+1}',flush=True)
        changed=sum(not torch.equal(before[n],v.detach().cpu()) for n,v in params)
        if not changed:raise RuntimeError('No adapter parameter changed')
        adapter=output/'adapter';model.save_pretrained(adapter,safe_serialization=True)
        model.eval();batch.pop('labels')
        with torch.no_grad():expected=model(**batch).logits[:,-1].float().cpu()
        model=PeftModel.from_pretrained(model.unload(),adapter).eval()
        with torch.no_grad():actual=model(**batch).logits[:,-1].float().cpu()
        reload_diff=float((expected-actual).abs().max())
        if reload_diff>1e-3:raise RuntimeError('Adapter reload mismatch')
    predictions=[];model.eval()
    for row in rows['dev']:
        e=encode_row(tok,row);ids=e['input_ids'][:e['prompt_tokens']]
        inputs=torch.tensor([ids],device='cuda');before=time.monotonic()
        with torch.inference_mode():
            generated=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                max_new_tokens=contract['max_new_tokens'],do_sample=False,use_cache=True,pad_token_id=tok.eos_token_id)
        tail=generated[0,len(ids):].tolist()
        predictions.append({'id':row['id'],'label':row['label'],
            'output_text':tok.decode(tail,skip_special_tokens=True),
            'output_tokens':len(tail),'truncated':len(tail)>=contract['max_new_tokens'],
            'seconds':round(time.monotonic()-before,3)})
        print(f'DEV_COMPLETED={len(predictions)}',flush=True)
    report={'status':'COMPLETED','created_at_utc':datetime.now(timezone.utc).isoformat(),
       'contract':contract,'tokenizer_sha256':tokenizer_hashes,'phase':args.phase,'weights':'Real pinned pretrained checkpoint, NF4',
       'optimizer_steps':len(losses),'losses':losses,'training_ids':train_ids,
       'changed_adapter_tensors':changed,'dev_optimizer_steps':0,
       'training_order':'deterministic label round-robin, ID sorted within label',
       'adapter_reload_max_logit_difference':reload_diff if args.phase=='sft' else None,
       'records':predictions,'gpu_name':torch.cuda.get_device_name(0),
       'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),
       'elapsed_seconds':round(time.monotonic()-started,3),
       'versions':{n:version(n) for n in ['torch','transformers','peft','accelerate','bitsandbytes']},
       'scope':'EXPLORATORY_EXTERNAL_SILVER_PILOT_NOT_OFFICIAL_BENCHMARK'}
    dest.write_text(json.dumps(report,indent=2)+'\n');signal.alarm(0)
    print(json.dumps({'status':report['status'],'result':str(dest),'optimizer_steps':len(losses)}))

if __name__=='__main__':main()
