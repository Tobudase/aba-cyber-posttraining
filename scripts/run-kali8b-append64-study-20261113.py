#!/usr/bin/env python3
"""Separate, pre-frozen append-vs-replay diagnostic. Never queries final64.
Four operator-controlled SFT arms, not a new native ABA search.
"""
import base64,copy,datetime,gzip,hashlib,json,os,struct,subprocess,sys,tarfile,time
from pathlib import Path
from kali8b_study_jobs import k as cluster_call,placement_pool,TransientClusterError
from kali8b_study_grade import score_arm
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12'
S=ROOT/'data/benchkit/kali-8b-append64-study-2026-11-13'
ARMS={'A15':('replay',42),'A16':('append',42),'A17':('replay',43),'A18':('append',43)}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def k(*args,**kwargs):
 # Retry bounded read-only calls; never blindly repeat a create/delete mutation.
 for attempt in range(6):
  try:return cluster_call(*args,**kwargs)
  except (TransientClusterError,subprocess.TimeoutExpired):
   if not args or args[0] not in {'get','logs'} or attempt==5:raise
   time.sleep(5)
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def prepare():
 assert not S.exists(),'Do not overwrite this study'
 oldworker=ROOT/'scripts/run-kali-8b-verified64-worker-20261112.py';oldrecipe=ROOT/'scripts/kali_verified64_sft_recipe.py'
 assert sha(oldworker)=='2e21c53194545f458a068584bd799e6f9319ca8cf3f862956411944489fd4fae'
 assert sha(oldrecipe)=='4411dddf01f2cbc0449889c811fbf39be7404fd4facfdf823d0bf8c3a955f085'
 # New bounded recipe supports exactly this new study's row/step counts.
 recipe=oldrecipe.read_text().replace("c['max_optimizer_steps']>768","c['max_optimizer_steps']>797").replace('{(733,0),(669,64)}','{(797,0),(733,64)}')
 worker=oldworker.read_text().replace('kali_verified64_sft_recipe','kali_append64_sft_recipe').replace('/cache/kali-8b-verified64-study','/cache/kali-8b-append64-study')
 S.mkdir();(S/'worker.py').write_text(worker);(S/'kali_append64_sft_recipe.py').write_text(recipe)
 original=json.loads(gzip.decompress((OLD/'publisher-payload-private.json.gz').read_bytes()))
 mixed=json.loads(gzip.decompress((OLD/'mixed-payload-private.json.gz').read_bytes()))
 rows=original['train_rows'];assert len(rows)==733
 byid={r['id']:r for r in mixed['train_rows']};replacement=read(OLD/'replacement-map-private.json');assert len(replacement)==64
 added=[copy.deepcopy(byid[r['new_id']]) for r in replacement]
 replay=[]
 for i,r in enumerate(replacement):
  row=copy.deepcopy(rows[r['index']]);assert row['id']==r['old_id'] and row['target_tokens']==added[i]['target_tokens']
  row['replay_source_id']=row['id'];row['id']='append64-replay-'+str(i)+'-'+row['id'];replay.append(row)
 assert rows==original['train_rows'] and len({r['id'] for r in rows+added})==797
 protected={r['id'] for sec in ['dev1','dev2','anchors'] for r in original[sec]}
 protected|={r['id'] for r in json.loads(gzip.decompress((ROOT/'data/benchkit/kali-redsage-aba-final64-2026-11-10/inputs-private.json.gz').read_bytes()))['holdout']}
 assert not protected & {r.get('replay_source_id',r['id']) for r in rows+added+replay}
 tokenbudget=sum(r['target_tokens'] for r in rows+added);assert tokenbudget==sum(r['target_tokens'] for r in rows+replay)
 import importlib.util
 spec=importlib.util.spec_from_file_location('append_recipe',S/'kali_append64_sft_recipe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 frozen={}
 for cid,(kind,seed) in ARMS.items():
  d=S/cid;d.mkdir();payload=copy.deepcopy(original);payload['train_rows']=rows+(replay if kind=='replay' else added);raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();(d/'payload.json.gz').write_bytes(gzip.compress(raw,mtime=0))
  p=read(OLD/'P11/protocol-private.json');p.update(candidate_id=cid,run_kind='operator_append64_diagnostic',candidate_recipe={'data':kind,'seed':seed,'lr':1e-5},training_rows=797,initialization_seed=seed,payload_sha256=hashlib.sha256(raw).hexdigest(),payload_gzip_sha256=sha(d/'payload.json.gz'),worker_sha256=sha(S/'worker.py'),recipe_sha256=sha(S/'kali_append64_sft_recipe.py'),quality_counts={'publisher_verified':797 if kind=='replay' else 733,'source_silver':0 if kind=='replay' else 64},scope='Separate append vs replay diagnostic on exposed DEV128. No official TEST or final64 queries. Not native ABA.',prepared_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  p['optimizer'].update(max_optimizer_steps=797,seed=seed);m.validate_recipe(p['optimizer'],payload['train_rows']);write(d/'protocol.json',p);frozen[cid]=sha(d/'protocol.json')
 lock={'status':'FROZEN_BEFORE_ANY_NEW_ARM_OUTPUT','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'arms':ARMS,'protocol_sha256':frozen,'worker_sha256':sha(S/'worker.py'),'recipe_sha256':sha(S/'kali_append64_sft_recipe.py'),'parent_worker_sha256':sha(oldworker),'parent_recipe_sha256':sha(oldrecipe),'training_rows_and_updates':797,'supervised_tokens_per_arm':tokenbudget,'original733_preserved':True,'replay_rows_are_duplicates_not_novel':True,'matched_append_target_lengths':True,'seeds':[42,43],'learning_rate':1e-5,'GPU_parallel_limit':1,'placement':placement_pool(),'decision':'Diagnostic contrasts append-minus-replay per seed, report all arms and retention failures. No model promotion, no candidate selection from final64.','data_quality':'64 AI authored locally behavior verified silver;32 related families;4tools;not expertgold.','DEV128_exposed':True,'official_TEST_rows':0,'final64_queries_planned':0,'expected_completed_worker_hours_upper_bound':8,'queue_deadline_per_job':21600,'pod_runtime_per_job':7200,'total_wall_deadline':100800,'independent_confirmation':'Not available in this study. Requires a separate new frozen set before any independent improvement claim.'}
 write(S/'freeze.json',lock);print(json.dumps(lock),flush=True)
def name(cid):return 'miw113-kali8b-append64-'+cid.lower()
def objects(cid):
 p=read(S/cid/'protocol.json');pool=read(S/'freeze.json')['placement'];n=name(cid);labels={'app.kubernetes.io/managed-by':'miw113','app.kubernetes.io/part-of':'kali8b-append64-study'}
 cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':n,'labels':labels},'data':{'worker.py':(S/'worker.py').read_text(),'kali_append64_sft_recipe.py':(S/'kali_append64_sft_recipe.py').read_text(),'protocol.json':json.dumps(p,indent=2)+'\n','control-base-reference.json':json.dumps({r['id']:r['response'] for r in read(OLD/'P11/run/base-predictions-private.json')})}}
 sec={'apiVersion':'v1','kind':'Secret','metadata':{'name':n+'-input','labels':labels},'data':{'payload.json.gz':base64.b64encode((S/cid/'payload.json.gz').read_bytes()).decode()}}
 resources={'cpu':'2','memory':'12Gi','ephemeral-storage':'24Gi','nvidia.com/a100':'1'}
 expr=[{'key':'kubernetes.io/hostname','operator':'In','values':pool['allowed_hostnames']},{'key':'nvidia.com/gpu.product','operator':'In','values':[pool['GPU_product']]},{'key':'nvidia.com/cuda.driver-version.full','operator':'In','values':pool['allowed_driver_full']}]
 pod={'restartPolicy':'Never','activeDeadlineSeconds':7200,'automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/arch':'amd64'},'affinity':{'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':expr}]},'preferredDuringSchedulingIgnoredDuringExecution':[{'weight':100,'preference':{'matchExpressions':[{'key':'topology.kubernetes.io/region','operator':'In','values':['us-west']}]}}]}},'containers':[{'name':'train','image':read(ROOT/'configs/gpu-runtime-image.lock.json')['image'],'command':['/bin/bash','-lc','set -euo pipefail; mkdir -p /cache/kali-8b-append64-study/logs; python -u /input/worker.py 2>&1 | tee /cache/kali-8b-append64-study/logs/'+cid+'.log'],'env':[{'name':'HF_HUB_OFFLINE','value':'1'},{'name':'OMP_NUM_THREADS','value':'2'},{'name':'CUBLAS_WORKSPACE_CONFIG','value':':4096:8'},{'name':'PYTHONDONTWRITEBYTECODE','value':'1'}],'resources':{'requests':resources,'limits':resources},'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True},{'name':'cache','mountPath':'/cache'},{'name':'scratch','mountPath':'/scratch'}]}],'volumes':[{'name':'input','projected':{'defaultMode':256,'sources':[{'configMap':{'name':n}},{'secret':{'name':n+'-input'}}]}},{'name':'cache','persistentVolumeClaim':{'claimName':'miw113-kali-cuda-cache'}},{'name':'scratch','emptyDir':{'sizeLimit':'24Gi'}}]}
 job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':n,'labels':labels},'spec':{'activeDeadlineSeconds':21600,'backoffLimit':0,'ttlSecondsAfterFinished':3600,'template':{'metadata':{'labels':labels},'spec':pod}}}
 return [cm,sec,job]
def export(cid,node):
 # Reuse reviewed interactive CPU exporter in a separate module namespace.
 import importlib.util
 spec=importlib.util.spec_from_file_location('append_jobs',ROOT/'scripts/kali8b_study_jobs.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.S=S;m.CIDS=set(ARMS);m.paths=lambda c:(S/c,S/c/'run',name(c))
 # Exporter reads a cache path; create this separate helper with only that path changed.
 source=(ROOT/'scripts/kali8b_study_jobs.py').read_text().replace('/cache/kali-8b-verified64-study/','/cache/kali-8b-append64-study/')
 ns=dict(m.__dict__);exec(compile(source,str(ROOT/'scripts/kali8b_study_jobs.py'),'exec'),ns);ns['S']=S;ns['CIDS']=set(ARMS);ns['paths']=m.paths
 return ns['export_adapter'](cid,node)
def run_arm(cid):
 lock=read(S/'freeze.json');d=S/cid;assert sha(d/'protocol.json')==lock['protocol_sha256'][cid] and sha(S/'worker.py')==lock['worker_sha256'] and sha(S/'kali_append64_sft_recipe.py')==lock['recipe_sha256']
 run=d/'run';assert not run.exists(),'No automatic retraining or overwriting attempted arms';run.mkdir();record={'status':'SUBMITTING','candidate_id':cid,'cleanup_errors':[],'official_TEST_rows':0};made=[]
 try:
  active=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items'];assert not any(q.get('status',{}).get('phase') in ['Pending','Running'] and any(key.startswith('nvidia.com/') for c in q['spec']['containers'] for key in c.get('resources',{}).get('requests',{})) for q in active),'Another owned GPU job already active'
  for obj in objects(cid):k('create','--dry-run=server','-f','-',payload=json.dumps(obj))
  for obj in objects(cid):k('create','-f','-',payload=json.dumps(obj));made.append((obj['kind'].lower(),obj['metadata']['name']))
  job=json.loads(k('get','job',name(cid),'-o','json').stdout);record.update(status='QUEUED',job_uid=job['metadata']['uid'],submitted_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());write(run/'host-private.json',record)
  until=time.monotonic()+22200;last=None
  while time.monotonic()<until:
   job=json.loads(k('get','job',name(cid),'-o','json').stdout);assert job['metadata']['uid']==record['job_uid']
   pods=json.loads(k('get','pods','-l','job-name='+name(cid),'-o','json').stdout)['items'];pod=pods[0] if pods else None;phase=pod.get('status',{}).get('phase','QUEUED') if pod else 'QUEUED'
   if phase!=last:print(cid+' '+phase,flush=True);last=phase
   if pod and pod['spec'].get('nodeName'):record.update(node_name=pod['spec']['nodeName'],resources=pod['spec']['containers'][0]['resources'])
   if job.get('status',{}).get('succeeded') or job.get('status',{}).get('failed'):break
   time.sleep(30)
  logs=k('logs','job/'+name(cid),check=False).stdout;(run/'worker-log-private.txt').write_text(logs);assert job.get('status',{}).get('succeeded'),'Job did not succeed; preserve attempt, stop study'
  def marker(key):
   values=[x.split('=',1)[1] for x in logs.splitlines() if x.startswith(key+'=')];assert len(values)==1,key;return values[0]
  receipt=json.loads(marker('ABA_CANDIDATE_RECEIPT'));assert receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==797 and receipt['supervised_token_presentations']==lock['supervised_tokens_per_arm'] and receipt['worker_sha256']==lock['worker_sha256'] and receipt['protocol_sha256']==lock['protocol_sha256'][cid] and receipt['adapter_reload_max_logit_delta']<=1e-4
  write(run/'receipt-private.json',receipt)
  for key,out in [('ABA_BASE_PREDICTIONS','base-predictions-private.json'),('ABA_CANDIDATE_PREDICTIONS','candidate-predictions-private.json')]:write(run/out,json.loads(gzip.decompress(base64.b64decode(marker(key),validate=True))))
  record['status']='COMPUTE_COLLECTED'
 except BaseException as e:record.update(status='FAILED',error=type(e).__name__+': '+str(e)[:400]);raise
 finally:
  for kind,n in reversed(made):
   q=k('delete',kind,n,'--ignore-not-found=true','--wait=true','--timeout=60s',check=False)
   if q.returncode:record['cleanup_errors'].append(kind+':'+q.stderr[-200:])
  write(run/'host-private.json',record)
 export(cid,record['node_name']);score_arm(cid,run);record['status']='COLLECTED';write(run/'host-private.json',record);print(cid+' COLLECTED',flush=True)
def main():
 if '--prepare' in sys.argv:prepare();return
 assert S.exists()
 if '--dry-run' in sys.argv:
  for cid in ARMS:
   for obj in objects(cid):k('create','--dry-run=server','-f','-',payload=json.dumps(obj))
  print('ALL_FOUR_SERVER_DRY_RUNS_PASS');return
 host={'status':'RUNNING','arms':list(ARMS),'official_TEST_rows':0,'final64_queries':0};write(S/'host-private.json',host)
 if __import__('shutil').which('caffeinate'):subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())])
 try:
  for cid in ARMS:run_arm(cid)
  host['status']='COMPLETE';write(S/'host-private.json',host)
 except BaseException as e:host.update(status='FAILED',error=str(e)[:300]);write(S/'host-private.json',host);raise
if __name__=='__main__':main()
