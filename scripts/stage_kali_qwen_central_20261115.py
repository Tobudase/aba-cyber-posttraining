"""CPU-only regional staging; source is read-only, only pinned runtime/fixed adapter."""
import datetime,json,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,cleanup,write
from kali_two_model_submit_20261115 import submit_pilot
from kali_qwen_gpu_placement_20261115 import eligible_nodes
from kali_qwen_aba_jobs_20261115 import DATA,CLAIM
DEST='miw113-kali-two-model-central-1115';NAME='miw113-qwen-central-stage-1115'
def run():
 audit=DATA/'central-stage-audit.json'
 if audit.exists():return
 p={'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':DEST,'labels':{'app.kubernetes.io/managed-by':'miw113'}},'spec':{'accessModes':['ReadWriteOnce'],'storageClassName':'rook-ceph-block-central','resources':{'requests':{'storage':'8Gi'}}}}
 r=k('get','pvc',DEST,'-o','json',check=False)
 if r.returncode:
  assert 'NotFound' in r.stderr;k('create','--dry-run=server','-f','-',body=p);k('create','-f','-',body=p)
 else:
  old=json.loads(r.stdout);assert old['spec']['storageClassName']=='rook-ceph-block-central' and old['metadata']['labels']['app.kubernetes.io/managed-by']=='miw113'
 runtime=json.loads((ROOT/'data/benchkit/kali-two-model-sft-2026-11-15/model-protocols.json').read_text())['qwen']['runtime_archive_sha256'];receipt=json.loads((ROOT/'data/benchkit/kali-two-model-sft-2026-11-15/receipt.json').read_text())['models']['qwen']['checkpoints']['qwen_step256'];prefix='kali-two-model-sft-20261115/miw113-kali-two-model-sft-r3-1115/qwen_step256/adapter/'
 expected={'runtime-deps.tar':runtime,prefix+'adapter_model.safetensors':receipt['weights_sha256'],prefix+'adapter_config.json':receipt['config_sha256']}
 program="""import hashlib,json,shutil,time
from pathlib import Path
expected="""+repr(expected)+"""
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
checks={};started=time.monotonic()
for name,digest in expected.items():
 source=Path('/cache')/name;target=Path('/dest')/name;assert sha(source)==digest;target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():assert sha(target)==digest
 else:
  temporary=target.with_suffix(target.suffix+'.partial');shutil.copyfile(source,temporary);assert sha(temporary)==digest;temporary.replace(target)
 checks[name]={'sha256':digest,'bytes':target.stat().st_size}
 print('REGIONAL_FILE_VERIFIED '+name,flush=True)
print('CENTRAL_STAGE_ARTIFACT='+json.dumps({'source_read_only':True,'GPU_count':0,'model_calls':0,'files':checks,'wall_seconds':time.monotonic()-started}),flush=True)
"""
 d=OUT/NAME
 if not d.exists():
  placement=json.loads((DATA/'placement-amendment-private.json').read_text());nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];hosts=eligible_nodes(nodes,placement['allowed_products'],'us-central');assert hosts
  print(json.dumps(submit_pilot(NAME,{'worker.py':program},{'cpu':'250m','memory':'512Mi','ephemeral-storage':'256Mi'},cache=True,readonly=True,cache_claim=CLAIM,cache_region='us-central',node_names=hosts,extra_volumes=[{'name':'dest','persistentVolumeClaim':{'claimName':DEST}}],extra_mounts=[{'name':'dest','mountPath':'/dest'}],runtime=1800)),flush=True)
 if not (d/'host.json').exists():
  from kali_qwen_submission_recovery_20261115 import recover
  recover(NAME)
 deadline=time.monotonic()+2100;last=None
 while time.monotonic()<deadline:
  state=poll(NAME)
  if state['status']!=last:print('CENTRAL_STAGE '+state['status'],flush=True);last=state['status']
  if state['status']=='FAILED':raise RuntimeError('Central CPU staging failed; preserve source and logs')
  if state['status']=='SUCCEEDED':
   log=(d/'worker.log').read_text();found=[json.loads(x.split('=',1)[1]) for x in log.splitlines() if x.startswith('CENTRAL_STAGE_ARTIFACT=')];assert len(found)==1 and set(found[0]['files'])==set(expected);result=found[0];result.update(claim=DEST,region='us-central',source_claim=CLAIM);write(audit,result);cleanup(NAME);return
  time.sleep(10)
 raise TimeoutError('CPU staging bounded window')
if __name__=='__main__':run()
