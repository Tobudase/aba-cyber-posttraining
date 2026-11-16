"""Balanced continued SFT/replay and command-only frozen-reference KL controls."""
import base64,concurrent.futures,gzip,hashlib,json,os,sys,tarfile,time,shutil
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(8*1024**2),b''):h.update(x)
 return h.hexdigest()
def main():
 started=time.monotonic();cfg=json.loads(Path('/input/config.json').read_text());p=cfg['model_protocol'];raw=Path('/input/inputs.json.gz').read_bytes();assert hashlib.sha256(raw).hexdigest()==cfg['inputs_gzip_sha256']
 assert sha('/input/worker.py')==cfg['worker_sha256'];assert os.environ['CUBLAS_WORKSPACE_CONFIG']==':4096:8'
 modeldir=Path('/scratch/model');modeldir.mkdir()
 def copy(item):
  import requests
  name,expected=item;assert Path(name).name==name;dest=modeldir/name;h=hashlib.sha256()
  cached=Path('/cache/model')/name
  if cached.is_file():
   # Infrastructure only: bounded range copies, byte-for-byte SHA checked.
   srcfd=os.open(cached,os.O_RDONLY);dstfd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600);size=cached.stat().st_size;block=8*1024**2
   def piece(offset):
    content=os.pread(srcfd,min(block,size-offset),offset);assert len(content)==min(block,size-offset)
    written=os.pwrite(dstfd,content,offset);assert written==len(content)
   try:
    os.ftruncate(dstfd,size)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pieces:list(pieces.map(piece,range(0,size,block)))
    os.fsync(dstfd)
   finally:os.close(srcfd);os.close(dstfd)
   if sha(dest)==expected:
    print('STAGED_HASH_VERIFIED '+name+' source=existing_cache',flush=True);return
   dest.unlink() # Delete only the newly staged mismatching copy, preserve cache.
  url='https://huggingface.co/'+p['model_id']+'/resolve/'+p['model_revision']+'/'+name+'?download=true'
  with requests.get(url,stream=True,timeout=(15,60)) as response:
   response.raise_for_status()
   with dest.open('xb') as target:
    for block in response.iter_content(8*1024**2):
     if block:h.update(block);target.write(block)
  assert h.hexdigest()==expected,'Official checkpoint SHA mismatch: '+name
  print('STAGED_HASH_VERIFIED '+name,flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(copy,p['checkpoint_files'].items()))
 assert sha('/cache/runtime-deps.tar')==p['runtime_archive_sha256'];deps=Path('/scratch/deps');deps.mkdir()
 with tarfile.open('/cache/runtime-deps.tar') as t:
  assert all(m.isfile() and (deps/m.name).resolve().is_relative_to(deps.resolve()) for m in t.getmembers());t.extractall(deps,filter='data')
 sys.path.insert(0,str(deps))
 import torch
 from transformers import AutoModelForCausalLM,AutoTokenizer
 from peft import PeftModel
 from importlib.metadata import version
 assert {n:version(n) for n in p['expected_packages']}==p['expected_packages'];assert torch.cuda.is_available() and torch.cuda.get_device_name(0) in p['allowed_GPU_models']
 assert torch.cuda.get_device_capability(0)[0]>=8 and torch.cuda.is_bf16_supported(),'Native BF16 Ampere-or-newer GPU required'
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False);torch.backends.cuda.enable_math_sdp(True);torch.set_num_threads(2)
 tok=AutoTokenizer.from_pretrained(modeldir,local_files_only=True,trust_remote_code=False,fix_mistral_regex=False);tok.padding_side='left';tok.pad_token=tok.eos_token;assert tok.eos_token_id==151645
 model=AutoModelForCausalLM.from_pretrained(modeldir,local_files_only=True,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='sdpa');model.requires_grad_(False);model.eval()
 sys.path.insert(0,'/input')
 for file,expected in cfg['module_sha256'].items():assert sha('/input/'+file)==expected
 from kali_retention_body_v13_20261116 import run_repair
 run_repair(model,tok,torch,cfg,raw,started,sha)

if __name__=='__main__':main()



