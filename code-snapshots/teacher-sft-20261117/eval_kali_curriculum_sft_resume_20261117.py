"""Inference only. No evaluation reference or training target is loaded here."""
import argparse,hashlib,json,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--model-path',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--adapter',type=Path);p.add_argument('--resume-prefix',action='store_true');a=p.parse_args();assert not a.output.exists() or a.resume_prefix and not a.adapter
    proto=json.loads((a.stage/'evaluation-protocol.json').read_text());f=a.stage/'evaluation-inputs-private.json';assert hashlib.sha256(f.read_bytes()).hexdigest()==proto['input_sha256'];rows=json.loads(f.read_text());assert len(rows)==len({r['id'] for r in rows})==proto['rows']
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    tok=AutoTokenizer.from_pretrained(a.model_path,local_files_only=True,trust_remote_code=False);tok.padding_side='left';tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(a.model_path,local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa');adapter_hash=None
    if a.adapter:
        receipt=json.loads((a.adapter.parent/'receipt.json').read_text());adapter_hash=hashlib.sha256((a.adapter/'adapter_model.safetensors').read_bytes()).hexdigest();assert receipt['adapter_sha256']==adapter_hash
        model=PeftModel.from_pretrained(model,a.adapter,is_trainable=False)
    model.eval();model.requires_grad_(False);torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=False;reload_audit=None
    if a.adapter:
        from kali_exact_adapter_loading_20261115 import load_exact_adapter
        reload_audit=load_exact_adapter(model,a.adapter,'default',is_trainable=False)
        probe=torch.tensor([receipt['reload_probe_input_ids']],device='cuda')
        with torch.inference_mode():logits=model(input_ids=probe,use_cache=False).logits[:,-1].float().cpu()
        assert hashlib.sha256(logits.numpy().tobytes()).hexdigest()==receipt['reload_probe_logits_sha256'],'Reloaded model differs from trained adapter probe'
        reload_audit['trained_vs_reloaded_probe_identical']=True
    previous=json.loads(a.output.read_text()) if a.resume_prefix else None
    prefix=previous['predictions'] if previous else []
    expected=[(seed,mode,r['id']) for seed in proto['seeds'] for mode in proto['modes'] for r in rows]
    assert [(r['sampling_seed'],r['mode'],r['id']) for r in prefix]==expected[:len(prefix)]
    boundaries=set();n=0
    for _seed in proto['seeds']:
        for _mode in proto['modes']:
            for _off in range(0,len(rows),proto['batch_size']):
                n+=len(rows[_off:_off+proto['batch_size']]);boundaries.add(n)
    if prefix:assert len(prefix) in boundaries and previous.get('adapter_sha256') is None
    allrows=[];began=time.monotonic();replay_audit=None;old_seconds=0

    for sampling_seed in proto['seeds']:
        for mode in proto['modes']:
            thinking=mode=='thinking';gen=proto['generation'][mode]
            for off in range(0,len(rows),proto['batch_size']):
                batch=rows[off:off+proto['batch_size']]
                keys={(r['sampling_seed'],r['mode'],r['id']) for r in allrows}
                batchkeys={(sampling_seed,mode,r['id']) for r in batch}
                if batchkeys<=keys:continue
                assert not batchkeys&keys,'Partial batch in resume prefix'
                texts=[tok.apply_chat_template(r['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=thinking) for r in batch];x=tok(texts,add_special_tokens=False,padding=True,return_tensors='pt').to('cuda');width=x.input_ids.shape[1];seed=sampling_seed+off;torch.manual_seed(seed)
                with torch.inference_mode():y=model.generate(**x,max_new_tokens=proto['max_new_tokens'],do_sample=True,temperature=gen['temperature'],top_p=gen['top_p'],top_k=20,min_p=0.,use_cache=True,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id)
                for r,body in zip(batch,y[:,width:].cpu().tolist()):
                    stopped=tok.eos_token_id in body;body=body[:body.index(tok.eos_token_id)] if stopped else body;raw=tok.decode(body,skip_special_tokens=False,clean_up_tokenization_spaces=False)
                    content=raw.split('</think>',1)[1] if '</think>' in raw else '' if thinking or '<think>' in raw else raw
                    allrows.append({'id':r['id'],'panel':r['panel'],'mode':mode,'sampling_seed':sampling_seed,'content':content,'response':raw,'finish_reason':'stop' if stopped else 'length','generated_tokens':len(body),'seed':seed})
                if prefix and replay_audit is None:
                    replay_count=len(batch);fields=['id','panel','mode','sampling_seed','content','response','finish_reason','generated_tokens','seed']
                    identical=len(prefix)>=replay_count and all(all(a0.get(k)==b0.get(k) for k in fields) for a0,b0 in zip(allrows,prefix[:replay_count]))
                    replay_audit={'first_batch_replay_identical':identical,'replayed_responses':replay_count,'prior_prefix_responses':len(prefix),'reused_prior_responses':len(prefix) if identical else 0,'rule':'If any first-batch token/output differs, discard old prefix and continue a full fresh baseline, no score inspection'}
                    if identical:allrows=prefix;old_seconds=previous['seconds']
                    (a.output.parent/'baseline-prefix-replay-audit.json').write_text(json.dumps(replay_audit,indent=2)+'\n')
                temp=a.output.with_suffix('.tmp');temp.write_text(json.dumps({'status':'RUNNING','predictions':allrows,'adapter_sha256':adapter_hash,'seconds':old_seconds+time.monotonic()-began}));temp.replace(a.output)
                print('EVAL_PROGRESS '+mode+' '+str(off+len(batch))+'/'+str(len(rows)),flush=True)
    data={'status':'COMPLETE','predictions':allrows,'adapter_sha256':adapter_hash,'seconds':old_seconds+time.monotonic()-began,'GPU':torch.cuda.get_device_name(0),'inputs_sha256':proto['input_sha256'],'no_evaluation_gold_loaded':True,'reload_audit':reload_audit,'prefix_replay_audit':replay_audit};a.output.write_text(json.dumps(data)+'\n');print('EVAL_COMPLETE',flush=True)
if __name__=='__main__':main()
