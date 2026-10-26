#!/usr/bin/env python3
"""Portable finite single-GPU SFT using the audited shared recipe consumer.

Requires local pinned weights and eligible encoded TRAIN. Does not submit cluster
jobs, download weights, call teachers, load evaluation data or select candidates.
"""
import argparse,hashlib,json
from pathlib import Path
from kali_sft_recipe import validate_recipe,train_fixed_sft

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()

def main():
 a=argparse.ArgumentParser();a.add_argument('--model-dir',type=Path,required=True);a.add_argument('--model-config',type=Path,required=True);a.add_argument('--optimizer-config',type=Path,required=True);a.add_argument('--encoded-train',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
 if args.output.exists():raise ValueError('No overwriting existing experiment')
 c=json.loads(args.model_config.read_text());optimizer=json.loads(args.optimizer_config.read_text());rows=json.loads(args.encoded_train.read_text());validate_recipe(optimizer,rows)
 if set(c)!={'model_id','revision','LoRA','quantization','checkpoint_files_sha256','expected_runtime'}:raise ValueError('Unknown/missing model configuration field')
 if c['quantization']!={'type':'nf4','compute':'bfloat16','double_quant':False}:raise ValueError('Only reviewed NF4/BF16 mode supported by this entrypoint')
 for name,digest in c['checkpoint_files_sha256'].items():
  if Path(name).name!=name or sha(args.model_dir/name)!=digest:raise ValueError('Pinned model file mismatch')
 import torch
 from importlib.metadata import version
 from transformers import AutoModelForCausalLM,BitsAndBytesConfig
 from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training,set_peft_model_state_dict
 from safetensors.torch import load_file
 actual={k:version(k) for k in c['expected_runtime']}
 if actual!=c['expected_runtime']:raise ValueError('Runtime mismatch;use recorded versions')
 if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise ValueError('BF16-capable CUDA GPU required')
 torch.manual_seed(optimizer['seed']);model=AutoModelForCausalLM.from_pretrained(args.model_dir,local_files_only=True,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='sdpa',quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type=c['quantization']['type'],bnb_4bit_compute_dtype=getattr(torch,c['quantization']['compute']),bnb_4bit_use_double_quant=c['quantization']['double_quant']));model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False});model=get_peft_model(model,LoraConfig(**c['LoRA']));model.config.use_cache=False
 receipt=train_fixed_sft(model,rows,optimizer,'cuda',lambda step:print(json.dumps(step),flush=True));args.output.mkdir(parents=True,exist_ok=False);model.eval();model.gradient_checkpointing_disable();model.save_pretrained(args.output/'adapter');probe=torch.tensor([rows[0]['input_ids']],device='cuda')
 with torch.inference_mode():reference=model(input_ids=probe,use_cache=False).logits[:,-1,:].float().cpu()
 saved=load_file(str(args.output/'adapter/adapter_model.safetensors'))
 with torch.no_grad():
  for v in model.parameters():
   if v.requires_grad:v.zero_()
 set_peft_model_state_dict(model,saved,adapter_name='default')
 with torch.inference_mode():reloaded=model(input_ids=probe,use_cache=False).logits[:,-1,:].float().cpu()
 delta=float((reference-reloaded).abs().max())
 if delta>1e-4:raise ValueError('Adapter reload failed')
 receipt.update({'status':'COMPLETE_TRAINING_NOT_BENCHMARK_EVALUATION','model_id':c['model_id'],'revision':c['revision'],'model_config':c,'runtime':actual,'GPU':torch.cuda.get_device_name(0),'adapter_reload_max_logit_delta':delta,'adapter_sha256':sha(args.output/'adapter/adapter_model.safetensors'),'TRAIN_file_sha256':sha(args.encoded_train),'official_or_validation_model_calls':0,'external_teacher_calls':0,'native_ABA_search':False})
 (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'status':receipt['status'],'optimizer_steps':receipt['optimizer_steps'],'reload_delta':delta}))

if __name__=='__main__':main()
