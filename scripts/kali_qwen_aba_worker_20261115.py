"""One GPU, sequential original RedSage/Qwen paired-baseline SFT pilot.

Expanded DEV46 + old64. No candidate command is executed. Eval references are absent. Every model starts
from pinned publisher weights with fresh FP32 zero-B LoRA; no warm adapter.
"""
import base64,concurrent.futures,gc,gzip,hashlib,json,math,os,random,shutil,sys,tarfile,time
from pathlib import Path

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
 return h.hexdigest()

def prepare_output_directory(path):
 """Allow a brand-new cache volume, but never overwrite an existing run."""
 out=Path(path);out.mkdir(parents=True,exist_ok=False);return out

def main():
 started=time.monotonic();cfg=json.loads(Path('/input/config.json').read_text());raw=Path('/input/inputs.json.gz').read_bytes();assert sha('/input/worker.py')==cfg['worker_sha256'] and hashlib.sha256(raw).hexdigest()==cfg['inputs_sha256']
 data=json.loads(gzip.decompress(raw));protocols=cfg['model_protocols'];out=prepare_output_directory(cfg['durable_output'])
 def save(name,value):
  p=out/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value)+'\n');t.replace(p)
 assert sha('/cache/runtime-deps.tar')==protocols['qwen']['runtime_archive_sha256'];deps=Path('/scratch/deps');deps.mkdir()
 with tarfile.open('/cache/runtime-deps.tar') as tar:
  assert all(m.isfile() and (deps/m.name).resolve().is_relative_to(deps.resolve()) for m in tar.getmembers());tar.extractall(deps,filter='data')
 sys.path.insert(0,str(deps));sys.path.insert(0,'/input')
 import torch
 from importlib.metadata import version
 from transformers import AutoTokenizer,AutoModelForCausalLM,LogitsProcessorList
 from peft import get_peft_model,LoraConfig,get_peft_model_state_dict
 from kali_command_ngram_guard_20261115 import CommandNGramGuard
 from kali_stable_objective_20261114 import objective_sums
 from kali_exact_adapter_loading_20261115 import load_exact_adapter
 assert {n:version(n) for n in protocols['qwen']['expected_packages']}==protocols['qwen']['expected_packages']
 assert torch.cuda.is_available() and torch.cuda.get_device_name(0) in protocols['qwen']['allowed_GPU_models']
 assert torch.cuda.get_device_capability(0)[0]>=8 and torch.cuda.get_device_properties(0).total_memory>=20*1024**3
 probe=torch.ones((128,128),device='cuda',dtype=torch.bfloat16);assert torch.isfinite(probe@probe).all();del probe
 assert all(sha('/input/'+n)==v for n,v in cfg['module_sha256'].items())
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False);torch.backends.cuda.enable_math_sdp(True)
 receipt={'mode':cfg['mode'],'learning_rate':cfg.get('learning_rate'),'status':'RUNNING','GPU':torch.cuda.get_device_name(0),'worker_sha256':sha('/input/worker.py'),'config_sha256':sha('/input/config.json'),'inputs_sha256':cfg['inputs_sha256'],'models':{},'official_TEST_queries':0,'confirmation_model_queries':0}
 predictions={};evalrows=sum(data['panels'].values(),[]);assert len(evalrows)==110 and len({r['id'] for r in evalrows})==110
 for name in ['qwen']:
  p=protocols[name];model_started=time.monotonic();modeldir=Path('/scratch/model');modeldir.mkdir();torch.cuda.reset_peak_memory_stats()
  def copy(item):
   import requests
   filename,expected=item;assert Path(filename).name==filename;dest=modeldir/filename
   for attempt in range(3):
    try:
     with requests.get('https://huggingface.co/'+p['model_id']+'/resolve/'+p['model_revision']+'/'+filename+'?download=true',stream=True,timeout=(20,90)) as r:
      r.raise_for_status();h=hashlib.sha256()
      with dest.open('wb') as f:
       for block in r.iter_content(8*1024**2):
        if block:f.write(block);h.update(block)
     assert h.hexdigest()==expected,'Model hash mismatch';print('TWO_MODEL_STAGED '+name+' '+filename,flush=True);return
    except Exception:
     if attempt==2:raise
     time.sleep(3)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(copy,p['checkpoint_files'].items()))
  tok=AutoTokenizer.from_pretrained(modeldir,local_files_only=True,trust_remote_code=False,fix_mistral_regex=False);tok.padding_side='left';tok.pad_token=tok.eos_token;assert tok.eos_token_id==151645
  model=AutoModelForCausalLM.from_pretrained(modeldir,local_files_only=True,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='sdpa');model.requires_grad_(False);model.eval()
  def infer(rows,label,guarded=True):
   model.eval();res=[]
   for offset in range(0,len(rows),4):
    batch=rows[offset:offset+4];texts=[tok.apply_chat_template(r['native_messages'],tokenize=False,add_generation_prompt=True,**({'enable_thinking':False} if name=='qwen' else {})) for r in batch]
    inputs=tok(texts,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda');length=inputs['input_ids'].shape[1];torch.manual_seed(3407)
    extra={'logits_processor':LogitsProcessorList([CommandNGramGuard(tok,length,8)])} if guarded else {}
    with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=1024,do_sample=False,use_cache=True,pad_token_id=151645,eos_token_id=151645,temperature=None,top_p=None,top_k=None,**extra)
    for row,ids in zip(batch,generated[:,length:].cpu().tolist()):
     ended=151645 in ids;body=ids[:ids.index(151645)] if ended else ids
     res.append({'id':row['id'],'response':tok.decode(body,skip_special_tokens=False,clean_up_tokenization_spaces=False),'truncated':not ended,'generated_tokens':len(body),'early_EOS_first_two':151645 in ids[:2]})
    save(label+'.json',res);print('TWO_MODEL_INFER '+label+' '+str(len(res))+'/'+str(len(rows)),flush=True)
   predictions[label]=res;return res
  baseline=infer(evalrows,name+'_base')
  train=data['encoded'][name]
  assert len(train)==256 and all(len(r['input_ids'])==len(r['labels']) and all(v==-100 for v in r['labels'][:r['prompt_tokens']]) and r['labels'][r['prompt_tokens']:]==r['input_ids'][r['prompt_tokens']:] for r in train)
  probe=train[0];probeids=torch.tensor([probe['input_ids']],device='cuda');kw={'input_ids':probeids,'attention_mask':torch.ones_like(probeids),'use_cache':False}
  with torch.no_grad():probe_base=model(**kw).logits[:,-1].detach().cpu()
  torch.manual_seed(42);model=get_peft_model(model,LoraConfig(r=16,lora_alpha=32,target_modules=['q_proj','v_proj'],lora_dropout=0,bias='none',task_type='CAUSAL_LM',init_lora_weights=True))
  for n,param in model.named_parameters():
   if param.requires_grad:param.data=param.data.float()
  with torch.no_grad():delta=float((model(**kw).logits[:,-1].detach().cpu().float()-probe_base.float()).abs().max());assert delta==0
  if cfg['mode']=='controls':
   adapter=Path(cfg['fixed_adapter']);assert sha(adapter/'adapter_model.safetensors')==cfg['fixed_adapter_sha256']
   audit=load_exact_adapter(model,adapter,'fixed',False);model.set_adapter('fixed');infer(evalrows,'qwen_fixed')
   receipt['models']['qwen']={'model_id':p['model_id'],'model_revision':p['model_revision'],'optimizer_steps':0,'fixed_adapter_sha256':cfg['fixed_adapter_sha256'],'exact_load_audit':audit,'initial_zero_B_probe_difference':delta,'wall_seconds':time.monotonic()-model_started}
   receipt.update(status='QWEN_CONTROLS_COMPLETE',wall_seconds=time.monotonic()-started);save('receipt.json',receipt);save('predictions.json',predictions)
   print('TWO_MODEL_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps({'receipt':receipt,'predictions':predictions}).encode())).decode(),flush=True);print('TWO_MODEL_COMPLETE',flush=True);return
  initial={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()};assert len(initial)==144 and all(not bool(v.any()) for k,v in initial.items() if '.lora_B.' in k)
  init_hash=hashlib.sha256(b''.join(initial[k].numpy().tobytes() for k in sorted(initial))).hexdigest()
  params=[v for v in model.parameters() if v.requires_grad];optimizer=torch.optim.AdamW(params,lr=cfg['learning_rate'],betas=(.9,.999),eps=1e-8,weight_decay=0)
  model.enable_input_require_grads();model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.config.use_cache=False
  traces=[];cps={};training_started=time.monotonic()
  for epoch,order in enumerate(data['epoch_orders']):
   assert sorted(order)==list(range(256));torch.manual_seed(42+epoch)
   for offset in range(0,256,4):
    rows=[train[i] for i in order[offset:offset+4]];total=sum(r['target_tokens'] for r in rows);optimizer.zero_grad(set_to_none=True);ce_sum=0.;window_started=time.monotonic();model.train()
    for row in rows:
     ids=torch.tensor([row['input_ids']],device='cuda');labels=torch.tensor([row['labels']],device='cuda');logits=model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False).logits;ce,_,n=objective_sums(logits,labels);assert n==row['target_tokens'];loss=ce/total;assert math.isfinite(float(loss.detach()));loss.backward();ce_sum+=float(ce.detach());del logits,ce,loss
    gradient=float(torch.nn.utils.clip_grad_norm_(params,1.));assert math.isfinite(gradient) and gradient>0;optimizer.step();step=len(traces)+1
    traces.append({'step':step,'epoch':epoch+1,'ids':[r['id'] for r in rows],'target_tokens':total,'ce_mean':ce_sum/total,'grad_norm_before_clip':gradient,'window_seconds':time.monotonic()-window_started});save(name+'-trace.json',traces)
    if step%16==0:print('TWO_MODEL_TRAIN '+name+' '+json.dumps({k:v for k,v in traces[-1].items() if k!='ids'}),flush=True)
   if len(traces)==128:
    step=len(traces);label=name+'_step'+str(step);adapter=out/label/'adapter';model.save_pretrained(adapter)
    ac=json.loads((adapter/'adapter_config.json').read_text());ac.update(base_model_name_or_path=p['model_id'],revision=p['model_revision']);(adapter/'adapter_config.json').write_text(json.dumps(ac,indent=2)+'\n')
    state=get_peft_model_state_dict(model);changed=sum(not torch.equal(v.detach().cpu(),initial[k]) for k,v in state.items());assert changed==144
    cps[label]={'optimizer_steps':step,'weights_sha256':sha(adapter/'adapter_model.safetensors'),'config_sha256':sha(adapter/'adapter_config.json'),'changed_tensors':changed,'adapter_relative_path':str(adapter.relative_to(out))}
    infer(evalrows,label)
  train_elapsed=time.monotonic()-training_started
  assert len(traces)==128
  # Verify actual exported weights by an independent adapter load and a complete
  # generation check, rather than just trusting save_pretrained's return.
  model.eval();checkrows=data['panels']['new_dev46'][:4];actual=infer(checkrows,name+'_before_reload')
  load_audit=load_exact_adapter(model,out/(name+'_step128')/'adapter','check',False);model.set_adapter('check');reloadrows=infer(checkrows,name+'_after_reload');assert actual==reloadrows
  receipt['models'][name]={'model_id':p['model_id'],'model_revision':p['model_revision'],'optimizer_steps':len(traces),'nonzero_gradient_steps':sum(t['grad_norm_before_clip']>0 for t in traces),'supervised_tokens':sum(t['target_tokens'] for t in traces),'training_trace':traces,'initial_adapter_sha256':init_hash,'initial_zero_B_probe_difference':delta,'checkpoints':cps,'reload_audit':load_audit,'reload_complete_responses_identical':True,'wall_seconds':time.monotonic()-model_started,'training_and_checkpoint_eval_seconds':train_elapsed,'peak_cuda_bytes':torch.cuda.max_memory_allocated(),'order_sha256':[hashlib.sha256(json.dumps(x).encode()).hexdigest() for x in data['epoch_orders']]}
  save('receipt.json',receipt);save('predictions.json',predictions)
  # Free the first complete model, its graph references, optimizer and scratch
  # weights before staging the second; both arms use the same allocated GPU.
  del model,optimizer,params,state,initial,probeids,probe_base,kw;gc.collect();torch.cuda.empty_cache();shutil.rmtree(modeldir)
  print('TWO_MODEL_ARM_COMPLETE '+name,flush=True)
 receipt.update(status='TWO_MODEL_SFT_COMPUTE_COMPLETE',wall_seconds=time.monotonic()-started)
 save('receipt.json',receipt);save('predictions.json',predictions)
 archive=out/'adapters.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for label in [n+'_step'+str(s) for n in ['qwen'] for s in [128]]:tar.add(out/label,arcname=label)
  tar.add(out/'receipt.json',arcname='receipt.json')
 receipt['archive_sha256']=sha(archive);save('receipt.json',receipt)
 packed=base64.b64encode(gzip.compress(json.dumps({'receipt':receipt,'predictions':predictions}).encode())).decode();print('TWO_MODEL_ARTIFACT='+packed,flush=True);print('TWO_MODEL_COMPLETE',flush=True)
if __name__=='__main__':main()
