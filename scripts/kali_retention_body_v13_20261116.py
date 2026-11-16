"""Verified TRAIN replay repair with fixed generic old command KL.

Matched auxiliary replay content ablation. No development gradients or benchmark commands.
"""
import base64,collections,gzip,hashlib,json,math,random,shlex,time
from pathlib import Path

def adapter_key(name):return {'R':'replay','RK':'regularized'}.get(name,name)

def run_repair(model,tok,torch,cfg,raw,started,sha):
 from transformers import LogitsProcessorList
 from peft import PeftModel,get_peft_model_state_dict
 from safetensors.torch import load_file
 from kali_command_ngram_guard_20261115 import CommandNGramGuard
 from kali_exact_adapter_loading_20261115 import load_exact_adapter
 from kali_stable_objective_20261114 import objective_sums
 from kali_rollout_distillation_20261115 import command_rollout_mask,aligned_reverse_kl_sum
 p=cfg['model_protocol'];data=json.loads(gzip.decompress(raw));new=data['train_new'];old=data['train_old'];panels=data['panels'];records=sum(panels.values(),[])
 trusted=data['train_trusted'];assert len(new)==384 and len(old)==160 and len(trusted)==64 and len(records)==192
 assert all(r['split']=='train' and r['training_eligible'] and not r['official_test'] for r in new+old+trusted)
 assert not {r['id'] for r in old}&{r['id'] for r in records}
 outdir=Path(cfg['durable_output']);outdir.mkdir(parents=True,exist_ok=False)
 def save(name,value):
  f=outdir/name;tmp=f.with_suffix(f.suffix+'.tmp');tmp.write_text(json.dumps(value)+'\n');tmp.replace(f)
 def emit(marker,value):print(marker+'='+base64.b64encode(gzip.compress(json.dumps(value).encode())).decode(),flush=True)
 def generate_ids(prompts,seed,sample=False,max_tokens=1024,guarded=True):
  inputs=tok.pad({'input_ids':prompts},padding=True,return_tensors='pt').to('cuda');torch.manual_seed(seed)
  extra={'do_sample':sample,'temperature':1. if sample else None,'top_p':1. if sample else None,'top_k':0 if sample else None}
  processors=[CommandNGramGuard(tok,inputs['input_ids'].shape[1],8)] if guarded else []
  with torch.inference_mode():out=model.generate(**inputs,max_new_tokens=max_tokens,use_cache=True,pad_token_id=151645,eos_token_id=151645,logits_processor=LogitsProcessorList(processors),**extra)
  return out[:,inputs['input_ids'].shape[1]:].cpu().tolist()
 def infer(rows,label,batch_size=4,use_cache=True):
  model.eval();result=[]
  for offset in range(0,len(rows),batch_size):
   batch=rows[offset:offset+batch_size];texts=[tok.apply_chat_template(r['native_messages'],tokenize=False,add_generation_prompt=True) for r in batch]
   if use_cache:outputs=generate_ids([tok.encode(t,add_special_tokens=False) for t in texts],p['inference_seed'])
   else:
    inputs=tok(texts,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda');torch.manual_seed(p['inference_seed']);guard=CommandNGramGuard(tok,inputs['input_ids'].shape[1],8)
    with torch.inference_mode():out=model.generate(**inputs,max_new_tokens=1024,do_sample=False,use_cache=False,pad_token_id=151645,eos_token_id=151645,temperature=None,top_p=None,top_k=None,logits_processor=LogitsProcessorList([guard]))
    outputs=out[:,inputs['input_ids'].shape[1]:].cpu().tolist()
   for row,ids in zip(batch,outputs):
    ended=151645 in ids;effective=ids[:ids.index(151645)] if ended else ids
    result.append({'id':row['id'],'response':tok.decode(effective,skip_special_tokens=False,clean_up_tokenization_spaces=False),'truncated':not ended,'generated_tokens':len(effective),'early_EOS_first_two':151645 in ids[:2]})
   save(label+'.json',result);print('FUNCTIONAL_INFER '+label+' '+str(len(result))+'/'+str(len(rows)),flush=True)
  return result
 def logits_on(ids):
  ids=torch.tensor([ids],device='cuda');return model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False).logits
 source=Path(cfg['source_adapter']);assert sha(source/'adapter_model.safetensors')==cfg['source_weights_sha256'] and sha(source/'adapter_config.json')==cfg['source_config_sha256']
 initial=load_file(str(source/'adapter_model.safetensors'));probe=old[0]['input_ids']
 with torch.no_grad():
  probe_tensor=torch.tensor([probe],device='cuda')
  original=model(input_ids=probe_tensor,attention_mask=torch.ones_like(probe_tensor),use_cache=False).logits[:,-1].detach().cpu()
  original_unmasked=model(input_ids=probe_tensor,use_cache=False).logits[:,-1].detach().cpu()
 mask_path_difference=float((original.float()-original_unmasked.float()).abs().max())
 model=PeftModel.from_pretrained(model,source,adapter_name='start',is_trainable=True)
 initialization={n:load_exact_adapter(model,source,adapter_key(n),True) for n in ['start','R','RK']};model.set_adapter('start')
 with torch.no_grad(),model.disable_adapter():difference=float((logits_on(probe)[:,-1].cpu().float()-original.float()).abs().max())
 with torch.no_grad(),model.disable_adapter():
  unmasked_after=model(input_ids=probe_tensor,use_cache=False).logits[:,-1].detach().cpu()
 unmasked_difference=float((unmasked_after.float()-original_unmasked.float()).abs().max())
 save('base-invariance-preflight.json',{'matched_mask_difference':difference,'matched_unmasked_difference':unmasked_difference,'pre_PEFT_mask_vs_no_mask_difference':mask_path_difference,'GPU':torch.cuda.get_device_name(0),'optimizer_steps':0})
 print('BASE_INVARIANCE '+json.dumps({'matched_mask_difference':difference,'matched_unmasked_difference':unmasked_difference,'mask_path_difference':mask_path_difference}),flush=True)
 assert difference==0 and unmasked_difference==0;del original,original_unmasked,unmasked_after,probe_tensor
 save('initialization-audit.json',initialization)
 assert all(not isinstance(m,torch.nn.Dropout) or m.p==0 for m in model.modules()) and getattr(model.config,'attention_dropout',0)==0
 model.enable_input_require_grads();model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.config.use_cache=False
 def activate(name,training):
  actual=adapter_key(name);model.set_adapter(actual);model.requires_grad_(False)
  if training:
   for n,v in model.named_parameters():
    if '.lora_' in n and '.'+actual+'.' in n:v.requires_grad_(True)
  model.train(training);return [v for v in model.parameters() if v.requires_grad]

 def wait_gate(file):
  until=time.monotonic()+1200
  while not Path(file).exists():assert time.monotonic()<until,'Host gate timeout';time.sleep(2)
  value=json.loads(Path(file).read_text());assert value['config_sha256']==sha('/input/config.json');return value
 # Fresh candidate optimizer starts at v11 CE; old KL remains anchored to R120.
 anchor=Path(cfg['anchor_adapter']);assert sha(anchor/'adapter_model.safetensors')==cfg['anchor_weights_sha256'] and sha(anchor/'adapter_config.json')==cfg['anchor_config_sha256']
 load_exact_adapter(model,anchor,'anchor',False)
 anchor_initial=get_peft_model_state_dict(model,adapter_name='anchor');anchor_initial={k:v.detach().cpu().clone() for k,v in anchor_initial.items()}
 qdecision={'action':'train','source':'Direct supervised labels; original teacher checks and new parser/encoding admission recorded before launch'}
 outputs={}
 with model.disable_adapter():outputs['E0']=infer(records,'E0')
 f22=Path(cfg['F22_adapter']);assert sha(f22/'adapter_model.safetensors')==cfg['F22_weights_sha256'] and sha(f22/'adapter_config.json')==cfg['F22_config_sha256']
 load_exact_adapter(model,f22,'baseline',False);activate('baseline',False);outputs['F22']=infer(records,'F22');activate('start',False);outputs['W0']=infer(records,'W0')


 shifted={'W0':infer(data['shifted_dev_messages'],'shifted_W0')};auxiliary_predictions={'W0':infer(data['auxiliary_eval_messages'],'auxiliary_W0')}
 def stream(rows,count,seed):
  out=[];rng=random.Random(seed)
  while len(out)<count:
   part=rows.copy();rng.shuffle(part);out.extend(part)
  return out[:count]
 traces={};checkpoints={};order_hashes={};rollout_audits={};trusted_predictions={};fullfit={};aux_order_hashes={}
 for name in ['R','RK']:
  load_exact_adapter(model,source,adapter_key(name),True);params=activate(name,True);assert len(params)==144 and all(v.dtype==torch.float32 for v in params)
  state=get_peft_model_state_dict(model,adapter_name=adapter_key(name));assert state.keys()==initial.keys() and all(torch.equal(v.cpu(),initial[k]) for k,v in state.items())
  optimizer=torch.optim.AdamW(params,lr=5e-6,betas=(.9,.999),eps=1e-8,weight_decay=0);steps=0;traces[name]=[];order_hashes[name]=[];rollout_audits[name]=[]
  generic_stream=stream(old,192,420);trusted_stream=stream(trusted,384,421);aux_stream=stream(data['auxiliary_replay'][name],384,432);aux_order_hashes[name]=hashlib.sha256(json.dumps([r['id'] for r in aux_stream]).encode()).hexdigest()
  def reference(ids):
   activate('anchor',False)
   with torch.no_grad():ref=logits_on(ids).detach()
   activate(name,True);return ref
  for epoch in range(1):
   aa=new.copy();random.Random(42+epoch).shuffle(aa);visited=aa
   epoch_ids=[];activate(name,True)
   for offset in range(0,384,4):
    tick=time.monotonic();nr=aa[offset:offset+4];vr=visited[offset:offset+4];tr=trusted_stream[steps*4:steps*4+4];orr=generic_stream[steps*2:steps*2+2];assert len(nr)==len(vr)==len(tr)==4 and len(orr)==2
    epoch_ids.extend(r['id'] for r in nr+tr+orr);optimizer.zero_grad(set_to_none=True);nk=gold=tc=ok=aux_loss=0.;kt=sum(sum(v!=-100 for v in r['kl_labels'][1:]) for r in orr)
    for original,row in zip(nr,vr):
     logits=logits_on(row['input_ids']);labels=torch.tensor([original['kl_labels']],device='cuda');kl,_,count=objective_sums(logits,labels);del labels
     loss=kl/count/4;assert math.isfinite(float(loss.detach()));loss.backward();nk+=float((kl/count).detach());del logits,kl,loss
     logits=logits_on(original['input_ids']);lab=torch.tensor([original['labels']],device='cuda');ce,_,count=objective_sums(logits,lab);loss=.1*ce/count/4;loss.backward();gold+=float((ce/count).detach());del logits,lab,ce,loss
    for row in tr:
     logits=logits_on(row['input_ids']);lab=torch.tensor([row['labels']],device='cuda');cmd=torch.tensor([row['kl_labels']],device='cuda');ce,_,n=objective_sums(logits,lab);cc,_,nc=objective_sums(logits,cmd);loss=(cc/nc+.1*ce/n)/4;loss.backward();tc+=float((cc/nc).detach());del logits,lab,cmd,ce,cc,loss
    for row in aux_stream[steps*4:steps*4+4]:
     logits=logits_on(row['input_ids']);lab=torch.tensor([row['labels']],device='cuda');cmd=torch.tensor([row['kl_labels']],device='cuda');ce,_,n=objective_sums(logits,lab);cc,_,nc=objective_sums(logits,cmd);loss=.5*(cc/nc+.1*ce/n)/4;loss.backward();aux_loss+=float((cc/nc+.1*ce/n).detach());del logits,lab,cmd,ce,cc,loss
    for row in orr:
     ref=reference(row['input_ids']);logits=logits_on(row['input_ids']);mask=[v!=-100 for v in row['kl_labels'][row['prompt_tokens']:]];kl,count=aligned_reverse_kl_sum(logits,ref,row['prompt_tokens'],row['prompt_tokens'],mask);loss=.3*kl/kt;loss.backward();ok+=float(kl.detach());del logits,ref,kl,loss
    assert all(p.grad is None for n,p in model.named_parameters() if ('.start.' in n or '.anchor.' in n) and '.lora_' in n)
    gn=float(torch.nn.utils.clip_grad_norm_(params,1.));assert math.isfinite(gn) and gn>0;optimizer.step();steps+=1
    trace={'step':steps,'epoch':epoch+1,'new_primary_objective_example_mean':nk/4,'objective':'command_CE','auxiliary_replay_loss_example_mean':aux_loss/4,'auxiliary_weight':.5,'new_gold_completion_CE_example_mean':gold/4,'trusted_command_CE_example_mean':tc/4,'old_source_KL_token_mean':ok/kt,'beta_old_source':.3,'grad_norm_before_clip':gn,'window_wall_seconds':time.monotonic()-tick};traces[name].append(trace);save('progress-'+name+'.json',{'arm':name,'steps':steps,'trace':traces[name]})
    if steps%4==0:print('FUNCTIONAL_TRAIN '+name+' '+json.dumps(trace),flush=True)
   assert len(epoch_ids)==960;order_hashes[name].append(hashlib.sha256(json.dumps(epoch_ids).encode()).hexdigest())
  assert steps==96
  frozen=get_peft_model_state_dict(model,adapter_name='start');assert frozen.keys()==initial.keys() and all(torch.equal(v.cpu(),initial[k]) for k,v in frozen.items())
  label=name+'_step96';path=outdir/label/'adapter';model.save_pretrained(path,selected_adapters=[adapter_key(name)]);actual=path/adapter_key(name)
  ac=json.loads((actual/'adapter_config.json').read_text());ac.update(base_model_name_or_path=p['model_id'],revision=p['model_revision']);(actual/'adapter_config.json').write_text(json.dumps(ac,indent=2)+'\n')
  state=get_peft_model_state_dict(model,adapter_name=adapter_key(name));changed=sum(not torch.equal(v.cpu(),initial[k]) for k,v in state.items());assert changed>0
  checkpoints[label]={'adapter_relative_path':str(actual.relative_to(outdir)),'weights_sha256':sha(actual/'adapter_model.safetensors'),'config_sha256':sha(actual/'adapter_config.json'),'optimizer_steps':96,'changed_tensors':changed,'teacher_source_unchanged':True}
  anchor_after=get_peft_model_state_dict(model,adapter_name='anchor');assert anchor_after.keys()==anchor_initial.keys() and all(torch.equal(v.cpu(),anchor_initial[k]) for k,v in anchor_after.items())
  auxiliary_predictions[label]=infer(data['auxiliary_eval_messages'],'auxiliary_'+label)
  fullfit[label]=infer(data['train_new_messages'],label+'_fullTRAIN384');outputs[label]=infer(records,label);trusted_predictions[label]=infer(data['trusted_messages'],label+'_trusted_train64');shifted[label]=infer(data['shifted_dev_messages'],'shifted_'+label)
 assert order_hashes['R']==order_hashes['RK']
 receipt={'auxiliary_predictions':auxiliary_predictions,'auxiliary_order_hashes':aux_order_hashes,'auxiliary_training_ids':{a:[r['id'] for r in rows] for a,rows in data['auxiliary_replay'].items()},'anchor_weights_sha256':cfg['anchor_weights_sha256'],'anchor_unchanged':True,'status':'FUNCTIONAL_PRIMARY_TRAINING_COMPLETE','full_train_predictions':fullfit,'panels':{k:[r['id'] for r in v] for k,v in panels.items()},'extra_panels':{'teacher_train32':data['teacher_quality_ids'],'shifted_dev64':[r['id'] for r in data['shifted_dev_messages']]},'legacy_fit_ids':data['legacy_fit_ids'],'training_new_ids':[r['id'] for r in new],'training_old_ids':[r['id'] for r in old],'training_trusted_ids':[r['id'] for r in trusted],'trusted_train_predictions':trusted_predictions,'shifted_dev_outputs':shifted,'initialization':initialization,'checkpoints':checkpoints,'optimizer_steps':{'R':96,'RK':96},'order_hashes':order_hashes,'traces':traces,'rollout_audits':rollout_audits,'teacher_quality_decision':qdecision,'source_adapter_sha256':cfg['source_weights_sha256'],'worker_sha256':sha('/input/worker.py'),'config_sha256':sha('/input/config.json'),'GPU':torch.cuda.get_device_name(0),'wall_seconds':time.monotonic()-started,'official_TEST_queries':0,'protected_v1_confirm384_queries':0,'protected_original_final64_queries':0}
 save('receipt.json',receipt);emit('FUNCTIONAL_ARTIFACT',{'receipt':receipt,'outputs':outputs});print('READY_FOR_FUNCTIONAL_DECISION',flush=True)
 def wait_gate(file):
  deadline=time.monotonic()+1200
  while not Path(file).exists():assert time.monotonic()<deadline,'Functional host gate timed out';time.sleep(2)
  value=json.loads(Path(file).read_text());assert value['config_sha256']==sha('/input/config.json');return value
 decision=wait_gate('/scratch/functional-decision.json');robust={};train_all=[];selected=decision.get('candidate');selected_reload=None
 if decision['action']=='verify':
  assert selected in checkpoints;path=outdir/checkpoints[selected]['adapter_relative_path'];selected_reload=load_exact_adapter(model,path,'selected',False);activate('selected',False)
  for b in [1,4]:
   for c in [False,True]:robust['batch'+str(b)+'_cache'+str(c)]=infer(panels['legacy_new64']+panels['new_dev32'],'robust_batch'+str(b)+'_cache'+str(c),b,c)
  train_all=infer(data['train_new_messages'],'train_all384')
 else:assert decision['action']=='stop';selected=None
 emit('FUNCTIONAL_ROBUSTNESS_ARTIFACT',{'selected':selected,'selected_reload':selected_reload,'outputs':robust,'train_all':train_all,'GPU':torch.cuda.get_device_name(0),'wall_seconds':time.monotonic()-started,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated()});print('READY_FOR_FUNCTIONAL_EXPORT',flush=True)
 decision=wait_gate('/scratch/functional-export-decision.json');confirmation={}
 if decision['action']=='confirm':
  assert selected is not None;rows=json.loads(Path('/scratch/functional-confirm-inputs.json').read_text());assert len(rows)==64 and sha('/scratch/functional-confirm-inputs.json')==decision['inputs_sha256']
  with model.disable_adapter():confirmation['E0']=infer(rows,'confirm_E0')
  activate('baseline',False);confirmation['F22']=infer(rows,'confirm_F22');activate('selected',False);confirmation[selected]=infer(rows,'confirm_selected');emit('FUNCTIONAL_CONFIRM_ARTIFACT',{'selected':selected,'outputs':confirmation,'inputs_sha256':decision['inputs_sha256'],'optimizer_steps_after_selection':0});print('READY_FOR_FUNCTIONAL_FINAL_EXPORT',flush=True);decision=wait_gate('/scratch/functional-final-exported.json')
 assert decision['action']=='finish';print('FUNCTIONAL_COMPLETE',flush=True)
