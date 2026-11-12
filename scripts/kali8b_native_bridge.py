"""Host-only native ABA recipe dispatcher and frozen scorer. Maximum one GPU."""
import hashlib,json,shlex,threading,time
from pathlib import Path
import kali8b_study_jobs as jobs
ROOT=jobs.ROOT;S=jobs.S;CIDS=('P13','P14')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def pointer(cid):
 p={'schema':'kali.verified64.pointer.v1','candidate_id':cid,
    'grading_lock_sha256':sha(S/'grading-lock-private.json'),
    'model_id':jobs.protocol('P11')['model_id'],'model_revision':jobs.protocol('P11')['model_revision']}
 if cid=='E0':p.update(adapter_sha256=None,optimizer_steps=0)
 else:
  r=json.loads((S/cid/'run/receipt-private.json').read_text());e=json.loads((S/cid/'run/adapter-export-private.json').read_text())
  assert e['adapter_sha256']==r['adapter_sha256'];p.update(adapter_sha256=r['adapter_sha256'],optimizer_steps=r['optimizer_steps'])
 return p

def freeze_baseline():
 scores={}
 for cid in ('P11','P12'):
  assert json.loads((S/cid/'run/host-private.json').read_text())['status']=='COLLECTED'
  scores[cid]=json.loads((S/cid/'run/scores-private.json').read_text())
 b1=json.loads((S/'P11/run/base-predictions-private.json').read_text());b2=json.loads((S/'P12/run/base-predictions-private.json').read_text());assert b1==b2
 choices=[('E0',0.0)]+[(cid,x['ABA_score']) for cid,x in scores.items() if x['passes_all_gates']]
 best=max(choices,key=lambda a:a[1]);record={'status':'FIXED_CONTROL_CHAMPION_FROZEN_BEFORE_ABA','candidate_id':best[0],'score':best[1],'pointer':pointer(best[0]),'fixed_scores':{c:v['ABA_score'] for c,v in scores.items()},'official_TEST_rows':0,'final64_used':False}
 path=S/'native-baseline-private.json';raw=json.dumps(record,indent=2)+'\n'
 if path.exists():assert path.read_text()==raw
 else:path.write_text(raw)
 return record

class Broker:
 def __init__(self,driver):
  self.driver=driver;self.baseline=freeze_baseline();self.lock=threading.Lock();self.states={};self.threads=[];self.started=[];self.current=None
  self.manifest_sha256=sha(driver.OUT/'task/training_manifest.json')
 def train(self,cid):
  try:
   jobs.submit(cid);host=jobs.watch(cid,seconds=3*3600)
   assert host['status']=='COLLECTED',host.get('error','Training did not complete')
   r=json.loads((S/cid/'run/receipt-private.json').read_text());assert r['optimizer_steps']==r['nonzero_gradient_steps']==733 and r['changed_tensors']>0
   state={'status':'REAL_GPU_TRAINING_COMPLETE','candidate_id':cid,'pointer':pointer(cid),'training_receipt':r,'official_TEST_rows':0}
  except BaseException as e:state={'status':'FAILED','candidate_id':cid,'error_type':type(e).__name__,'detail':str(e)[:180]}
  with self.lock:self.states[cid]=state;self.current=None
  (self.driver.OUT/(cid+'-backend-private.json')).write_text(json.dumps(state,indent=2)+'\n')
 def call(self,req):
  action=req.get('action')
  if action=='health' and set(req)=={'action'}:
   return {'status':'READY','allowed_candidates':list(CIDS),'baseline_candidate':self.baseline['candidate_id'],'max_parallel_GPU':1,'official_TEST_rows':0}
  if action=='submit' and set(req)=={'action','candidate_id','manifest_sha256'}:
   cid=req['candidate_id'];assert cid in CIDS and req['manifest_sha256']==self.manifest_sha256
   with self.lock:
    assert self.current is None,'Parallel GPU submission prohibited'
    assert cid not in self.started and not (S/cid/'run').exists(),'No duplicate or replay training'
    assert len(self.started)<2
    journal=self.driver.collect_journal();assert any(a['target'].endswith('/setup_1') and a['output'].get('failed') is False for a in journal['actions'])
    active=set(journal['started_actions'])-{a['target'] for a in journal['actions']}
    assert any('/worker_' in a for a in active),'Only an active native Worker can dispatch'
    self.started.append(cid);self.current=cid;self.states[cid]={'status':'IN_PROGRESS','candidate_id':cid}
    (self.driver.OUT/(cid+'-native-dispatch-private.json')).write_text(json.dumps({'run_id':journal['run_id'],'active_actions':sorted(active),'request':req},indent=2)+'\n')
    t=threading.Thread(target=self.train,args=(cid,),daemon=True);self.threads.append(t);t.start()
   return {'status':'SUBMITTED','candidate_id':cid,'official_TEST_rows':0}
  if action=='status' and set(req)=={'action','candidate_id'}:
   cid=req['candidate_id'];assert cid in self.started
   return self.states[cid]
  if action=='score' and set(req)=={'action','pointer'}:
   p=req['pointer'];cid=p['candidate_id']
   if p==self.baseline['pointer']:score=self.baseline['score'];steps=p['optimizer_steps']
   else:
    assert cid in self.started and self.states[cid]['status']=='REAL_GPU_TRAINING_COMPLETE'
    assert p==self.states[cid]['pointer'],'Uncertified artifact pointer'
    s=json.loads((S/cid/'run/scores-private.json').read_text());score=s['ABA_score'];steps=733
   return {'score':score,'components':{'optimizer_steps':steps,'official_TEST_rows':0}}
  raise ValueError('Invalid request schema')
 def abort_running(self):
  cid=self.current
  if cid:
   _,run,_=jobs.paths(cid);f=run/'host-private.json'
   if f.exists():
    r=json.loads(f.read_text());jobs.delete_training(cid,r);r.update(status='FAILED',error='Native controller stopped before training completion');f.write_text(json.dumps(r,indent=2)+'\n')

def bridge(driver,stop):
 broker=Broker(driver);driver.BROKER=broker;done=set();transport_failures=0
 try:
  while not stop.is_set():
   code="import json,pathlib;d=pathlib.Path('/mnt/aba-scratch/study/broker');print(json.dumps({p.name:p.read_text() for p in d.glob('*.request.json') if not p.with_name(p.name.replace('.request.','.response.')).exists()}))"
   r=driver.ssh('python3 -c '+shlex.quote(code))
   if r.returncode:
    transport_failures+=1
    if transport_failures>=5:raise RuntimeError('Repeated mailbox SSH failure')
    stop.wait(5);continue
   transport_failures=0
   for name,raw in json.loads(r.stdout).items():
    if name in done:continue
    try:response=broker.call(json.loads(raw))
    except Exception as e:response={'status':'FAILED','error_type':type(e).__name__,'detail':str(e)[:180]}
    target=name.replace('.request.','.response.')
    code="import pathlib,sys;p=pathlib.Path('/mnt/aba-scratch/study/broker')/"+repr(target)+";t=p.with_suffix('.tmp');t.write_text(sys.stdin.read());t.replace(p)"
    r=driver.ssh('python3 -c '+shlex.quote(code),payload=json.dumps(response));assert r.returncode==0;done.add(name)
   stop.wait(2)
 finally:
  if broker.current:broker.abort_running()
  for t in broker.threads:t.join(timeout=100)
  (driver.OUT/'broker-final-private.json').write_text(json.dumps({'started_candidates':broker.started,'states':{c:{k:v for k,v in r.items() if k!='training_receipt'} for c,r in broker.states.items()}},indent=2)+'\n')
