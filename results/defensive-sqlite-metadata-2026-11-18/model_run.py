import gc,hashlib,json,math,random,time
from pathlib import Path
import torch
from peft import LoraConfig, PeftModel, get_peft_model, get_peft_model_state_dict
from transformers import AutoModelForCausalLM, AutoTokenizer
from importlib.metadata import version
from kali_framed_artifacts_20261117 import emit

inp=Path('/input')
cfg=json.loads((inp/'task.json').read_text())
for pkg,ver in json.loads((inp/'model.json').read_text())['expected_packages'].items():assert version(pkg)==ver
tok=AutoTokenizer.from_pretrained('/scratch/model',local_files_only=True)
tok.padding_side='left';tok.pad_token=tok.eos_token
torch.backends.cuda.matmul.allow_tf32=False
def load():
    return AutoModelForCausalLM.from_pretrained('/scratch/model',local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':0}).eval()
def prompt(row,think,aux=False):
    system=cfg['aux_prompt'] if aux else cfg['system']
    return tok.apply_chat_template([dict(role='system',content=system),dict(role='user',content=row['prompt'])],tokenize=False,enable_thinking=think,add_generation_prompt=True)
def predict(model,rows,think,seed,sample):
    answers=[]
    batch_size=4 if cfg['phase']=='long' else 8
    for start in range(0,len(rows),batch_size):
        batch=rows[start:start+batch_size];torch.manual_seed(seed+start)
        encoded=tok([prompt(r,think) for r in batch],padding=True,add_special_tokens=False,return_tensors='pt').to('cuda')
        with torch.inference_mode(): sequences=model.generate(**encoded,max_new_tokens=(6144 if cfg['phase']=='long' else 1024) if think else 320,do_sample=sample,**(dict(temperature=.65,top_p=.9,top_k=20) if sample else {}),pad_token_id=tok.eos_token_id)
        for r,seq in zip(batch,sequences[:,encoded.input_ids.shape[1]:].tolist()):
            stop=tok.eos_token_id in seq
            if stop:seq=seq[:seq.index(tok.eos_token_id)]
            text=tok.decode(seq,skip_special_tokens=False)
            content=text.rsplit('</think>',1)[-1] if not think or '</think>' in text else ''
            answers.append(dict(id=r['id'],seed=seed,thinking=think,stop=stop,content=content))
        print('generated',think,seed,start+len(batch),flush=True)
    return answers
def ce(net,row,target,aux=False):
    prefix=tok.encode(prompt(row,False,aux),add_special_tokens=False)
    suffix=tok.encode(target,add_special_tokens=False)+[tok.eos_token_id]
    ids=torch.tensor([prefix+suffix],device='cuda')
    logits=net(ids,use_cache=False).logits[0,len(prefix)-1:-1]
    return torch.nn.functional.cross_entropy(logits.float(),ids[0,len(prefix):]),len(suffix)
def state_hash(model):
    state=get_peft_model_state_dict(model)
    h=hashlib.sha256()
    for k,v in sorted(state.items()):h.update(k.encode());h.update(v.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()
result={'gpu':torch.cuda.get_device_name(0)}
if cfg['phase'] in ['screen','long']:
    model=load()
    result['responses']=[]
    for think in ((True,) if cfg['phase']=='long' else (False,True)):
        for seed in ((7407,8407,9407) if cfg['phase']=='long' else (3407,4407,5407)):result['responses']+=predict(model,cfg['rows'],think,seed,True)
else:
    rows=cfg['rows'];replay=cfg['replay'];hold=cfg['eval_inputs']
    def evaluate(model):return predict(model,hold,False,3407,False)
    for arm in ['answer','reason']:
        base=load()
        torch.manual_seed(3407)
        net=get_peft_model(base,LoraConfig(r=16,lora_alpha=32,target_modules=['q_proj','v_proj'],lora_dropout=0,bias='none',task_type='CAUSAL_LM'))
        params=[p for p in net.parameters() if p.requires_grad]
        assert all(p.dtype==torch.float32 for p in params)
        initial=state_hash(net);opt=torch.optim.AdamW(params,lr=1e-5,weight_decay=0)
        net.train(); trace=[]
        for epoch in range(4):
            order=list(range(len(rows)));random.Random(3407+epoch).shuffle(order)
            for index in order:
                row=rows[index];rep=replay[len(trace)%len(replay)]
                opt.zero_grad(set_to_none=True)
                a,an=ce(net,row,row['target']);a.backward()
                b,bn=ce(net,rep,rep['target']);(.25*b).backward()
                if arm=='reason':
                    e,en=ce(net,row,row['evidence_target'],True);(.5*e).backward()
                norm=float(torch.nn.utils.clip_grad_norm_(params,1.))
                assert math.isfinite(norm) and norm>0
                opt.step()
                trace.append(dict(id=row['id'],replay=rep['id'],answer_tokens=an,replay_tokens=bn,answer_weight=1.,replay_weight=.25,norm=norm))
        net.eval();final=state_hash(net);assert initial!=final
        dest=Path('/cache/miw113-defensive-metadata-1118')/cfg['run_name']/arm
        dest.mkdir(parents=True,exist_ok=False);net.save_pretrained(dest)
        del net,base,params,opt,a,b;gc.collect();torch.cuda.empty_cache()
        result[arm]=dict(trace=trace,init=initial,final=final)
    base=load()
    result['base']=evaluate(base)
    del base;gc.collect();torch.cuda.empty_cache()
    for arm in ['answer','reason']:
        dest=Path('/cache/miw113-defensive-metadata-1118')/cfg['run_name']/arm
        net=PeftModel.from_pretrained(load(),dest)
        assert state_hash(net)==result[arm]['final']
        result[arm]['responses']=evaluate(net)
        del net;gc.collect();torch.cuda.empty_cache()
result['model_revision']=json.loads((inp/'model.json').read_text())['model_revision']
emit({'result.json':json.dumps(result)},'DEFENSIVE_METADATA')
