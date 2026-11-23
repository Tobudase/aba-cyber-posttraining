"""True Qwen3-8B BF16 single-sample matched SFT. Durable checkpoints and native fresh generation."""
import gc,hashlib,json,os,random,time
from importlib.metadata import version
from pathlib import Path
import torch
import torch.nn.functional as F
from peft import LoraConfig,PeftModel,get_peft_model
from transformers import AutoModelForCausalLM,AutoTokenizer
from kali_framed_artifacts_20261117 import emit
cfg=json.loads(Path('/input/model.json').read_text()); plan=json.loads(Path('/input/aligned-task.json').read_text())
assert all(version(k)==cfg['expected_packages'][k] for k in ('torch','transformers','peft','accelerate','safetensors'))
device='cuda' if torch.cuda.is_available() else 'cpu'
if device=='cpu':
    assert any(x in Path('/proc/cpuinfo').read_text() for x in ('amx_bf16','avx512_bf16'))
    torch.set_num_threads(int(os.environ.get('ACCESS_THREADS','16')))
tok=AutoTokenizer.from_pretrained('/scratch/model',local_files_only=True,padding_side='left')
tok.pad_token=tok.eos_token
dest=Path('/cache')/('miw113-json-triad-'+plan['run_hash']);dest.mkdir(exist_ok=True)
def save(p,obj):
    tmp=p.with_suffix('.writing');tmp.write_text(json.dumps(obj));tmp.replace(p)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def base():
    return AutoModelForCausalLM.from_pretrained('/scratch/model',local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to(device)
def prefix(row):
    return tok.apply_chat_template([{'role':'system','content':plan['system']},{'role':'user','content':row['prompt']}],tokenize=False,add_generation_prompt=True,enable_thinking=True)
def encode(arm):
    p=prefix(plan['rows'][0]);assert not p.rstrip().endswith('<think>')
    r=plan['traces'].get(arm, '')
    head=p+'<think>\n'
    command=plan['command']
    justification=plan['common_visible_explanation']
    final=json.dumps(dict(command=command,explanation=justification),ensure_ascii=False,separators=(',',':'))
    start=head+(r+'\n' if r else '')+'</think>\n\n'
    txt=start+final+tok.eos_token
    left=len(start)+final.index(command)
    right=left+len(command)
    ex=len(start)+final.index(justification)
    enc=tok(txt,return_offsets_mapping=True,add_special_tokens=False)
    lab=[]
    for lo,hi in enc.offset_mapping:
        if hi<=len(p): tag='masked'
        elif hi>ex and lo<ex+len(justification): tag='visible_masked'
        elif hi>left and lo<right: tag='answer'
        elif r and hi>len(head) and lo<len(head)+len(r): tag='trace'
        else: tag='format'
        lab.append(tag)
    ids=enc.input_ids
    cmd_tokens=tok.decode([v for v,l in zip(ids,lab) if l=='answer'])
    assert command in cmd_tokens and lab[-1]=='format' and ids[-1]==tok.eos_token_id and len(ids)<=4096
    assert 'visible_masked' in lab and 'masked' in lab
    if r:assert r in tok.decode([v for v,l in zip(ids,lab) if l=='trace'])
    return torch.tensor([ids],device=device),lab
xs={arm:encode(arm) for arm in ('A','B','C')}
def labels(arm,k):
    x,l=xs[arm];return [v for v,y in zip(x[0].tolist(),l) if y==k]
assert labels('A','answer')==labels('B','answer')==labels('C','answer') and not labels('A','trace')
def evaluate(model,label):
    dst=dest/(label+'-eval.json')
    if dst.exists():return json.loads(dst.read_text())
    model.eval();rows=plan['rows'];tokens=tok([prefix(r) for r in rows],padding=True,add_special_tokens=False,return_tensors='pt').to(device)
    torch.manual_seed(11341)
    with torch.inference_mode():
        seq=model.generate(**tokens,max_new_tokens=plan['cap'],do_sample=True,temperature=.6,top_p=.95,top_k=20,min_p=0.,pad_token_id=tok.eos_token_id)
    stops=model.generation_config.eos_token_id
    if isinstance(stops,int):stops=[stops]
    out={}
    for row,y in zip(rows,seq[:,tokens.input_ids.shape[1]:].tolist()):
        n=next((i for i,v in enumerate(y) if v in stops),len(y));text=tok.decode(y[:n],skip_special_tokens=False)
        pre,sep,final=text.rpartition('</think>')
        out[row['name']]=dict(ended=n<len(y),tokens=n,trace=pre if sep else '',command_output=final.strip() if sep else text.strip(),closed=bool(sep))
    save(dst,out);print('evaluated',label,flush=True);return out
def weights(m):
    h=hashlib.sha256()
    for n,w in m.named_parameters():
        if 'lora_' in n:h.update(n.encode());h.update(w.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()
base_model=base();baseline=evaluate(base_model,'base');del base_model;gc.collect()
all_out={};inits={}
for arm in ('A',):
    torch.manual_seed(plan['seed']);m=base();torch.manual_seed(plan['seed'])
    m=get_peft_model(m,LoraConfig(r=16,lora_alpha=32,lora_dropout=0,target_modules=['q_proj','v_proj'],bias='none',task_type='CAUSAL_LM'))
    m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});inits[arm]=weights(m);params=[w for w in m.parameters() if w.requires_grad]
    assert all(w.dtype==torch.float32 for w in params)
    opt=torch.optim.AdamW(params,lr=1e-4,weight_decay=0);x,lab=xs[arm];hist=[];hashes={}
    mask={k:torch.tensor([z==k for z in lab[1:]],device=device) for k in ('answer','trace','format') if k in lab}
    for step in range(1,65):
        m.train();opt.zero_grad(set_to_none=True)
        logits=m(x,use_cache=False).logits[0,:-1].float();ce=F.cross_entropy(logits,x[0,1:],reduction='none');ls={k:ce[mk].mean() for k,mk in mask.items()}
        total=ls['answer']+.1*ls['format']+.5*ls.get('trace',0)
        total.backward();norm=torch.nn.utils.clip_grad_norm_(params,1.);assert torch.isfinite(norm) and torch.isfinite(total)
        opt.step();hist.append(dict(step=step,loss={k:v.item() for k,v in ls.items()},grad=norm.item()))
        del logits,ce,ls,total
        if step in plan['step_points']:
            folder=dest/f'{arm}-{step}';m.save_pretrained(folder)
            hashes[str(step)]=dict(weights=digest(folder/'adapter_model.safetensors'),state=weights(m))
            save(dest/(arm+'-loss.json'),hist);print('saved',arm,step,flush=True)
    del opt,m,params;gc.collect()
    ev={}
    for step in (16,32,64):
        m=PeftModel.from_pretrained(base(),dest/f'{arm}-{step}');assert weights(m)==hashes[str(step)]['state']
        ev[str(step)]=evaluate(m,f'{arm}-{step}');del m;gc.collect()
    all_out[arm]=dict(init=inits[arm],loss=hist,checks=hashes,eval=ev,token_counts={k:lab.count(k) for k in set(lab)})
assert len(inits)==1
emit(dict(base=baseline,arms=all_out,device=device,hardware=torch.cuda.get_device_name() if device=='cuda' else 'cpu',dir=dest.name),'FIT')
