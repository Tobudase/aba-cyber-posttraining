"""Frozen original/adapter evaluation runner. No teacher or gold reaches model."""
import argparse,hashlib,json,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--model-path',type=Path);p.add_argument('--adapter',type=Path);p.add_argument('--output',type=Path);p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
    protocol=json.loads((a.stage/'evaluation-protocol.json').read_text());inputs=a.stage/'evaluation-inputs-private.json';rows=json.loads(inputs.read_text())
    assert hashlib.sha256(inputs.read_bytes()).hexdigest()==protocol['input_sha256']
    assert len(rows)==len({r['id'] for r in rows})==88 and all(set(r)=={'id','panel','messages'} for r in rows)
    assert all([m['role'] for m in r['messages']]==['system','user'] for r in rows)
    if a.preflight_only:print(json.dumps({'status':'PREFLIGHT_PASS','rows':88,'model_calls':0,'gold_in_payload':False}));return
    assert a.model_path and a.output and not a.output.exists()
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    data=json.loads((a.stage/'paired-training-private.json').read_text());mp=data['model_protocol']
    for name,expected in mp['checkpoint_files'].items():
        h=hashlib.sha256()
        with (a.model_path/name).open('rb') as f:
            for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
        assert h.hexdigest()==expected
    tok=AutoTokenizer.from_pretrained(a.model_path,local_files_only=True,trust_remote_code=False);tok.padding_side='left';tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(a.model_path,local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
    if a.adapter:
        receipt=json.loads((a.adapter.parent/'receipt.json').read_text())
        assert receipt['model_revision']==mp['model_revision'] and receipt['data_sha256']==hashlib.sha256((a.stage/'paired-training-private.json').read_bytes()).hexdigest()
        assert receipt['adapter_sha256']==hashlib.sha256((a.adapter/'adapter_model.safetensors').read_bytes()).hexdigest()
        model=PeftModel.from_pretrained(model,a.adapter,is_trainable=False)
    model.eval();model.requires_grad_(False);out=[];start=time.monotonic()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    for offset in range(0,len(rows),protocol['batch_size']):
        batch=rows[offset:offset+protocol['batch_size']]
        texts=[tok.apply_chat_template(r['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=True) for r in batch]
        x=tok(texts,add_special_tokens=False,padding=True,return_tensors='pt').to('cuda');n=x.input_ids.shape[1]
        with torch.inference_mode():y=model.generate(**x,max_new_tokens=protocol['max_new_tokens'],do_sample=False,temperature=None,top_p=None,top_k=None,use_cache=True,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id)
        for r,b in zip(batch,y[:,n:].cpu().tolist()):
            stopped=tok.eos_token_id in b;b=b[:b.index(tok.eos_token_id)] if stopped else b
            raw=tok.decode(b,skip_special_tokens=False,clean_up_tokenization_spaces=False)
            # Never score an answer embedded in an unfinished thought block.
            if '</think>' in raw:content=raw.split('</think>',1)[1]
            else:content='' if '<think>' in raw else raw
            out.append({'id':r['id'],'panel':r['panel'],'content':content,'response':raw,'finish_reason':'stop' if stopped else 'length','generated_tokens':len(b)})
        tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps({'status':'COMPLETE' if len(out)==88 else 'RUNNING','model_revision':mp['model_revision'],'adapter_sha256':receipt['adapter_sha256'] if a.adapter else None,'predictions':out,'seconds':time.monotonic()-start}));tmp.replace(a.output)
    print(json.dumps({'status':'COMPLETE','rows':len(out),'seconds':time.monotonic()-start}))
if __name__=='__main__':main()
