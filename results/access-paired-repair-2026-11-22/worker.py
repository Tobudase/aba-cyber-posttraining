"""Matched-budget intervention evaluated with free generation on offline schema prompts."""
import gc
import hashlib
import json
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoTokenizer, AutoModelForCausalLM
from kali_framed_artifacts_20261117 import emit

cfg = json.loads(Path('/input/experiment.json').read_text())
protocol = cfg['protocol']
auxiliary = cfg.get('auxiliary')
tok = AutoTokenizer.from_pretrained('/scratch/model', local_files_only=True, padding_side='left')
tok.pad_token = tok.eos_token
def base():
    return AutoModelForCausalLM.from_pretrained('/scratch/model',torch_dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True).to('cuda')
def prefix(row):
    messages=[{'role':'system','content':row.get('system', protocol['system'])},{'role':'user','content':row['prompt']}]
    return tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=True)
def params_hash(model):
    h=hashlib.sha256()
    for n,w in model.named_parameters():
        if 'lora_' in n:
            h.update(n.encode())
            h.update(w.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()
def train_example(row):
    p=prefix(row)
    header=p+'<think>\n\n</think>\n\n'
    payload=row['answer'] if row.get('kind')=='explanation' else '<output>'+row['answer']+'</output>'
    answer=payload+tok.eos_token
    enc=tok(header+answer,return_offsets_mapping=True,add_special_tokens=False)
    labels=['masked' if end<=len(p) else 'answer' if start>=len(header) else 'format' for start,end in enc.offset_mapping]
    assert tok.decode([i for i,k in zip(enc.input_ids,labels) if k=='answer'])==answer
    return torch.tensor([enc.input_ids],device='cuda'),{k:torch.tensor([s==k for s in labels[1:]],device='cuda') for k in ('answer','format')}
def evaluate(m,label):
    m.eval()
    x=tok([prefix(r) for r in protocol['probes']],padding=True,return_tensors='pt',add_special_tokens=False).to('cuda')
    stops=m.generation_config.eos_token_id
    stops=[stops] if isinstance(stops,int) else stops
    out={}
    for seed in protocol['seeds']:
        torch.manual_seed(seed)
        with torch.inference_mode():
            seq=m.generate(**x,max_new_tokens=protocol['cap'],do_sample=True,temperature=.6,top_p=.95,top_k=20,min_p=0.,pad_token_id=tok.eos_token_id)
        rows=[]
        for ids in seq[:,x.input_ids.shape[1]:].tolist():
            n=next((i for i,v in enumerate(ids) if v in stops),len(ids))
            rows.append(dict(ended=n<len(ids),tokens=n,text=tok.decode(ids[:n],skip_special_tokens=False)))
        out[str(seed)]=rows
        print('finished',label,seed,flush=True)
    return out
result={}
if not auxiliary:
    m=base()
    result['base']=evaluate(m,'base')
    del m
    gc.collect()
    m=PeftModel.from_pretrained(base(), cfg['old_adapter'])
    assert params_hash(m)==cfg['old_hash']
    result['historical-A16']=evaluate(m,'historical-A16')
    del m
    gc.collect()

torch.manual_seed(protocol['train_seed'])
m=base()
torch.manual_seed(protocol['train_seed'])
m=get_peft_model(m,LoraConfig(r=16,lora_alpha=32,lora_dropout=0,target_modules=['q_proj','v_proj'],bias='none',task_type='CAUSAL_LM'))
assert params_hash(m)==cfg['initial_hash']
params=[w for w in m.parameters() if w.requires_grad]
opt=torch.optim.AdamW(params,lr=1e-4,weight_decay=0)
examples=[train_example(r) for r in protocol['train']]
extra_examples=[]
if auxiliary:
    for row,sentence in zip(protocol['train'],auxiliary['sentences']):
        extra_examples.append(train_example(dict(prompt=row['prompt'],system=auxiliary['instruction'],answer=sentence,kind='explanation')))
    assert len(extra_examples)==len(examples)
def supervised_loss(m,example):
    x,masks=example
    logits=m(x,use_cache=False).logits[0,:-1].float()
    ce=torch.nn.functional.cross_entropy(logits,x[0,1:],reduction='none')
    return ce[masks['answer']].mean()+.1*ce[masks['format']].mean()
history=[]
for step in range(protocol['step']):
    index=step%len(examples)
    m.train()
    opt.zero_grad(set_to_none=True)
    loss=supervised_loss(m,examples[index])
    if auxiliary:
        loss=loss+auxiliary['weight']*supervised_loss(m,extra_examples[index])
    loss.backward()
    norm=torch.nn.utils.clip_grad_norm_(params,1.)
    assert torch.isfinite(norm) and torch.isfinite(loss)
    history.append(loss.item())
    opt.step()
    del loss
dest=Path('/cache')/cfg['new_folder']
m.save_pretrained(dest)
state=params_hash(m)
del m,opt,params
gc.collect()
m=PeftModel.from_pretrained(base(),dest)
assert params_hash(m)==state
label='paired-explain16' if auxiliary else 'paired-A16'
result[label]=evaluate(m,label)
emit(dict(outputs=result,adapter_state=state,losses=history,device=torch.cuda.get_device_name(),init_hash=cfg['initial_hash']),'REPAIR')
