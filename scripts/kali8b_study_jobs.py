"""One-GPU bounded jobs and durable private adapter collection for frozen study."""
import base64,datetime,gzip,hashlib,json,struct,subprocess,tarfile,time
from pathlib import Path
from kali8b_study_grade import score_arm
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12';BASE=['kubectl','--context','nautilus','-n','ecepxie'];WORKER=ROOT/'scripts/run-kali-8b-verified64-worker-20261112.py';RECIPE=ROOT/'scripts/kali_verified64_sft_recipe.py';CIDS={'P11','P12','P13','P14'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class TransientClusterError(RuntimeError):pass
def k(*args,payload=None,check=True,timeout=90):
 p=subprocess.run(BASE+list(args),input=payload,text=True,capture_output=True,timeout=timeout)
 if check and p.returncode:
  transient=any(s in p.stderr.lower() for s in ['connection reset',"can't assign requested address",'connection refused','no route to host','unexpected eof','unable to connect','tls handshake timeout','i/o timeout','context deadline exceeded','serviceunavailable','temporarily unavailable'])
  raise (TransientClusterError if transient else RuntimeError)(p.stderr[-500:])
 return p

def paths(cid):
 assert cid in CIDS;d=S/cid;return d,d/'run','miw113-kali8b-v64-'+cid.lower()
def labels(cid):return {'app.kubernetes.io/managed-by':'miw113','app.kubernetes.io/part-of':'kali8b-verified64-study','study-arm':cid.lower()}
def protocol(cid):
 d,run,name=paths(cid);p=json.loads((d/'protocol-private.json').read_text());f=json.loads((S/'protocol-freeze-private.json').read_text());assert sha(d/'protocol-private.json')==f['protocol_sha256'][cid];assert sha(WORKER)==p['worker_sha256'] and sha(RECIPE)==p['recipe_sha256'];assert sha(d/'payload-private.json.gz')==p['payload_gzip_sha256'];return p

def placement_pool():
 p=S/'placement-amendment-private.json'
 if not p.exists():return None
 x=json.loads(p.read_text());assert x['status']=='FROZEN_RESOURCE_POOL_AMENDMENT_BEFORE_ABA_UPDATES' and x['GPU_product']=='NVIDIA-A100-SXM4-80GB' and x['driver_full']=='615.71.09' and len(x['allowed_hostnames'])==5
 return x

def objects(cid):
 d,run,name=paths(cid);p=protocol(cid);data={'worker.py':WORKER.read_text(),'kali_verified64_sft_recipe.py':RECIPE.read_text(),'protocol.json':(d/'protocol-private.json').read_text()}
 products={'NVIDIA L40':'NVIDIA-L40','NVIDIA L40S':'NVIDIA-L40S','NVIDIA A100-SXM4-80GB':'NVIDIA-A100-SXM4-80GB','NVIDIA A100 80GB PCIe':'NVIDIA-A100-80GB-PCIe','NVIDIA A100-PCIE-40GB':'NVIDIA-A100-PCIE-40GB'}
 expr=[{'key':'nvidia.com/gpu.product','operator':'In','values':[products[v] for v in p['allowed_GPU_models']]},{'key':'topology.kubernetes.io/region','operator':'In','values':p.get('hardware_regions',['us-west'])}]
 if cid!='P11':
  control=S/'P11/run';c=json.loads((control/'host-private.json').read_text());assert c['status']=='COLLECTED';h=json.loads((S/'hardware-lock-private.json').read_text());pool=placement_pool() if cid in {'P13','P14'} else None
  if pool:
   expr[0]['values']=[pool['GPU_product']];expr.append({'key':'kubernetes.io/hostname','operator':'In','values':pool['allowed_hostnames']});expr.append({'key':'nvidia.com/cuda.driver-version.full','operator':'In','values':[pool['driver_full']]})
  else:expr.append({'key':'kubernetes.io/hostname','operator':'In','values':[h['hostname_label']]})
  data['control-base-reference.json']=json.dumps({r['id']:r['response'] for r in json.loads((control/'base-predictions-private.json').read_text())})
 cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'labels':labels(cid)},'data':data}
 secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':name+'-input','labels':labels(cid)},'type':'Opaque','data':{'payload.json.gz':base64.b64encode((d/'payload-private.json.gz').read_bytes()).decode()}}
 pod={'restartPolicy':'Never','activeDeadlineSeconds':p['pod_runtime_seconds'],'automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/arch':'amd64'},'affinity':{'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':expr}]}}},'containers':[{'name':'train','image':json.loads((ROOT/'configs/gpu-runtime-image.lock.json').read_text())['image'],'command':['/bin/bash','-lc','set -euo pipefail; mkdir -p /cache/kali-8b-verified64-study/logs; python -u /input/worker.py 2>&1 | tee /cache/kali-8b-verified64-study/logs/'+cid.lower()+'.log'],'env':[{'name':'HF_HUB_OFFLINE','value':'1'},{'name':'OMP_NUM_THREADS','value':'2'},{'name':'CUBLAS_WORKSPACE_CONFIG','value':':4096:8'},{'name':'PYTHONDONTWRITEBYTECODE','value':'1'}],'resources':{'requests':p['resource_request'],'limits':p['resource_request']},'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True},{'name':'cache','mountPath':'/cache'},{'name':'scratch','mountPath':'/scratch'}]}],'volumes':[{'name':'input','projected':{'defaultMode':256,'sources':[{'configMap':{'name':name}},{'secret':{'name':name+'-input'}}]}},{'name':'cache','persistentVolumeClaim':{'claimName':'miw113-kali-cuda-cache'}},{'name':'scratch','emptyDir':{'sizeLimit':'24Gi'}}]}
 job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'labels':labels(cid)},'spec':{'activeDeadlineSeconds':p['queue_deadline_seconds'],'backoffLimit':0,'ttlSecondsAfterFinished':p['result_ttl_seconds'],'template':{'metadata':{'labels':labels(cid)},'spec':pod}}}
 return cm,secret,job

def submit(cid,dry=False):
 assert not (S/'confirmation/query-freeze-private.json').exists(),'Confirmation is frozen: no further study training is permitted'
 d,run,name=paths(cid);cache=json.loads((ROOT/'docs/verification/kali-8b-cache-west-check-20261112-private.json').read_text());assert cache['result']['status']=='CACHE_READY' and not cache['cleanup_errors']
 objs=objects(cid)
 for obj in objs:k('create','--dry-run=server','-f','-',payload=json.dumps(obj))
 if dry:return {'status':'SERVER_DRY_RUN_PASS','candidate_id':cid,'GPU':1}
 assert not run.exists(),'Do not overwrite an attempted arm'
 active=json.loads(k('get','pods','-l','app.kubernetes.io/part-of=kali8b-verified64-study','-o','json').stdout)['items'];assert not any(p.get('status',{}).get('phase') in ['Pending','Running'] and p['spec']['containers'][0]['resources']['requests'].get('nvidia.com/gpu',p['spec']['containers'][0]['resources']['requests'].get('nvidia.com/a100',0)) for p in active)
 run.mkdir();record={'status':'SUBMITTING','candidate_id':cid,'submitted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_sha256':sha(d/'protocol-private.json'),'cleanup_errors':[],'GPU_count':1};created=[]
 try:
  for obj in objs:k('create','-f','-',payload=json.dumps(obj));created.append((obj['kind'].lower(),obj['metadata']['name']))
  actual=json.loads(k('get','job',name,'-o','json').stdout);record.update(status='QUEUED',job_uid=actual['metadata']['uid'])
  owner={'apiVersion':'batch/v1','kind':'Job','name':name,'uid':record['job_uid'],'controller':False,'blockOwnerDeletion':False}
  for kind,n in [('configmap',name),('secret',name+'-input')]:k('patch',kind,n,'--type=merge','-p',json.dumps({'metadata':{'ownerReferences':[owner]}}))
 except BaseException:
  record['status']='SUBMISSION_FAILED'
  for kind,n in reversed(created):k('delete',kind,n,'--ignore-not-found=true','--wait=true','--timeout=60s',check=False)
  raise
 finally:(run/'host-private.json').write_text(json.dumps(record,indent=2)+'\n')
 return {'status':record['status'],'candidate_id':cid,'GPU':1}

def delete_training(cid,record):
 d,run,name=paths(cid)
 for kind,n in [('job',name),('configmap',name),('secret',name+'-input')]:
  p=k('delete',kind,n,'--ignore-not-found=true','--wait=true','--timeout=60s',check=False)
  if p.returncode:record['cleanup_errors'].append(kind+':'+p.stderr[-200:])

def export_adapter(cid,node):
 d,run,name=paths(cid);export=name+'-export';res={'cpu':'1','memory':'256Mi','ephemeral-storage':'128Mi'}
 pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':export,'labels':labels(cid)},'spec':{'activeDeadlineSeconds':600,'restartPolicy':'Never','automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/hostname':node},'containers':[{'name':'export','image':json.loads((ROOT/'configs/gpu-runtime-image.lock.json').read_text())['image'],'command':['python','-c','import time;print("EXPORT_READY",flush=True);time.sleep(550)'],'resources':{'requests':res,'limits':res},'volumeMounts':[{'name':'cache','mountPath':'/cache','readOnly':True}]}],'volumes':[{'name':'cache','persistentVolumeClaim':{'claimName':'miw113-kali-cuda-cache','readOnly':True}}]}}
 # This is a short interactive CPU Pod (manual exec is allowed),never an idle
 # Job. GPU batch Jobs above still execute their computation and terminate.
 assert k('get','pod',export,check=False).returncode!=0
 try:
  k('create','-f','-',payload=json.dumps(pod));deadline=time.monotonic()+240;pod=None
  while time.monotonic()<deadline:
   response=k('get','pod',export,'-o','json',check=False);item=json.loads(response.stdout) if response.returncode==0 else None
   if item and item.get('status',{}).get('phase')=='Running' and any(s.get('ready') for s in item.get('status',{}).get('containerStatuses',[])):pod=item['metadata']['name'];break
   time.sleep(3)
  assert pod,'CPU adapter exporter unavailable'
  archive=run/'adapter-bundle-private.tar.gz'
  with archive.open('wb') as f:
   p=subprocess.run(BASE+['exec',pod,'--','tar','-C','/cache/kali-8b-verified64-study/'+cid,'-czf','-','adapter','receipt.json','training-receipt.json'],stdout=f,stderr=subprocess.PIPE,timeout=240)
  assert p.returncode==0,p.stderr[-300:]
  dest=run/'adapter-bundle-private';dest.mkdir(exist_ok=False)
  with tarfile.open(archive) as t:
   assert all((m.isfile() or m.isdir()) and (dest/m.name).resolve().is_relative_to(dest.resolve()) for m in t.getmembers());t.extractall(dest,filter='data')
  r=json.loads((run/'receipt-private.json').read_text());weights=dest/'adapter/adapter_model.safetensors';assert sha(weights)==r['adapter_sha256'];assert sha(dest/'adapter/adapter_config.json')==r['adapter_config_sha256']
  with weights.open('rb') as f:n=struct.unpack('<Q',f.read(8))[0];header=json.loads(f.read(n))
  tensor_keys=[k for k in header if k!='__metadata__'];assert len(tensor_keys)==144 and all('lora_' in k for k in tensor_keys)
  out={'status':'ADAPTER_EXPORTED_AND_HASH_VERIFIED','adapter_sha256':sha(weights),'tensor_count':144,'archive_sha256':sha(archive),'bytes':weights.stat().st_size};(run/'adapter-export-private.json').write_text(json.dumps(out,indent=2)+'\n');return out
 finally:k('delete','pod',export,'--ignore-not-found=true','--wait=true','--timeout=60s',check=False)

def check_once(cid):
 d,run,name=paths(cid);record=json.loads((run/'host-private.json').read_text())
 if record['status'] in ['COLLECTED','FAILED']:return True,record
 job=json.loads(k('get','job',name,'-o','json').stdout);assert job['metadata']['uid']==record['job_uid'];pods=json.loads(k('get','pods','-l','job-name='+name,'-o','json').stdout)['items'];pod=pods[0] if pods else None
 if pod and pod['spec'].get('nodeName'):
  record['node_name']=pod['spec']['nodeName']
  if cid=='P11' and not (S/'hardware-lock-private.json').exists():
   nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];n=next(n for n in nodes if n['metadata']['name']==record['node_name']);h={'hostname_label':n['metadata']['labels']['kubernetes.io/hostname'],'node_name':record['node_name'],'product':n['metadata']['labels']['nvidia.com/gpu.product']};(S/'hardware-lock-private.json').write_text(json.dumps(h,indent=2)+'\n')
 if not (job.get('status',{}).get('succeeded') or job.get('status',{}).get('failed')):
  record.update(status=pod.get('status',{}).get('phase','QUEUED') if pod else 'QUEUED',last_checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(run/'host-private.json').write_text(json.dumps(record,indent=2)+'\n');return False,record
 logs=k('logs','job/'+name,check=False).stdout;(run/'worker-log-private.txt').write_text(logs)
 try:
  assert job.get('status',{}).get('succeeded'),'GPU job did not succeed'
  def marker(prefix):
   x=[s.split('=',1)[1] for s in logs.splitlines() if s.startswith(prefix+'=')];assert len(x)==1,prefix;return x[0]
  receipt=json.loads(marker('ABA_CANDIDATE_RECEIPT'));p=protocol(cid);assert receipt['status']=='COMPLETE_8B_STUDY_ARM' and receipt['candidate_id']==cid
  assert receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==733 and receipt['changed_tensors']>0 and receipt['supervised_token_presentations']==17439
  assert receipt['deterministic_algorithms'] and receipt['adapter_reload_max_logit_delta']<=1e-4 and receipt['protocol_sha256']==sha(d/'protocol-private.json') and receipt['worker_sha256']==p['worker_sha256']
  for prefix,file in [('ABA_BASE_PREDICTIONS','base-predictions-private.json'),('ABA_CANDIDATE_PREDICTIONS','candidate-predictions-private.json'),('MATCHED_SFT733_BASE_ANCHORS','base-anchor-audit-private.json')]:
   rows=json.loads(gzip.decompress(base64.b64decode(marker(prefix),validate=True)));assert len(rows)==(4 if 'ANCHORS' in prefix else 128);(run/file).write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
  if cid!='P11' and p['initialization_seed']==42:
   c=json.loads((S/'P11/run/receipt-private.json').read_text());assert c['initial_lora_sha256']==receipt['initial_lora_sha256'],'Matched initialization changed'
  (run/'receipt-private.json').write_text(json.dumps(receipt,indent=2)+'\n');record['status']='TRAINING_AND_INFERENCE_COLLECTED'
 except BaseException as e:record.update(status='FAILED',error_type=type(e).__name__,error=str(e)[:300])
 finally:delete_training(cid,record);(run/'host-private.json').write_text(json.dumps(record,indent=2)+'\n')
 if record['status']=='TRAINING_AND_INFERENCE_COLLECTED':
  try:
   export_adapter(cid,record['node_name']);score=score_arm(cid,run);record.update(status='COLLECTED',optimizer_steps=733,native_delta=score['native_delta'],passes_all_gates=score['passes_all_gates'])
  except BaseException as e:record.update(status='FAILED',error_type=type(e).__name__,error=str(e)[:300])
 (run/'host-private.json').write_text(json.dumps(record,indent=2)+'\n');return True,record

def watch(cid,seconds=28800):
 until=time.monotonic()+seconds;last=None
 while time.monotonic()<until:
  try:done,r=check_once(cid)
  except (TransientClusterError,subprocess.TimeoutExpired):
   print(json.dumps({'candidate_id':cid,'status':'RECONNECTING_CLUSTER_WITHOUT_RESUBMITTING'}),flush=True);time.sleep(15);continue
  if r['status']!=last:print(json.dumps({'candidate_id':cid,'status':r['status'],'native_delta':r.get('native_delta'),'error':r.get('error')}),flush=True);last=r['status']
  if done:return r
  time.sleep(30)
 raise TimeoutError('Bounded study watcher expired')
