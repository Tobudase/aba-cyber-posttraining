"""One GPU, post-selection confirmation of original/fixed/native Qwen models.

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
 assert cfg['mode']=='confirmation'
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
 predictions={};evalrows=sum(data['panels'].values(),[]);assert len(evalrows)==384 and len({r['id'] for r in evalrows})==384
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
  diagnostic=data['diagnostic_rows'];assert len(diagnostic)==4
  infer(diagnostic,'qwen_base_diag_guard',True);infer(diagnostic,'qwen_base_diag_raw',False)
  torch.manual_seed(42);model=get_peft_model(model,LoraConfig(r=16,lora_alpha=32,target_modules=['q_proj','v_proj'],lora_dropout=0,bias='none',task_type='CAUSAL_LM',init_lora_weights=True))
  for _,parameter in model.named_parameters():
   if parameter.requires_grad:parameter.data=parameter.data.float()
  audits=[]
  for info in cfg['confirmation_adapters']:
   adapter=Path(info['path']);assert sha(adapter/'adapter_model.safetensors')==info['sha256'];audit=load_exact_adapter(model,adapter,info['adapter_name'],False);model.set_adapter(info['adapter_name']);infer(evalrows,info['label']);infer(diagnostic,info['label']+'_diag_guard',True);infer(diagnostic,info['label']+'_diag_raw',False);audits.append({'label':info['label'],'adapter_sha256':info['sha256'],'exact_load_audit':audit})
  receipt['models']['qwen']={'model_id':p['model_id'],'model_revision':p['model_revision'],'optimizer_steps':0,'adapters':audits,'peak_cuda_bytes':torch.cuda.max_memory_allocated()}
  receipt.update(status='QWEN_CONFIRMATION_COMPLETE',wall_seconds=time.monotonic()-started,confirmation_model_queries=384*(1+len(audits)),diagnostic_model_queries=8*(1+len(audits)));save('receipt.json',receipt);save('predictions.json',predictions)
  print('TWO_MODEL_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps({'receipt':receipt,'predictions':predictions}).encode())).decode(),flush=True);print('CONFIRMATION_COMPLETE',flush=True);return
if __name__=='__main__':main()
