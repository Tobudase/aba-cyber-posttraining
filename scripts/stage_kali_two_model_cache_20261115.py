"""Copy pinned runtime deps into a dedicated small RWO volume, CPU only.

Source is mounted read-only on its already active node. No other experiment or
its files are modified. The new volume remains for verified model artifacts.
"""
import json,time,hashlib
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,write,cleanup
from kali_two_model_submit_20261115 import submit_pilot
NAME='miw113-kali-two-model-stage-1115'
CLAIM='miw113-kali-two-model-cache-1115'
DATA=ROOT/'data/benchkit/kali-two-model-sft-2026-11-15'
def main():
 expected=json.loads((DATA/'model-protocols.json').read_text())['redsage']['runtime_archive_sha256']
 pods=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
 owners=[p for p in pods if p['status'].get('phase')=='Running' and any(v.get('persistentVolumeClaim',{}).get('claimName')=='miw113-kali-cuda-cache' for v in p['spec']['volumes'])]
 assert owners and len({p['spec']['nodeName'] for p in owners})==1;node=owners[0]['spec']['nodeName']
 existing=k('get','pvc',CLAIM,'-o','name',check=False)
 if existing.returncode:
  assert 'NotFound' in existing.stderr
  pvc={'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':CLAIM,'labels':{'app.kubernetes.io/managed-by':'miw113','app.kubernetes.io/part-of':'kali-two-model-sft-20261115'}},'spec':{'accessModes':['ReadWriteOnce'],'storageClassName':'rook-ceph-block','resources':{'requests':{'storage':'8Gi'}}}}
  k('create','--dry-run=server','-f','-',body=pvc);k('create','-f','-',body=pvc);write(DATA/'dedicated-cache-pvc.json',pvc)
 program="""import hashlib,json,shutil
from pathlib import Path
expected=EXPECTED
source=Path('/cache/runtime-deps.tar');target=Path('/dest/runtime-deps.tar')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
assert sha(source)==expected
if not target.exists():
 tmp=target.with_suffix('.tmp')
 with source.open('rb') as src,tmp.open('wb') as dst:shutil.copyfileobj(src,dst,8*1024**2)
 assert sha(tmp)==expected;tmp.replace(target)
assert sha(target)==expected
print('DEDICATED_CACHE_READY '+json.dumps({'runtime_sha256':expected,'runtime_bytes':target.stat().st_size,'source_read_only':True,'GPU':0}),flush=True)
""".replace('EXPECTED',repr(expected))
 if not (OUT/NAME).exists():
  print(json.dumps(submit_pilot(NAME,{'worker.py':program},{'cpu':'250m','memory':'512Mi','ephemeral-storage':'128Mi'},cache=True,readonly=True,node_names=[node],runtime=900,extra_volumes=[{'name':'destination','persistentVolumeClaim':{'claimName':CLAIM}}],extra_mounts=[{'name':'destination','mountPath':'/dest'}])),flush=True)
 last=None
 for _ in range(120):
  state=poll(NAME)
  if state['status']!=last:print(json.dumps({'status':state['status'],'node':state.get('node')}),flush=True);last=state['status']
  if state['status']=='SUCCEEDED':
   log=(OUT/NAME/'worker.log').read_text();x=[json.loads(s.split(' ',1)[1]) for s in log.splitlines() if s.startswith('DEDICATED_CACHE_READY ')];assert len(x)==1 and x[0]['runtime_sha256']==expected
   write(DATA/'dedicated-cache-stage-audit.json',{'node':node,'claim':CLAIM,'source_claim_read_only':True,**x[0]});cleanup(NAME);print('STAGE_COMPLETE '+json.dumps(x[0]),flush=True);return
  if state['status']=='FAILED':raise RuntimeError('Dedicated cache stage failed; preserve source and diagnose')
  time.sleep(10)
 raise TimeoutError('CPU cache stage bounded wait expired')
if __name__=='__main__':main()
