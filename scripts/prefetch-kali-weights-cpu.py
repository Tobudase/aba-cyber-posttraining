"""Resumable CPU-only checkpoint preparation, streaming SHA256 and explicit sizes."""
import hashlib,json,sys,time,urllib.request
from pathlib import Path

def main(spec):
 root=Path('/cache/model');root.mkdir(exist_ok=True);start=time.monotonic();verified={}
 def digest(path):
  h=hashlib.sha256();total=0
  with path.open('rb') as f:
   for block in iter(lambda:f.read(4*1024**2),b''):
    total+=len(block);h.update(block)
    if total%(512*1024**2)==0:print('HASH_PROGRESS '+path.name+' '+str(total),flush=True)
  return h.hexdigest()
 for entry in spec['files']:
  name=entry['name'];dest=root/name;partial=root/(name+'.partial')
  if Path(name).name!=name:raise ValueError('Unexpected path')
  if not dest.exists() and partial.exists() and (not entry.get('bytes') or partial.stat().st_size==entry['bytes']):
   if digest(partial)==entry['sha256']:partial.rename(dest)
  if dest.exists() and digest(dest)==entry['sha256']:
   verified[name]=entry['sha256'];print('VERIFIED '+name,flush=True);continue
  for attempt in range(3):
   offset=partial.stat().st_size if partial.exists() else 0
   headers={'Range':f'bytes={offset}-'} if offset else {}
   try:
    with urllib.request.urlopen(urllib.request.Request(entry['url'],headers=headers),timeout=90) as response:
     append=offset>0 and response.status==206
     h=hashlib.sha256()
     if append:
      with partial.open('rb') as old:
       for block in iter(lambda:old.read(4*1024**2),b''):h.update(block)
     with partial.open('ab' if append else 'wb') as out:
      total=offset if append else 0
      while True:
       block=response.read(4*1024**2)
       if not block:break
       h.update(block);out.write(block);total+=len(block)
       if total%(512*1024**2)==0:print('DOWNLOAD_PROGRESS '+name+' '+str(total),flush=True)
    if h.hexdigest()!=entry['sha256'] or entry.get('bytes',total)!=total:raise ValueError('Checkpoint size/hash mismatch: '+name)
    partial.rename(dest);verified[name]=entry['sha256'];print('VERIFIED '+name,flush=True);break
   except Exception as exc:
    print('DOWNLOAD_RETRY '+name+' '+type(exc).__name__,flush=True)
    if attempt==2:raise
 report={'status':'CPU_PREFETCH_COMPLETE','model_id':spec['model_id'],'revision':spec['revision'],'files':verified,'gpu_requested':0,'wall_seconds':time.monotonic()-start,'dependency_scope':'Packages installed in earlierCPUstage; import and CUDA compatibility still checked in boundedGPUrun','weight_bytes':sum(e.get('bytes',0) for e in spec['files'] if e['name'].endswith('.safetensors'))}
 Path('/cache/prefetch-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('KALI_PREFETCH_RESULT='+json.dumps(report),flush=True)
if __name__=='__main__':main(json.loads(sys.argv[1]))
