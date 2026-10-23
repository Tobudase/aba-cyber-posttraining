#!/usr/bin/env python3
"""Controlled one-GPU worker. No agent-supplied commands, labels or recipes."""
import argparse,base64,hashlib,json,re,shutil,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from benchkit import ROOT,load_jsonl,load_manifest,score_predictions,write_json

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def verified_receipt(folder,p):
 r=json.loads((folder/'receipt.json').read_text());v=json.loads((folder/'verified.json').read_text())
 if r.get('status')!='COMPLETE' or r.get('protocol_sha256')!=sha(canonical(p)) or r.get('runner_sha256')!=p['runner_sha256'] or v.get('status')!='HOST_COLLECTION_VERIFIED' or not v.get('job_succeeded') or v.get('receipt_sha256')!=sha((folder/'receipt.json').read_bytes()):raise ValueError('Cached receipt is not independently host-verified')
 if r['phase']=='infer':
  if sha((folder/'predictions.jsonl').read_bytes())!=r['predictions_sha256'] or sha((folder/'scores.json').read_bytes())!=v.get('scores_sha256'):raise ValueError('Cached prediction/score bytes changed')
 return r
def frozen():
 p=json.loads((ROOT/'configs/kali-cuda-cycle-v1.protocol.json').read_text())
 manifest=ROOT/p['train_manifest'];assert sha(manifest.read_bytes())==p['train_manifest_sha256']
 _,train=load_manifest(manifest,'train')
 inputs={'train_rows':train,'inference_rows':json.loads((ROOT/'data/benchkit/kali-cuda-cycle-v1/inference-inputs.json').read_text())}
 assert sha((ROOT/'scripts/run-kali-cuda-cycle.py').read_bytes())==p['runner_sha256']
 for k in ['train_rows','inference_rows']:assert sha(canonical(inputs[k]))==p[k+'_sha256']
 return p,inputs

def kubectl(args,input=None,check=True,timeout=40):
 local=json.loads((ROOT/'configs/kali-cuda-jobs.local.json').read_text())
 return subprocess.run(['kubectl','--context',local['context'],'-n',local['namespace']]+args,input=input,capture_output=True,text=True,check=check,timeout=timeout)

def build(run,phase,local=None):
 if run not in ['E0','E1','E2'] or phase not in ['train','infer'] or (run=='E0' and phase=='train'):raise ValueError('Unapproved operation')
 p,inputs=frozen();phash=sha(canonical(p));name=f'miw113-kali-cv1-{run.lower()}-{phase}'
 labels={'app.kubernetes.io/part-of':'kali-cuda-cycle-v1','kali-protocol':phash[:16]}
 field='train_rows' if phase=='train' else 'inference_rows'
 payload={'protocol':p,'protocol_sha256':phash,'run_id':run,'phase':phase,field:inputs[field]}
 cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'labels':labels},'data':{'runner.py':(ROOT/'scripts/run-kali-cuda-cycle.py').read_text(),'payload.json':json.dumps(payload)}}
 local=local or json.loads((ROOT/'configs/kali-cuda-jobs.local.json').read_text())
 resources={'cpu':'2','memory':'12Gi','ephemeral-storage':'24Gi','nvidia.com/gpu':'1'}
 spec={'restartPolicy':'Never','automountServiceAccountToken':False,'nodeSelector':local['nodeSelector'],
   'containers':[{'name':'worker','image':p['image'],'command':['python','-u','/input/runner.py'],
     'resources':{'requests':resources,'limits':resources},
     'env':[{'name':k,'value':v} for k,v in {'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','HF_HUB_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'}.items()],
     'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True},{'name':'cache','mountPath':'/cache'},{'name':'scratch','mountPath':'/scratch'}]}],
   'volumes':[{'name':'input','configMap':{'name':name}},{'name':'cache','persistentVolumeClaim':{'claimName':local['PVC']}},{'name':'scratch','emptyDir':{'sizeLimit':'24Gi'}}]}
 job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'labels':labels},'spec':{'activeDeadlineSeconds':p['budget']['job_deadline_seconds'],'backoffLimit':0,'ttlSecondsAfterFinished':1800,'template':{'metadata':{'labels':labels},'spec':spec}}}
 return name,cm,job

def score(run,folder,predictions):
 p,_=frozen();result={}
 for name,ev in p['evaluation'].items():
  manifest=ROOT/ev['manifest'];assert sha(manifest.read_bytes())==ev['manifest_sha256']
  part=json.loads(manifest.read_text())['splits']['dev_search'];f=manifest.parent/part['file'];assert sha(f.read_bytes())==ev['file_sha256']
  rows=load_jsonl(f);pred=[r for r in predictions if r['set']==name]
  scored=score_predictions(rows,pred,'kali');write_json(folder/f'{name}-scores.json',scored)
  result[name]={'rows':len(rows),'correct':sum(x['strict_option_value_correct'] for x in scored['details']),'complete_XML_rows':sum(bool(re.search(r'<output>.*?</output>',x['response'],re.S)) for x in pred),'summary':scored['summary']}
 # Format metric comes from native scorer; XML check below uses actual native tags.
 write_json(folder/'scores.json',{'run_id':run,'protocol_sha256':sha(canonical(p)),'sets':result,'official_test_rows':0,'confirmation_rows':0,'scope':'Already exposed source-silver development only'})
 return result

def execute(run,phase):
 name,cm,job=build(run,phase);p,_=frozen();folder=ROOT/'docs/verification/kali-cuda-cycle-v1'/run/phase;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'receipt.json').exists():
  return verified_receipt(folder,p)
 if (folder/'lifecycle.json').exists():
  failure=folder/'failure.json'
  if not failure.is_file() or json.loads(failure.read_text()).get('GPU_allocated') is not False:raise ValueError('Previous allocation must be reviewed before retry')
  n=1
  while (folder/f'unscheduled-attempt{n}').exists():n+=1
  archive=folder/f'unscheduled-attempt{n}';archive.mkdir()
  for f in ['lifecycle.json','submission.json','failure.json']:
   if (folder/f).exists():shutil.move(str(folder/f),str(archive/f))
 if phase=='infer' and run!='E0':
  verified_receipt(folder.parent/'train',p)
 if run=='E2':
  verified_receipt(ROOT/'docs/verification/kali-cuda-cycle-v1/E0/infer',p)
 # Block parallel GPU jobs belonging to this study; do not alter others' jobs.
 existing=json.loads(kubectl(['get','jobs','-l','app.kubernetes.io/part-of=kali-cuda-cycle-v1','-o','json']).stdout)['items']
 if existing:raise ValueError('Existing cycle Job requires collection/cleanup first')
 submitted=False;cm_created=False;started=time.monotonic();pod=None;sample=[];jobdata=None;logs=''
 try:
  kubectl(['create','-f','-'],json.dumps(cm));cm_created=True
  kubectl(['create','-f','-'],json.dumps(job));submitted=True
  write_json(folder/'submission.json',{'submitted_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(canonical(p)),'run_id':run,'phase':phase,'GPU_count':1,'CPU':2,'RAM_GiB':12,'ephemeral_GiB':24,'deadline_seconds':1800,'GPU_model':p['GPU_model'],'runner_sha256':p['runner_sha256']})
  while time.monotonic()-started<2160:
   jobdata=json.loads(kubectl(['get','job',name,'-o','json']).stdout)
   pods=json.loads(kubectl(['get','pods','-l','job-name='+name,'-o','json']).stdout)['items']
   if pods:
    pod=pods[0];status=pod['status'];elapsed=round(time.monotonic()-started,1)
    sample.append({'elapsed_seconds':elapsed,'phase':status.get('phase'),'conditions':status.get('conditions',[]),'containers':[{k:v for k,v in c.items() if k in ['name','ready','restartCount','state']} for c in status.get('containerStatuses',[])]})
    if status.get('phase')=='Pending' and elapsed>360:raise TimeoutError('Bounded scheduler wait exceeded')
    latest=kubectl(['logs',pod['metadata']['name'],'--tail=1'],check=False).stdout.strip()
    print(json.dumps({'run':run,'phase':phase,'elapsed_seconds':elapsed,'pod':status.get('phase'),'progress':latest[:160] if not latest.startswith('KALI_CUDA_') else 'RESULT_SAVED'}),flush=True)
   if jobdata.get('status',{}).get('succeeded') or jobdata.get('status',{}).get('failed'):break
   time.sleep(15)
  else:raise TimeoutError('Host deadline exceeded')
  logs=kubectl(['logs',pod['metadata']['name']],check=False).stdout if pod else ''
  private=ROOT/'.tools'/f'{name}.log';private.write_text(logs)
  markers=[line.split('=',1)[1] for line in logs.splitlines() if line.startswith('KALI_CUDA_CYCLE_RESULT=')]
  if not markers:raise RuntimeError('No worker completion receipt; inspect private Job log')
  receipt=json.loads(markers[-1]);assert receipt['protocol_sha256']==sha(canonical(p)) and receipt['runner_sha256']==p['runner_sha256']
  write_json(folder/'receipt.json',receipt)
  if receipt['status']!='COMPLETE' or not jobdata.get('status',{}).get('succeeded'):raise RuntimeError('Worker failed; no success inferred')
  if phase=='infer':
   encoded=[line.split('=',1)[1] for line in logs.splitlines() if line.startswith('KALI_CUDA_PREDICTIONS_BASE64=')]
   data=base64.b64decode(encoded[-1],validate=True);assert sha(data)==receipt['predictions_sha256']
   (folder/'predictions.jsonl').write_bytes(data);pred=[json.loads(x) for x in data.splitlines()];score(run,folder,pred)
  write_json(folder/'verified.json',{'status':'HOST_COLLECTION_VERIFIED','protocol_sha256':sha(canonical(p)),'receipt_sha256':sha((folder/'receipt.json').read_bytes()),'job_succeeded':True,'score_recomputed':phase=='infer','scores_sha256':sha((folder/'scores.json').read_bytes()) if phase=='infer' else None})
  return receipt
 except BaseException as exc:
  write_json(folder/'failure.json',{'status':'NO_COMPLETED_RESULT','error_type':type(exc).__name__,'GPU_allocated':bool(pod and pod['spec'].get('nodeName')),'model_results_claimed':False,'protocol_sha256':sha(canonical(p))})
  raise
 finally:
  # Collect before deletion, even on failures. No pods left waiting or idling.
  cleanup_errors=[]
  if submitted:
   try:
    if pod and not logs:
     log=kubectl(['logs',pod['metadata']['name']],check=False).stdout
     (ROOT/'.tools'/f'{name}.log').write_text(log)
   except Exception:cleanup_errors.append('log_collection_failed')
   try:
    deleted=kubectl(['delete','job',name,'--ignore-not-found=true','--wait=true','--timeout=60s'],check=False,timeout=70)
    if deleted.returncode:cleanup_errors.append('job_delete_failed')
   except Exception:cleanup_errors.append('job_delete_failed')
  try:
   if cm_created:
    deleted=kubectl(['delete','configmap',name,'--ignore-not-found=true'],check=False)
    if deleted.returncode:cleanup_errors.append('configmap_delete_failed')
  except Exception:cleanup_errors.append('configmap_delete_failed')
  write_json(folder/'lifecycle.json',{'host_elapsed_seconds':round(time.monotonic()-started,2),'job_samples':sample,'terminal_job_status':jobdata.get('status') if jobdata else None,'cleanup_requested':True,'cleanup_errors':cleanup_errors,'submission_succeeded':submitted})
  if any('delete_failed' in e for e in cleanup_errors):raise RuntimeError('Cleanup incomplete; inspect lifecycle and remove own Job/ConfigMap before continuing')

def main():
 p=argparse.ArgumentParser();p.add_argument('--run-id',choices=['E0','E1','E2'],required=True);p.add_argument('--phase',choices=['train','infer'],required=True);a=p.parse_args()
 r=execute(a.run_id,a.phase);print(json.dumps({k:r.get(k) for k in ['status','run_id','phase','inference_rows','optimizer_steps','wall_seconds','staging_seconds']}))
if __name__=='__main__':main()
