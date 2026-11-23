"""Matched SFT of one local database schema question and batched free generation."""
import gc
import hashlib
import json
from pathlib import Path
import torch
from torch.nn import functional as F
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
from kali_framed_artifacts_20261117 import emit

def read(path):
    return json.loads(Path(path).read_text())

def load_base():
    return AutoModelForCausalLM.from_pretrained('/scratch/model',local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda')

def param_hash(model):
    h=hashlib.sha256()
    for name,value in model.named_parameters():
        if 'lora_' in name:
            h.update(name.encode())
            h.update(value.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()

def evaluate(model,plan,tok,batch,aux):
    out={}
    stops=model.generation_config.eos_token_id
    stops={stops} if isinstance(stops,int) else set(stops)
    for seed in plan['decoding_seeds']:
        torch.manual_seed(seed)
        with torch.inference_mode():
            output=model.generate(**batch,do_sample=True,temperature=.6,top_p=.95,top_k=20,
                min_p=0.,max_new_tokens=plan['cap'],pad_token_id=tok.pad_token_id)
        rows={}
        for row,tail in zip(plan['rows'],output[:,batch.input_ids.shape[1]:].tolist()):
            n=next((i for i,t in enumerate(tail) if t in stops),len(tail))
            text=tok.decode(tail[:n],skip_special_tokens=False)
            before,marker,visible=text.rpartition('</think>')
            closed=bool(marker)
            body=before.strip().removeprefix('<think>').strip()
            rows[row['name']]=dict(tokens=n,ended=n<len(tail),closed=closed,
                auxiliary_exact=closed and before.lstrip().startswith('<think>') and body==aux.strip(),
                visible=visible.strip() if closed else text.strip())
        out[str(seed)]=rows
    return out

def main():
    plan=read('/input/study.json')
    seed=plan['seed']
    tok=AutoTokenizer.from_pretrained('/scratch/model',local_files_only=True,padding_side='left')
    tok.pad_token=tok.eos_token
    prompts=[tok.apply_chat_template([{'role':'system','content':plan['system']},{'role':'user','content':r['prompt']}],
            tokenize=False,add_generation_prompt=True,enable_thinking=True) for r in plan['rows']]
    batch=tok(prompts,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda')
    x=plan['examples']['answer_only']
    assert tok(prompts[0],add_special_tokens=False).input_ids==[v for v,k in zip(x['input_ids'],x['segments']) if k=='prompt']
    checkpoints=Path('/cache')/('miw113-schema-factor-'+plan['study_id'])/str(seed)
    checkpoints.mkdir(exist_ok=True,parents=True)
    out={}
    for arm,data in plan['examples'].items():
        base=load_base()
        torch.manual_seed(seed)
        model=get_peft_model(base,LoraConfig(r=16,lora_alpha=32,lora_dropout=0,
              target_modules=['q_proj','v_proj'],bias='none',task_type='CAUSAL_LM'))
        init=param_hash(model)
        params=[p for p in model.parameters() if p.requires_grad]
        assert all(p.dtype==torch.float32 for p in params)
        opt=torch.optim.AdamW(params,lr=.0001,weight_decay=0.)
        ids=torch.tensor([data['input_ids']],device='cuda')
        masks={k:torch.tensor([s==k for s in data['segments'][1:]],device='cuda')
               for k in ('answer','format','trace') if k in data['segments']}
        scores={}
        for step in range(1,65):
            model.train()
            opt.zero_grad(set_to_none=True)
            logits=model(ids,use_cache=False).logits[0,:-1].float()
            ce=F.cross_entropy(logits,ids[0,1:],reduction='none')
            parts={k:ce[m].mean() for k,m in masks.items()}
            loss=parts['answer']+.1*parts['format']+.5*parts.get('trace',0)
            loss.backward()
            norm=torch.nn.utils.clip_grad_norm_(params,1.)
            assert torch.isfinite(loss) and torch.isfinite(norm)
            opt.step()
            del logits,ce,loss
            if step in plan['steps'] or step==1:
                scores[str(step)]={'loss_before_update':{k:v.item() for k,v in parts.items()}}
                if step in plan['steps']:
                    folder=checkpoints/(arm+'-'+str(step))
                    model.save_pretrained(folder)
                    scores[str(step)]['weights']=hashlib.sha256((folder/'adapter_model.safetensors').read_bytes()).hexdigest()
            del parts
        fitted=param_hash(model)
        del opt,model,base,params
        gc.collect()
        model=PeftModel.from_pretrained(load_base(),checkpoints/(arm+'-64')).eval()
        assert param_hash(model)==fitted
        draws=evaluate(model,plan,tok,batch,plan['auxiliary'][arm])
        out[arm]=dict(init=init,checkpoints=scores,draws=draws)
        print('completed arm',arm,seed,flush=True)
        del model
        gc.collect()
    assert len({v['init'] for v in out.values()})==1
    emit(dict(seed=seed,device=torch.cuda.get_device_name(),study_id=plan['study_id'],arms=out),'SCHEMAFACT')

if __name__=='__main__':main()
