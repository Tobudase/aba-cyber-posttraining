"""Check locally backed-up LoRA tensors against completed-run receipts."""
import argparse,hashlib,json
from pathlib import Path
import torch
from safetensors.torch import load_file

def main():
 p=argparse.ArgumentParser();p.add_argument('--job-dir',type=Path,required=True);a=p.parse_args();summary={}
 for arm in ['answer_only','reasoning']:
  path=a.job_dir/'adapters'/arm/'adapter/adapter_model.safetensors';receipt=json.loads((a.job_dir/'collected'/arm/'receipt.json').read_text())
  digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==receipt['adapter_sha256']
  tensors=load_file(str(path),device='cpu');assert len(tensors)==144 and sum(v.numel() for v in tensors.values())==7667712
  assert all(torch.isfinite(v).all() for v in tensors.values())
  b=[v for k,v in tensors.items() if 'lora_B' in k];assert len(b)==72 and all(bool(v.any()) for v in b)
  r={'arm':arm,'tensor_count':144,'trainable_parameters':7667712,'all_finite':True,'all_72_B_matrices_nonzero':True,'receipt_hash_matches':True,'dtypes':sorted({str(v.dtype) for v in tensors.values()}),'adapter_sha256':digest}
  assert r['dtypes']==['torch.float32']
  (a.job_dir/(arm+'-adapter-audit-private.json')).write_text(json.dumps(r,indent=2)+'\n');summary[arm]={k:v for k,v in r.items() if k!='adapter_sha256'}
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
