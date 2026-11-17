"""One fixed SFT arm from original Qwen3-8B; no automatic GPU submission.

Run each arm in a fresh process. Requires the pinned runtime and local, verified
checkpoint files. Targets are native-template visible rationales, not raw CoT.
"""
import argparse,hashlib,json,math,random,time
from pathlib import Path

def validate(data,arm):
    rows=data['encoded'][arm];p=data['protocol']
    assert len(rows)==p['rows'] and len({r['id'] for r in rows})==len(rows)
    for r in rows:
        n=r['prompt_tokens'];assert len(r['input_ids'])==len(r['labels'])<=p['max_sequence_length']
        assert all(v==-100 for v in r['labels'][:n]) and r['labels'][n:]==r['input_ids'][n:]
        assert r['input_ids'][-1]==151645 and r['target_tokens']==len(r['input_ids'])-n
        assert len(r['command_mask'])==len(r['input_ids']) and not any(r['command_mask'][:n]) and any(r['command_mask'][n:])
    for order in data['epoch_orders']:assert sorted(order)==list(range(len(rows)))
    assert len(data['epoch_orders'])*math.ceil(len(rows)/p['effective_batch'])==p['optimizer_updates_per_arm']
    return rows,p

def causal_ce_sum(logits,labels):
    import torch.nn.functional as F
    target=labels[:,1:];count=int((target!=-100).sum())
    assert count>0
    loss=F.cross_entropy(logits[:,:-1,:].float().reshape(-1,logits.shape[-1]),target.reshape(-1),ignore_index=-100,reduction='sum')
    return loss,count

def main():
    a=argparse.ArgumentParser();a.add_argument('--data',type=Path,required=True);a.add_argument('--arm',choices=['answer_only','reasoning'],required=True);a.add_argument('--model-path',type=Path);a.add_argument('--output',type=Path);a.add_argument('--expected-sha256');a.add_argument('--preflight-only',action='store_true');args=a.parse_args()
    data=json.loads(args.data.read_text());rows,p=validate(data,args.arm)
    if args.preflight_only:
        print(json.dumps({'status':'PREFLIGHT_PASS','arm':args.arm,'rows':len(rows),'updates_planned':p['optimizer_updates_per_arm'],'training_performed':False}));return
    assert args.model_path and args.output and not args.output.exists()
    assert args.expected_sha256 and hashlib.sha256(args.data.read_bytes()).hexdigest()==args.expected_sha256,'Use the frozen payload digest'
    import torch
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,get_peft_model_state_dict
    from importlib.metadata import version
    for name,v in data['model_protocol']['expected_packages'].items():assert version(name)==v,(name,version(name),v)
    for name,expected in data['model_protocol']['checkpoint_files'].items():
        h=hashlib.sha256()
        with (args.model_path/name).open('rb') as f:
            for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
        assert h.hexdigest()==expected,name
    assert torch.cuda.is_available();torch.manual_seed(p['seed']);random.seed(p['seed'])
    model=AutoModelForCausalLM.from_pretrained(args.model_path,local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
    model.requires_grad_(False);model.eval()
    probe=torch.tensor([rows[0]['input_ids'][:rows[0]['prompt_tokens']]],device='cuda')
    with torch.no_grad():base=model(input_ids=probe).logits[:,-1].float().cpu()
    torch.manual_seed(p['seed'])
    model=get_peft_model(model,LoraConfig(r=p['lora_r'],lora_alpha=p['lora_alpha'],target_modules=p['lora_targets'],lora_dropout=0,bias='none',task_type='CAUSAL_LM',init_lora_weights=True))
    for parameter in model.parameters():
        if parameter.requires_grad:parameter.data=parameter.data.float()
    with torch.no_grad():assert torch.equal(model(input_ids=probe).logits[:,-1].float().cpu(),base)
    initial={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}
    assert all(not bool(v.any()) for k,v in initial.items() if 'lora_B' in k)
    initialization_sha256=hashlib.sha256(b''.join(initial[k].numpy().tobytes() for k in sorted(initial))).hexdigest()
    parameters=[x for x in model.parameters() if x.requires_grad]
    opt=torch.optim.AdamW(parameters,lr=p['learning_rate'],betas=(.9,.999),eps=1e-8,weight_decay=0)
    model.enable_input_require_grads();model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.config.use_cache=False
    args.output.mkdir(parents=True);traces=[];start=time.monotonic()
    for epoch,order in enumerate(data['epoch_orders']):
        torch.manual_seed(p['seed']+epoch)
        for offset in range(0,len(rows),p['effective_batch']):
            batch=[rows[i] for i in order[offset:offset+p['effective_batch']]];denom=sum(r['target_tokens'] for r in batch)
            model.train();opt.zero_grad(set_to_none=True);total=0.;command_total=0.;command_tokens=0
            for r in batch:
                ids=torch.tensor([r['input_ids']],device='cuda');labels=torch.tensor([r['labels']],device='cuda')
                logits=model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False).logits
                loss,n=causal_ce_sum(logits,labels)
                with torch.no_grad():
                    cmdlabels=labels.clone();cmdlabels[~torch.tensor([r['command_mask']],device='cuda')]=-100
                    cmdloss,cn=causal_ce_sum(logits.detach(),cmdlabels);command_total+=float(cmdloss);command_tokens+=cn
                assert n==r['target_tokens'] and math.isfinite(float(loss.detach()))
                (loss/denom).backward();total+=float(loss.detach());del loss,ids,labels,logits,cmdloss,cmdlabels
            norm=float(torch.nn.utils.clip_grad_norm_(parameters,1.));assert math.isfinite(norm) and norm>0
            opt.step();traces.append({'step':len(traces)+1,'epoch':epoch+1,'ids':[r['id'] for r in batch],'target_tokens':denom,'loss':total/denom,'command_loss_monitor':command_total/command_tokens,'command_tokens':command_tokens,'gradient_norm':norm})
            tmp=args.output/'trace.tmp';tmp.write_text(json.dumps(traces));tmp.replace(args.output/'trace.json')
    assert len(traces)==p['optimizer_updates_per_arm']
    model.save_pretrained(args.output/'adapter')
    assert any(not torch.equal(initial[k],v.detach().cpu()) for k,v in get_peft_model_state_dict(model).items())
    receipt={'status':'TRAINED_PENDING_RELOAD_AND_EVALUATION','arm':args.arm,'updates':len(traces),'seconds':time.monotonic()-start,'data_sha256':hashlib.sha256(args.data.read_bytes()).hexdigest(),'initial_adapter_sha256':initialization_sha256,'model_revision':data['model_protocol']['model_revision'],'adapter_sha256':hashlib.sha256((args.output/'adapter/adapter_model.safetensors').read_bytes()).hexdigest(),'training_target_tokens':sum(r['target_tokens'] for r in traces),'evaluation_performed':False}
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
