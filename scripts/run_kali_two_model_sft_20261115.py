"""Bounded same-GPU two-model pilot orchestration and durable artifact recovery."""
import argparse,base64,datetime,gzip,hashlib,json,subprocess,tarfile,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,submit,poll,write,cleanup,BASE
from kali_two_model_submit_20261115 import submit_pilot
DATA=ROOT/'data/benchkit/kali-two-model-sft-2026-11-15'
NAME='miw113-kali-two-model-sft-r3-1115'
CLAIM='miw113-kali-two-model-cache-1115'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def launch():
 review=json.loads((OUT/'miw113-kali-preview-v6-review-1115/summary.json').read_text());assert review['status']=='PREVIEW_V6_UNIFORM_REVIEW_COMPLETE' and review['fixture_controls_all_passed'] and all(review['controls'].values())
 stage=json.loads((DATA/'dedicated-cache-stage-audit.json').read_text());assert stage['source_claim_read_only'] and stage['claim']==CLAIM
 protocol=json.loads((DATA/'protocol.json').read_text());raw=(DATA/'gpu-inputs.json.gz').read_bytes();assert sha(DATA/'gpu-inputs.json.gz')==protocol['inputs_gzip_sha256']
 worker=ROOT/'scripts/kali_two_model_sft_worker_20261115.py';modules={n:ROOT/'scripts'/n for n in ['kali_command_ngram_guard_20261115.py','kali_stable_objective_20261114.py','kali_exact_adapter_loading_20261115.py']}
 evaluation_names=['kali_functional_behavior_worker_v6_20261115.py','kali_hardlink_oracle_v6_20261115.py','kali_data_release_20261114.py','kali_functional_data_20261115.py','kali_functional_data_v2_20261115.py','kali_fit64_behavior_review_v5_20261115.py','kali-behavior-fixture-worker-v2-20261112.py','benchkit.py']
 cfg={'model_protocols':json.loads((DATA/'model-protocols.json').read_text()),'inputs_sha256':sha(DATA/'gpu-inputs.json.gz'),'worker_sha256':sha(worker),'module_sha256':{n:sha(p) for n,p in modules.items()},'evaluation_sha256':{n:sha(ROOT/'scripts'/n) for n in evaluation_names},'durable_output':'/cache/kali-two-model-sft-20261115/'+NAME,'protocol_sha256':sha(DATA/'protocol.json'),'oracle_v6_source_sha256':sha(ROOT/'scripts/kali_hardlink_oracle_v6_20261115.py'),'max_optimizer_steps_total':512,'max_model_generations':912}
 nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];allowed=set(cfg['model_protocols']['redsage']['allowed_GPU_models']);eligible=[]
 for n in nodes:
  labels=n['metadata'].get('labels',{});product=labels.get('nvidia.com/gpu.product','')
  # NVIDIA's scheduling labels replace spaces with dashes; A100's official
  # model names themselves also contain dashes in some driver generations.
  if product not in {a.replace(' ','-') for a in allowed}:continue
  if any(kind in product for kind in ['H100','H200','GH200']):continue
  if int(labels.get('nvidia.com/cuda.driver.major','0'))<570:continue
  if labels.get('topology.kubernetes.io/region')!='us-west' or n['spec'].get('unschedulable'):continue
  if any(t['effect'] in ['NoSchedule','NoExecute'] for t in n['spec'].get('taints',[])):continue
  if not any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']):continue
  if n['metadata']['name']=='nautilus-ext-gpu01.fullerton.edu':continue
  eligible.append({'node':n['metadata']['name'],'product':product})
 assert eligible;write(DATA/'eligible-nodes.json',eligible)
 write(DATA/'launch-freeze.json',{'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'config':cfg,'review_summary_sha256':sha(OUT/'miw113-kali-preview-v6-review-1115/summary.json'),'GPU_count':1,'max_pod_seconds':10800,'max_job_seconds_including_queue':12600,'ordinary_untainted_nodes_only':True})
 r=submit_pilot(NAME,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg,indent=2)+'\n',**{n:p.read_text() for n,p in modules.items()}},{'cpu':'2','memory':'16Gi','ephemeral-storage':'24Gi','nvidia.com/gpu':'1'},cache=True,readonly=False,cache_claim=CLAIM,gpu_products=sorted({n['product'] for n in eligible}),node_names=[n['node'] for n in eligible],binary_files={'inputs.json.gz':raw},runtime=10800)
 write(DATA/'status.json',{'status':'SUBMITTED','job':NAME,'uid':r['uid'],'model_outputs':False});return r

def collect():
 d=OUT/NAME;host=json.loads((d/'host.json').read_text());assert host['status']=='SUCCEEDED';log=(d/'worker.log').read_text();assert 'TWO_MODEL_COMPLETE' in log
 items=[x.split('=',1)[1] for x in log.splitlines() if x.startswith('TWO_MODEL_ARTIFACT=')];assert len(items)==1
 artifact=json.loads(gzip.decompress(base64.b64decode(items[0],validate=True)));r=artifact['receipt'];cfg=json.loads(json.loads((d/'objects.json').read_text())[0]['data']['config.json'])
 assert r['status']=='TWO_MODEL_SFT_COMPUTE_COMPLETE' and r['worker_sha256']==cfg['worker_sha256'] and r['inputs_sha256']==cfg['inputs_sha256']
 for label in ['redsage','qwen']:
  x=r['models'][label];assert x['optimizer_steps']==x['nonzero_gradient_steps']==256 and x['reload_complete_responses_identical'] and x['initial_zero_B_probe_difference']==0
 assert r['models']['redsage']['order_sha256']==r['models']['qwen']['order_sha256']
 write(DATA/'receipt.json',r);write(DATA/'predictions-private.json',artifact['predictions']);write(DATA/'collection-audit.json',{'job_uid':host['uid'],'log_sha256':sha(d/'worker.log'),'config_sha256':r['config_sha256'],'expected_actual_updates':512})
 cleanup(NAME);write(DATA/'status.json',{'status':'COMPUTE_COLLECTED_GPU_CLEANED','job':NAME,'optimizer_steps':512,'official_TEST_queries':0});return {'collected':True,'optimizer_steps':512}

def export():
 receipt=json.loads((DATA/'receipt.json').read_text());name=NAME+'-export';archive=DATA/'adapters-private.tar.gz'
 if archive.exists():assert sha(archive)==receipt['archive_sha256'];return
 if not (OUT/name).exists():submit(name,{'worker.py':"import time;print('EXPORT_READY',flush=True);time.sleep(600)\n"},{'cpu':'250m','memory':'256Mi','ephemeral-storage':'128Mi'},cache=True,readonly=True,cache_claim=CLAIM,runtime=660)
 deadline=time.monotonic()+900
 while time.monotonic()<deadline:
  state=poll(name)
  if state['status']=='Running' and 'EXPORT_READY' in (OUT/name/'worker.log').read_text():break
  if state['status']=='FAILED':raise RuntimeError('CPU export failed')
  time.sleep(10)
 else:raise TimeoutError('CPU export queue bounded wait exceeded')
 remote='/cache/kali-two-model-sft-20261115/'+NAME+'/adapters.tar.gz';tmp=archive.with_suffix('.partial')
 with tmp.open('wb') as f:r=subprocess.run(BASE+['exec','job/'+name,'--','cat',remote],stdout=f,stderr=subprocess.PIPE,timeout=180)
 assert r.returncode==0,r.stderr.decode()[-500:];assert sha(tmp)==receipt['archive_sha256'];tmp.replace(archive)
 dest=DATA/'adapters-private';dest.mkdir(exist_ok=True)
 with tarfile.open(archive) as tar:
  assert all((m.isfile() or m.isdir()) and (dest/m.name).resolve().is_relative_to(dest.resolve()) for m in tar.getmembers());tar.extractall(dest,filter='data')
 for m in receipt['models'].values():
  for cp in m['checkpoints'].values():
   p=dest/cp['adapter_relative_path'];assert sha(p/'adapter_model.safetensors')==cp['weights_sha256'] and sha(p/'adapter_config.json')==cp['config_sha256']
 # End owned CPU exporter early after verified bytes; no model compute occurs.
 k('delete','job',name,'--wait=true','--timeout=30s');k('delete','configmap',name,'--wait=true','--timeout=20s')
 write(DATA/'export-audit.json',{'all_four_adapter_hashes_verified':True,'archive_sha256':sha(archive),'CPU_exporter_deleted':True,'extra_optimizer_steps':0});return {'weights_exported':True}

def run():
 if not (OUT/NAME).exists():
  # One other independent one-GPU experiment may coexist after quota review.
  # Never cancel, migrate or modify another conversation's work.
  deadline=time.monotonic()+7200
  while True:
   pods=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items'];active=[p['metadata']['name'] for p in pods if p['status'].get('phase') in ['Pending','Running'] and any(any(n.startswith('nvidia.com/') for n in c.get('resources',{}).get('requests',{})) for c in p['spec']['containers'])]
   existing=sum(int(v) for p in pods if p['status'].get('phase') in ['Pending','Running'] for c in p['spec']['containers'] for key,v in c.get('resources',{}).get('requests',{}).items() if key.startswith('nvidia.com/'))
   if existing<=1:break
   print('WAIT_EXISTING_OWNED_GPU '+json.dumps(active),flush=True)
   assert time.monotonic()<deadline,'Existing authorized GPU task still active; preserve it and resume this study later'
   time.sleep(45)
  print('SUBMITTED '+json.dumps(launch()),flush=True)
 deadline=time.monotonic()+13000;last=None
 while time.monotonic()<deadline:
  state=poll(NAME);log=(OUT/NAME/'worker.log').read_text() if (OUT/NAME/'worker.log').exists() else ''
  lines=[x for x in log.splitlines() if x.startswith(('TWO_MODEL_STAGED ','TWO_MODEL_INFER ','TWO_MODEL_TRAIN ','TWO_MODEL_ARM_COMPLETE ','TWO_MODEL_COMPLETE'))];current=(state['status'],lines[-1] if lines else 'queue/setup')
  if current!=last:print(json.dumps({'status':current[0],'latest':current[1],'node':state.get('node')}),flush=True);last=current
  if state['status']=='SUCCEEDED':
   print(json.dumps(collect()),flush=True);print(json.dumps(export()),flush=True)
   subprocess.run([__import__('sys').executable,str(ROOT/'scripts/score_kali_two_model_sft_20261115.py'),'all'],check=True)
   env=__import__('os').environ.copy();env['MPLCONFIGDIR']=str(ROOT/'.tools/matplotlib-cache')
   subprocess.run([str(ROOT/'.tools/results-plot-venv/bin/python'),str(ROOT/'scripts/finalize_kali_two_model_sft_20261115.py')],check=True,env=env)
   print('TWO_MODEL_VERIFIED_REPORT_READY_FOR_PUBLICATION',flush=True)
   return
  if state['status']=='FAILED':
   write(DATA/'status.json',{'status':'FAILED_PRESERVED','job':NAME,'reason':'Inspect original logs and partial durable artifacts before any retry; never claim completion.'});raise RuntimeError('Two-model GPU worker failed')
  time.sleep(30)
 raise TimeoutError('Host wait bounded window elapsed; inspect Job deadline and preserve artifacts')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['run','launch','collect','export']);a=p.parse_args();print(json.dumps({'run':run,'launch':launch,'collect':collect,'export':export}[a.action](),default=str),flush=True)
