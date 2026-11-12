"""Evaluation only. No optimizer, training labels, or post-confirmation tuning."""
import base64,concurrent.futures,gzip,hashlib,json,os,sys,tarfile,time
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(8*1024**2),b''):h.update(x)
 return h.hexdigest()
def main():
 started=time.monotonic();cfg=json.loads(Path('/input/config.json').read_text());p=cfg['model_protocol'];raw=Path('/input/inputs.json.gz').read_bytes();assert hashlib.sha256(raw).hexdigest()==cfg['final64_inputs_gzip_sha256']
 rows=json.loads(gzip.decompress(raw))['holdout'];assert len(rows)==len({r['id'] for r in rows})==64 and all(set(r)=={'id','native_messages'} for r in rows)
 assert sha('/input/worker.py')==cfg['worker_sha256'];assert os.environ['CUBLAS_WORKSPACE_CONFIG']==':4096:8'
 modeldir=Path('/scratch/model');modeldir.mkdir()
 def copy(item):
  name,expected=item;assert Path(name).name==name;src=Path('/cache/model')/name;dest=modeldir/name;h=hashlib.sha256()
  with src.open('rb') as a,dest.open('xb') as b:
   for block in iter(lambda:a.read(8*1024**2),b''):h.update(block);b.write(block)
  assert h.hexdigest()==expected;print('STAGED '+name,flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(copy,p['checkpoint_files'].items()))
 assert sha('/cache/runtime-deps.tar')==p['runtime_archive_sha256'];deps=Path('/scratch/deps');deps.mkdir()
 with tarfile.open('/cache/runtime-deps.tar') as t:
  assert all(m.isfile() and (deps/m.name).resolve().is_relative_to(deps.resolve()) for m in t.getmembers());t.extractall(deps,filter='data')
 sys.path.insert(0,str(deps))
 import torch
 from transformers import AutoModelForCausalLM,AutoTokenizer
 from peft import PeftModel
 from importlib.metadata import version
 assert {n:version(n) for n in p['expected_packages']}==p['expected_packages'];assert torch.cuda.is_available() and torch.cuda.get_device_name(0) in p['allowed_GPU_models']
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False);torch.backends.cuda.enable_math_sdp(True);torch.set_num_threads(2)
 tok=AutoTokenizer.from_pretrained(modeldir,local_files_only=True,trust_remote_code=False,fix_mistral_regex=False);tok.padding_side='left';tok.pad_token=tok.eos_token;assert tok.eos_token_id==151645
 model=AutoModelForCausalLM.from_pretrained(modeldir,local_files_only=True,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='sdpa');model.requires_grad_(False);model.eval()
 def infer(data,cid):
  result=[]
  for offset in range(0,len(data),p['batch_size']):
   batch=data[offset:offset+p['batch_size']];prompts=[tok.apply_chat_template(r['native_messages'],tokenize=False,add_generation_prompt=True) for r in batch];assert all(t.endswith('<think>') for t in prompts)
   inputs=tok(prompts,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda');torch.manual_seed(p['inference_seed'])
   with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=p['max_new_tokens'],do_sample=False,use_cache=True,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id,temperature=None,top_p=None,top_k=None)
   for r,ids in zip(batch,output[:,inputs['input_ids'].shape[1]:].tolist()):
    truncated=tok.eos_token_id not in ids;effective=ids if truncated else ids[:ids.index(tok.eos_token_id)];result.append({'id':r['id'],'response':tok.decode(effective,skip_special_tokens=False,clean_up_tokenization_spaces=False),'truncated':truncated,'generated_tokens':len(effective)})
   print('FINAL64_INFER '+cid+' '+str(offset+len(batch)),flush=True)
  return result
 anchors=infer(cfg['anchors'],'E0-anchor');assert {r['id']:r['response'] for r in anchors}==cfg['expected_anchor_responses'],'Fresh-cohort anchor mismatch; refuse confirmation'
 outputs={'E0':infer(rows,'E0')};peft=False;adapter_checks={}
 for cid,expected in cfg['adapters'].items():
  adapter=Path('/cache/kali-8b-verified64-study')/cid/'adapter';assert sha(adapter/'adapter_model.safetensors')==expected['weights_sha256'] and sha(adapter/'adapter_config.json')==expected['config_sha256']
  if not peft:model=PeftModel.from_pretrained(model,adapter,adapter_name=cid,is_trainable=False);peft=True
  else:model.load_adapter(adapter,adapter_name=cid,is_trainable=False)
  model.set_adapter(cid);model.requires_grad_(False);model.eval();outputs[cid]=infer(rows,cid);adapter_checks[cid]=expected
 assert all(param.grad is None for param in model.parameters()),'Evaluation unexpectedly created gradients'
 packed=base64.b64encode(gzip.compress(json.dumps(outputs,ensure_ascii=False).encode())).decode();print('FINAL64_PREDICTIONS='+packed,flush=True)
 receipt={'status':'COMPLETE_FROZEN64_EVAL_ONLY','rows_per_arm':64,'arms':list(outputs),'optimizer_steps':0,'gradients_created':False,'GPU':torch.cuda.get_device_name(0),'GPU_count':1,'adapter_sha256':adapter_checks,'worker_sha256':sha('/input/worker.py'),'config_sha256':sha('/input/config.json'),'selection_sha256':cfg['selection_sha256'],'wall_seconds':round(time.monotonic()-started,2),'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'official_TEST_rows':0}
 print('FINAL64_RECEIPT='+json.dumps(receipt),flush=True)
if __name__=='__main__':main()
