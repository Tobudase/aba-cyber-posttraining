"""CPU-only public checkpoint cache; verify every pinned file before GPU use."""
import hashlib,json,os,subprocess,sys,time,urllib.request
from pathlib import Path

def main(spec):
 import torch
 if torch.cuda.is_available():raise RuntimeError('Prefetch must not reserve a GPU')
 start=time.monotonic();root=Path('/cache');model=root/'model';model.mkdir(exist_ok=True)
 packages=['transformers==4.57.6','tokenizers==0.22.2','peft==0.17.1','accelerate==1.10.1','bitsandbytes==0.47.0','huggingface-hub==0.36.0','safetensors==0.6.2','regex==2025.9.18','packaging==25.0','PyYAML==6.0.3','psutil==7.1.0','tqdm==4.67.1','requests==2.32.5','fsspec==2025.9.0','filelock==3.19.1','typing_extensions==4.15.0']
 if not (root/'deps/regex').exists(): subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','--no-deps','--target',str(root/'deps')]+packages,check=True,timeout=300)
 env=os.environ.copy();env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');env.pop('PYTHONPATH',None)
 check=subprocess.run([sys.executable,'-c',"import sys,faulthandler;faulthandler.dump_traceback_later(30,repeat=True);sys.path.insert(0,'/cache/deps');import json,transformers,peft,accelerate,bitsandbytes;print(json.dumps({n:m.__version__ for n,m in [('transformers',transformers),('peft',peft),('accelerate',accelerate),('bitsandbytes',bitsandbytes)]}))"],env=env,capture_output=True,text=True,check=True,timeout=120)
 versions=json.loads(check.stdout.strip().splitlines()[-1]);print('DEPENDENCIES_VERIFIED',flush=True)
 checked={}
 for file in spec['files']:
  name=file['name'];dest=model/name;print('FETCHING '+name,flush=True)
  if Path(name).name!=name:raise ValueError('Unexpected model filename')
  def digest(p):
   h=hashlib.sha256()
   with p.open('rb') as f:
    for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
   return h.hexdigest()
  if not dest.exists() or digest(dest)!=file['sha256']:
   partial=dest.with_suffix(dest.suffix+'.partial')
   with urllib.request.urlopen(file['url'],timeout=90) as response,partial.open('wb') as out:
    while True:
     block=response.read(4*1024**2)
     if not block:break
     out.write(block)
   if digest(partial)!=file['sha256']:raise ValueError('Hash mismatch: '+name)
   partial.rename(dest)
  checked[name]=file['sha256'];print('VERIFIED '+name,flush=True)
 report={'status':'CPU_PREFETCH_COMPLETE','model_id':spec['model_id'],'revision':spec['revision'],'files':checked,'gpu_requested':0,'wall_seconds':time.monotonic()-start,'torch':torch.__version__,**versions}
 (root/'prefetch-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('KALI_PREFETCH_RESULT='+json.dumps(report),flush=True)
if __name__=='__main__':main(json.loads(sys.argv[1]))
