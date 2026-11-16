"""Recover both real candidate adapters with CPU-only bounded cache access."""
import hashlib,json,subprocess,tarfile,time
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,write,BASE
from kali_two_model_submit_20261115 import submit_pilot
from kali_qwen_aba_jobs_20261115 import DATA,sha
NAME='miw113-qwen-aba-export-1115'
def run():
 assert json.loads((DATA/'native-controller/host-private.json').read_text())['native_completed']
 if (DATA/'export-audit.json').exists():return
 placement=json.loads((DATA/'placement-amendment-private.json').read_text());d=OUT/NAME
 if not d.exists():print(json.dumps(submit_pilot(NAME,{'worker.py':"import time;print('EXPORT_READY',flush=True);time.sleep(600)\n"},{'cpu':'250m','memory':'256Mi','ephemeral-storage':'128Mi'},cache=True,readonly=True,cache_claim=placement['claim'],cache_region=placement['region'],runtime=660)),flush=True)
 deadline=time.monotonic()+1000
 while time.monotonic()<deadline:
  state=poll(NAME);log=(d/'worker.log').read_text() if (d/'worker.log').exists() else ''
  if state['status']=='Running' and 'EXPORT_READY' in log:break
  if state['status']=='FAILED':raise RuntimeError('Adapter exporter failed')
  time.sleep(10)
 else:raise TimeoutError('Bounded CPU exporter queue wait')
 digests={}
 try:
  for cid in ['A1','A2']:
   receipt=json.loads((DATA/cid/'receipt.json').read_text());remote='/cache/kali-qwen-aba-20261115/'+cid+'/adapters.tar.gz';archive=DATA/cid/'adapters-private.tar.gz'
   if not archive.exists():
    temp=archive.with_suffix('.partial')
    with temp.open('wb') as f:r=subprocess.run(BASE+['exec','job/'+NAME,'--','cat',remote],stdout=f,stderr=subprocess.PIPE,timeout=180)
    assert r.returncode==0,r.stderr.decode()[-300:];assert sha(temp)==receipt['archive_sha256'];temp.replace(archive)
   assert sha(archive)==receipt['archive_sha256'];dest=DATA/cid/'adapters-private';dest.mkdir(exist_ok=True)
   with tarfile.open(archive) as tar:
    assert all((m.isfile() or m.isdir()) and (dest/m.name).resolve().is_relative_to(dest.resolve()) for m in tar.getmembers());tar.extractall(dest,filter='data')
   cp=receipt['models']['qwen']['checkpoints']['qwen_step128'];adapter=dest/'qwen_step128/adapter';assert sha(adapter/'adapter_model.safetensors')==cp['weights_sha256'] and sha(adapter/'adapter_config.json')==cp['config_sha256'];digests[cid]={'archive_sha256':sha(archive),'weights_sha256':cp['weights_sha256'],'config_sha256':cp['config_sha256']}
 finally:
  host=json.loads((d/'host.json').read_text());actual=json.loads(k('get','job',NAME,'-o','json').stdout);assert actual['metadata']['uid']==host['uid'];k('delete','job',NAME,'--wait=true','--timeout=30s');k('delete','configmap',NAME,'--wait=true','--timeout=20s')
 assert len(digests)==2;write(DATA/'export-audit.json',{'two_actual_adapters_exported_hash_verified':True,'digests':digests,'CPU_exporter_deleted':True,'new_optimizer_steps':0,'GPU_requested':0})
if __name__=='__main__':run()
