"""Native journal-gated fresh Qwen GPU dispatcher; host-only frozen scoring."""
import base64,gzip,hashlib,json,shlex,subprocess,threading,time
from pathlib import Path
import kali_qwen_aba_jobs_20261115 as jobs
from build_kali_qwen_native_20261115 import baseline
S=jobs.DATA
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class Broker:
 def __init__(self,driver):
  self.driver=driver;self.baseline=baseline();self.lock=threading.Lock();self.states={};self.started=[];self.threads=[];self.current=None;self.recipes={};self.manifest_sha256=sha(driver.OUT/'task/training_manifest.json');self.placement_sha256=json.loads((driver.OUT/'task/training_manifest.json').read_text())['placement_sha256']
 def train(self,cid,lr):
  try:
   assert sha(S/'placement-amendment-private.json')==self.placement_sha256,'Placement changed after native task freeze'
   result=jobs.run(cid,lr);r=json.loads((S/cid/'receipt.json').read_text())['models']['qwen'];p=json.loads((S/cid/'adapter-pointer-private.json').read_text());p.pop('cache_adapter');r['learning_rate']=lr;r['new_optimizer_steps_this_run']=128
   state={'status':'REAL_GPU_TRAINING_COMPLETE','candidate_id':cid,'pointer':p,'training_receipt':r,'training_provenance':{'execution':'FRESH_NATIVE_GPU_TRAINING','new_optimizer_steps_this_run':128,'reused_candidate_training':False}}
  except BaseException as e:state={'status':'FAILED','candidate_id':cid,'error_type':type(e).__name__,'detail':str(e)[:240]}
  with self.lock:self.states[cid]=state;self.current=None
  (self.driver.OUT/(cid+'-backend-private.json')).write_text(json.dumps(state,indent=2)+'\n')
 def call(self,req):
  action=req.get('action')
  if action=='health' and set(req)=={'action'}:return {'status':'READY','allowed_candidates':['A1','A2'],'learning_rates':[1e-5,3e-5,5e-5],'max_parallel_GPU':1,'official_TEST_rows':0}
  if action=='train_data' and set(req)=={'action','manifest_sha256'}:
   assert req['manifest_sha256']==self.manifest_sha256;raw=(self.driver.OUT/'training-encoded-host-private.json').read_bytes();m=json.loads((self.driver.OUT/'task/training_manifest.json').read_text());assert hashlib.sha256(raw).hexdigest()==m['train_encoded_sha256'] and len(json.loads(raw))==256
   return {'status':'TRAIN_ONLY','train_gzip_base64':base64.b64encode(gzip.compress(raw)).decode(),'DEV_rows':0}
  if action=='submit' and set(req)=={'action','candidate_id','learning_rate','manifest_sha256'}:
   cid=req['candidate_id'];lr=req['learning_rate'];assert cid in ['A1','A2'] and lr in [1e-5,3e-5,5e-5] and req['manifest_sha256']==self.manifest_sha256
   with self.lock:
    assert self.current is None and cid not in self.started and len(self.started)<2 and lr not in self.recipes.values();assert not (S/cid).exists(),'Never relabel an existing arm as fresh'
    journal=self.driver.collect_journal();assert any(a['target'].endswith('/setup_1') and a['output'].get('failed') is False for a in journal['actions']);active=set(journal['started_actions'])-{a['target'] for a in journal['actions']};assert any('/worker_' in a for a in active),'A real native Worker must be active'
    self.started.append(cid);self.recipes[cid]=lr;self.current=cid;self.states[cid]={'status':'IN_PROGRESS','candidate_id':cid};(self.driver.OUT/(cid+'-native-dispatch-private.json')).write_text(json.dumps({'run_id':journal['run_id'],'active_actions':sorted(active),'request':req},indent=2)+'\n');t=threading.Thread(target=self.train,args=(cid,lr),daemon=True);self.threads.append(t);t.start()
   return {'status':'SUBMITTED','candidate_id':cid,'new_updates_budget':128}
  if action=='status' and set(req)=={'action','candidate_id'}:
   assert req['candidate_id'] in self.started;return self.states[req['candidate_id']]
  if action=='score' and set(req)=={'action','pointer'}:
   p=req['pointer'];cid=p['candidate_id']
   if p==self.baseline['pointer']:score=self.baseline['score']
   else:
    assert cid in self.started and self.states[cid]['status']=='REAL_GPU_TRAINING_COMPLETE' and p==self.states[cid]['pointer'];score=json.loads((S/cid/'score.json').read_text())['qwen_step128']['score']
   return {'score':score,'components':{'optimizer_steps':p['optimizer_steps'],'official_TEST_rows':0}}
  raise ValueError('Invalid request schema')
 def abort_running(self):
  cid=self.current
  if not cid:return
  name='miw113-qwen-aba-'+cid.lower()+'-1115';d=jobs.OUT/name
  if (d/'host.json').exists():
   host=json.loads((d/'host.json').read_text());actual=jobs.k('get','job',name,'-o','json',check=False)
   if actual.returncode==0:
    assert json.loads(actual.stdout)['metadata']['uid']==host['uid'];jobs.k('delete','job',name,'--wait=true','--timeout=30s');jobs.k('delete','configmap',name,'--wait=true','--timeout=20s')

def bridge(driver,stop):
 broker=Broker(driver);driver.BROKER=broker;done=set();transport_failures=0;responses={}
 try:
  while not stop.is_set():
   code="import json,pathlib;d=pathlib.Path('/mnt/aba-scratch/study/broker');print(json.dumps({p.name:p.read_text() for p in d.glob('*.request.json') if not p.with_name(p.name.replace('.request.','.response.')).exists()}))"
   try:r=driver.ssh('python3 -c '+shlex.quote(code))
   except (subprocess.TimeoutExpired,OSError):r=None
   if r is None or r.returncode:
    transport_failures+=1
    (driver.OUT/'bridge-connectivity-private.json').write_text(json.dumps({'status':'RECONNECTING','consecutive_failures':transport_failures,'running_GPU_not_cancelled_for_transient_SSH':True})+'\n');stop.wait(10);continue
   transport_failures=0
   for name,raw in json.loads(r.stdout).items():
    if name in done:continue
    if name not in responses:
     try:responses[name]=broker.call(json.loads(raw))
     except Exception as e:responses[name]={'status':'FAILED','error_type':type(e).__name__,'detail':str(e)[:180]}
    response=responses[name]
    target=name.replace('.request.','.response.')
    code="import pathlib,sys;p=pathlib.Path('/mnt/aba-scratch/study/broker')/"+repr(target)+";t=p.with_suffix('.tmp');t.write_text(sys.stdin.read());t.replace(p)"
    try:r=driver.ssh('python3 -c '+shlex.quote(code),payload=json.dumps(response))
    except (subprocess.TimeoutExpired,OSError):r=None
    if r is None or r.returncode:break
    done.add(name)
   stop.wait(2)
 finally:
  if broker.current:broker.abort_running()
  for t in broker.threads:t.join(timeout=100)
  (driver.OUT/'broker-final-private.json').write_text(json.dumps({'started_candidates':broker.started,'states':{c:{k:v for k,v in r.items() if k!='training_receipt'} for c,r in broker.states.items()}},indent=2)+'\n')
