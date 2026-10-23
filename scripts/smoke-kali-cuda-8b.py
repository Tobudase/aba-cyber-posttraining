"""Finite20-step real pinned8B NF4 LoRA runtime check on TRAIN only."""
import hashlib,json,math,os,subprocess,sys,threading,time
from pathlib import Path

def main(rows):
 start=time.monotonic();cache=Path('/cache');prefetch=json.loads((cache/'prefetch-receipt.json').read_text())
 if prefetch['status']!='CPU_PREFETCH_COMPLETE' or prefetch['revision']!='843e2e3096e7de68f5c35eb16238f4909f21695a':raise ValueError('Verified CPU cache required')
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
 assert torch.cuda.is_available();torch.manual_seed(42);torch.set_num_threads(2)
 if torch.cuda.get_device_capability()[0]<8:raise RuntimeError('Ampere or newer required')
 usage=[];stop=threading.Event()
 def monitor():
  while not stop.is_set():
   r=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader,nounits'],text=True,capture_output=True,timeout=5)
   usage.append({'seconds':round(time.monotonic()-start,2),'reading':r.stdout.strip(),'returncode':r.returncode});stop.wait(5)
 t=threading.Thread(target=monitor,daemon=True);t.start()
 try:
  tok=AutoTokenizer.from_pretrained(cache/'model',local_files_only=True,trust_remote_code=False)
  base=AutoModelForCausalLM.from_pretrained(cache/'model',local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='sdpa',quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype=torch.bfloat16))
  base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
  model=get_peft_model(base,LoraConfig(r=16,lora_alpha=32,target_modules=['q_proj','v_proj'],lora_dropout=0.0,task_type='CAUSAL_LM'));model.config.use_cache=False
  params={n:p for n,p in model.named_parameters() if p.requires_grad};before={n:p.detach().cpu().clone() for n,p in params.items()}
  enc=[]
  for row in rows:
   assert row['split']=='train' and row['training_eligible'] and not row['official_test']
   messages=row['messages'];marker='KALI_SMOKE_BOUNDARY'
   full=tok.apply_chat_template(messages+[{'role':'assistant','content':row['target']}],tokenize=False,add_generation_prompt=False)
   marked=tok.apply_chat_template(messages+[{'role':'assistant','content':marker}],tokenize=False,add_generation_prompt=False)
   prefix=marked.split(marker)[0];ids=tok.encode(full,add_special_tokens=False);promptids=tok.encode(prefix,add_special_tokens=False)
   if ids[:len(promptids)]!=promptids or len(ids)>1024:raise ValueError('Assistant boundary/token budget mismatch')
   labels=[-100]*len(promptids)+ids[len(promptids):]
   enc.append({'input_ids':torch.tensor([ids],device='cuda'),'attention_mask':torch.ones((1,len(ids)),dtype=torch.long,device='cuda'),'labels':torch.tensor([labels],device='cuda')})
  model.train();optimizer=torch.optim.AdamW(params.values(),lr=1e-5,weight_decay=0);losses=[]
  for step in range(20):
   optimizer.zero_grad();loss=model(**enc[step%len(enc)]).loss
   if not math.isfinite(float(loss)):raise ValueError('Nonfinite loss')
   loss.backward();optimizer.step();losses.append(float(loss.detach()));print('STEP '+str(step+1),flush=True)
  model.eval();changed=sum(not torch.equal(before[n],p.detach().cpu()) for n,p in params.items())
  assert changed>0
  target=cache/'cuda-smoke-adapter';model.save_pretrained(target)
  with torch.no_grad():ref=model(input_ids=enc[0]['input_ids']).logits[:,-1,:].float().cpu()
  from safetensors.torch import load_file
  from peft import set_peft_model_state_dict
  saved=load_file(str(target/'adapter_model.safetensors'))
  with torch.no_grad():
   for p in params.values():p.zero_()
  set_peft_model_state_dict(model,saved,adapter_name='default')
  with torch.no_grad():restored=model(input_ids=enc[0]['input_ids']).logits[:,-1,:].float().cpu()
  delta=float((ref-restored).abs().max());assert delta<1e-4
  r={'status':'PASS_REAL_8B_CUDA_TRAIN_SMOKE','model_id':prefetch['model_id'],'revision':prefetch['revision'],'gpu':torch.cuda.get_device_name(0),'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,'quantization':'bitsandbytes NF4 BF16compute','lora':'rank16 alpha32 all q/v layers','steps':20,'train_rows':len(rows),'train_ids':[r['id'] for r in rows],'losses':losses,'changed_parameter_tensors':changed,'trainable_parameters':sum(p.numel() for p in params.values()),'reload_max_logit_delta':delta,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'wall_seconds':time.monotonic()-start,'official_test_rows':0,'confirmation_rows':0,'development_rows':0,'ABA_executed':False,'scope':'Runtime/persistence smoke on two training records, not domain evaluation or evidence of generalization','prefetch_receipt_sha256':hashlib.sha256((cache/'prefetch-receipt.json').read_bytes()).hexdigest(),'gpu_samples':usage}
  (cache/'cuda-smoke-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print('KALI_8B_GPU_RESULT='+json.dumps(r),flush=True)
 finally:stop.set();t.join(timeout=6)
if __name__=='__main__':main(json.loads(sys.argv[1]))
