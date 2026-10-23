"""Frozen CUDA train or inference worker; inputs are role-projected, no scorer."""
import base64,hashlib,json,math,os,sys,tarfile,threading,time,subprocess
from pathlib import Path

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
 return h.hexdigest()

def prompt_for(tok,messages):
 native=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
 if not native.endswith('<think>'):raise ValueError('Unexpected native inference prefix')
 marker='KALI_CUDA_BOUNDARY';full=tok.apply_chat_template(messages+[{'role':'assistant','content':marker}],tokenize=False,add_generation_prompt=False)
 if full.count(marker)!=1 or full.split(marker)[0]!=native[:-7]:raise ValueError('SFT boundary mismatch')
 return native[:-7]

def main(payload):
 protocol=payload['protocol'];phase=payload['phase'];run=payload['run_id']
 if phase not in {'train','infer'} or run not in {'E0','E1','E2'}:raise ValueError('Invalid role')
 canonical=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
 if hashlib.sha256(canonical(protocol)).hexdigest()!=payload['protocol_sha256']:raise ValueError('Protocol hash mismatch')
 if digest('/input/runner.py')!=protocol['runner_sha256']:raise ValueError('Runner hash mismatch')
 field='train_rows' if phase=='train' else 'inference_rows'
 if hashlib.sha256(canonical(payload[field])).hexdigest()!=protocol[field+'_sha256']:raise ValueError('Frozen input projection mismatch')
 if phase=='train' and run=='E0':raise ValueError('Baseline cannot train')
 root=Path('/cache');out=root/'cuda-cycle-v1'/run/phase;out.mkdir(parents=True,exist_ok=False)
 started=time.monotonic();receipt={'status':'RUNNING','run_id':run,'phase':phase,'protocol_sha256':payload['protocol_sha256'],'runner_sha256':hashlib.sha256(Path('/input/runner.py').read_bytes()).hexdigest(),'official_test_rows':0,'confirmation_rows':0,'labels_in_inference_input':False}
 scratch=Path('/scratch');modeldir=scratch/'model';modeldir.mkdir()
 for name,expected in protocol['checkpoint_files'].items():
  if Path(name).name!=name:raise ValueError('Unexpected filename')
  h=hashlib.sha256()
  with (root/'model'/name).open('rb') as inp,(modeldir/name).open('wb') as dest:
   for block in iter(lambda:inp.read(8*1024**2),b''):h.update(block);dest.write(block)
  if h.hexdigest()!=expected:raise ValueError('Checkpoint hash mismatch')
  print('STAGED '+name,flush=True)
 archive=root/'runtime-deps.tar'
 if digest(archive)!=protocol['runtime_archive_sha256']:raise ValueError('Dependency archive mismatch')
 deps=scratch/'deps';deps.mkdir()
 with tarfile.open(archive) as tar:
  for m in tar.getmembers():
   if not m.isfile() or not (deps/m.name).resolve().is_relative_to(deps.resolve()):raise ValueError('Unsafe archive member')
  tar.extractall(deps,filter='data')
 sys.path.insert(0,str(deps));receipt['staging_seconds']=time.monotonic()-started
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training,set_peft_model_state_dict
 from safetensors.torch import load_file
 import importlib.metadata
 if not torch.cuda.is_available() or torch.cuda.get_device_name(0)!=protocol['GPU_model']:raise ValueError('Frozen GPU class unavailable')
 torch.manual_seed(42);torch.set_num_threads(2);torch.cuda.reset_peak_memory_stats()
 receipt['GPU']=torch.cuda.get_device_name(0);receipt['packages']={n:importlib.metadata.version(n) for n in ['torch','transformers','peft','accelerate','bitsandbytes','safetensors']}
 telemetry=[];stop=threading.Event()
 def monitor():
  while not stop.is_set():
   x=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
   telemetry.append({'seconds':round(time.monotonic()-started,2),'returncode':x.returncode,'GPU':x.stdout.strip()});stop.wait(10)
 t=threading.Thread(target=monitor,daemon=True);t.start()
 try:
  tok=AutoTokenizer.from_pretrained(modeldir,local_files_only=True,trust_remote_code=False,fix_mistral_regex=False)
  base=AutoModelForCausalLM.from_pretrained(modeldir,local_files_only=True,trust_remote_code=False,device_map={'':0},dtype=torch.bfloat16,attn_implementation='sdpa',quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype=torch.bfloat16))
  base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=phase=='train',gradient_checkpointing_kwargs={'use_reentrant':False})
  model=get_peft_model(base,LoraConfig(r=16,lora_alpha=32,target_modules=['q_proj','v_proj'],lora_dropout=0.0,task_type='CAUSAL_LM'))
  params={n:p for n,p in model.named_parameters() if p.requires_grad}
  if phase=='train':
   rows=payload['train_rows']
   if len(rows)!=128 or any(r['split']!='train' or not r['training_eligible'] or r['official_test'] for r in rows):raise ValueError('TRAIN-only input required')
   model.config.use_cache=False;model.train();optimizer=torch.optim.AdamW(params.values(),lr=protocol['training']['learning_rate'],weight_decay=0)
   before={n:p.detach().cpu().clone() for n,p in params.items()};order=list(range(128));__import__('random').Random(42).shuffle(order);losses=[]
   for step,i in enumerate(order,1):
    row=rows[i];prefix=prompt_for(tok,row['messages']);full=tok.apply_chat_template(row['messages']+[{'role':'assistant','content':row['target']}],tokenize=False,add_generation_prompt=False)
    pids=tok.encode(prefix,add_special_tokens=False);ids=tok.encode(full,add_special_tokens=False)
    if ids[:len(pids)]!=pids or len(ids)>2048:raise ValueError('Native supervision boundary/length mismatch')
    labels=[-100]*len(pids)+ids[len(pids):];batch={'input_ids':torch.tensor([ids],device='cuda'),'attention_mask':torch.ones((1,len(ids)),dtype=torch.long,device='cuda'),'labels':torch.tensor([labels],device='cuda')}
    optimizer.zero_grad();loss=model(**batch).loss
    if not math.isfinite(float(loss.detach())):raise ValueError('Nonfinite loss')
    loss.backward();optimizer.step();losses.append(float(loss.detach()));print('TRAIN '+str(step),flush=True)
   model.eval();changed=sum(not torch.equal(before[n],p.detach().cpu()) for n,p in params.items())
   if changed==0:raise ValueError('No actual optimization')
   model.save_pretrained(out/'adapter');saved=load_file(str(out/'adapter/adapter_model.safetensors'))
   with torch.no_grad():reference=model(input_ids=batch['input_ids']).logits[:,-1,:].float().cpu()
   with torch.no_grad():
    for p in params.values():p.zero_()
   set_peft_model_state_dict(model,saved,adapter_name='default')
   with torch.no_grad():actual=model(input_ids=batch['input_ids']).logits[:,-1,:].float().cpu()
   delta=float((reference-actual).abs().max())
   if delta>1e-4:raise ValueError('Saved adapter reload mismatch')
   receipt.update(optimizer_steps=128,train_ids=[rows[i]['id'] for i in order],losses=losses,changed_parameter_tensors=changed,trainable_parameters=sum(p.numel() for p in params.values()),adapter_reload_max_logit_delta=delta,adapter_sha256=digest(out/'adapter/adapter_model.safetensors'),development_rows_used_for_optimization=0)
  else:
   rows=payload['inference_rows']
   if any(set(r)!={'id','messages','prompt_sha256','set'} for r in rows):raise ValueError('Inference projection contains unexpected fields/labels')
   if run!='E0':
    train=root/'cuda-cycle-v1'/run/'train';tr=json.loads((train/'receipt.json').read_text())
    if tr['status']!='COMPLETE' or tr['protocol_sha256']!=payload['protocol_sha256'] or digest(train/'adapter/adapter_model.safetensors')!=tr['adapter_sha256']:raise ValueError('Adapter provenance mismatch')
    set_peft_model_state_dict(model,load_file(str(train/'adapter/adapter_model.safetensors')),adapter_name='default');receipt['training_receipt_sha256']=digest(train/'receipt.json')
   else:
    if any(torch.count_nonzero(p).item()!=0 for n,p in params.items() if 'lora_B' in n):raise ValueError('E0 not zero adapter')
    receipt['baseline']='OriginalNF4 prepared exactly asE1, zeroBLoRA; no optimizer updates'
   model.eval();model.gradient_checkpointing_disable();model.config.use_cache=True;records=[]
   for row in rows:
    prompt=prompt_for(tok,row['messages']);h=hashlib.sha256(prompt.encode()).hexdigest()
    if h!=row['prompt_sha256']:raise ValueError('Frozen prompt changed')
    inputs=tok(prompt,add_special_tokens=False,return_tensors='pt').to('cuda');length=inputs['input_ids'].shape[-1]
    torch.manual_seed(42)
    with torch.no_grad():tokens=model.generate(**inputs,max_new_tokens=protocol['inference']['max_output_tokens'],do_sample=False,use_cache=True,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id)[0,length:].tolist()
    stopped=bool(tokens and tokens[-1]==tok.eos_token_id);canonical=tokens[:-1] if stopped else tokens
    record={'id':row['id'],'set':row['set'],'response':tok.decode(canonical,skip_special_tokens=False,clean_up_tokenization_spaces=False),'generated_token_ids':canonical,'output_tokens':len(tokens),'input_tokens':length,'prompt_sha256':h,'truncated':not stopped and len(tokens)>=protocol['inference']['max_output_tokens']}
    records.append(record)
    with (out/'predictions.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    print('INFER '+str(len(records))+'/'+str(len(rows)),flush=True)
   receipt.update(inference_rows=len(rows),predictions_sha256=digest(out/'predictions.jsonl'),truncated_rows=sum(x['truncated'] for x in records))
   print('KALI_CUDA_PREDICTIONS_BASE64='+base64.b64encode((out/'predictions.jsonl').read_bytes()).decode(),flush=True)
  receipt['status']='COMPLETE'
 except Exception as exc:
  receipt.update(status='FAILED',error=type(exc).__name__+': '+str(exc));raise
 finally:
  stop.set();t.join(timeout=11);receipt.update(peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),wall_seconds=time.monotonic()-started,GPU_samples=telemetry)
  (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('KALI_CUDA_CYCLE_RESULT='+json.dumps(receipt),flush=True)
if __name__=='__main__':main(json.loads(Path('/input/payload.json').read_text()))
