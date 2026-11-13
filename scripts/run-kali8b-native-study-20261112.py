#!/usr/bin/env python3
"""Real two-candidate native ABA controller, with durable host-only GPU adapters."""
import datetime,hashlib,json,os,shlex,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_kali8b_native_study_import import build_task
from kali8b_native_bridge import S,bridge
NAME='miw113-kali8b-native-v64-20261112-r13';REMOTE='/mnt/aba-scratch/study'
OUT=ROOT/'docs/verification/kali8b-native-v64-20261112';KNOWN=OUT/'ssh-known-private'
TASK_NAME='kali8b-verified64';BROKER=None
import kali8b_native_vm as m
SSH=[str(ROOT/'.tools/virtctl'),'--context','nautilus','-n','ecepxie','ssh','fedora@vm/'+NAME,'--identity-file',str(m.KEY),'--known-hosts',str(KNOWN),'--local-ssh-opts=-o StrictHostKeyChecking=accept-new','--local-ssh-opts=-o IdentitiesOnly=yes','--local-ssh-opts=-o ConnectTimeout=10']
SSH+=['--local-ssh-opts=-o ServerAliveInterval=20','--local-ssh-opts=-o ServerAliveCountMax=6']
def call(args,payload=None,timeout=60):return subprocess.run(args,input=payload,text=True,capture_output=True,timeout=timeout,cwd=ROOT)
def ssh(command,payload=None,timeout=60):return call(SSH+['--command',command],payload,timeout)
def k(*args,payload=None):
 r=call(m.BASE+list(args),payload);assert r.returncode==0,r.stderr[-400:];return r.stdout
def save(record):
 p=OUT/'host-private.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(record,indent=2)+'\n');t.replace(p)
JOURNAL_LOCK=threading.Lock()
def collect_journal():
 program=(ROOT/'scripts/kali8b_native_journal.py').read_text()
 extra="""
import hashlib
errorlog=pathlib.Path('/mnt/aba-scratch/.tools/nrp-transport-errors.jsonl')
result['transport_errors']=[json.loads(line) for line in errorlog.read_text().splitlines()] if errorlog.is_file() else []
result['task_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('/mnt/aba-scratch/study/task').iterdir() if p.is_file()}
result['scored_outputs']={}
for action in result['actions']:
 out=action.get('output',{})
 if '/score_program_' in action['target'] and out.get('failed') is False and out.get('output_dir'):
  d=pathlib.Path(out['output_dir']);assert d.resolve().is_relative_to(root.resolve());files={}
  for name in ['run.py','README.md','train_metrics.json','final_model/model.json']:
   p=d/name
   if p.is_file() and not p.is_symlink():files[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text':p.read_text()}
  result['scored_outputs'][str(d)]=files
print(json.dumps(result))
"""
 program=program.replace('print(json.dumps(result))',extra)
 with JOURNAL_LOCK:
  r=ssh('cd /mnt/aba-scratch/aba && /mnt/aba-scratch/conda/envs/manager/bin/python -',payload=program,timeout=80);assert r.returncode==0,r.stderr[-300:]
  token=(ROOT/'.secrets/nrp_api_key').read_text().strip();raw=r.stdout.replace(token,'[REDACTED]');x=json.loads(raw)
  p=OUT/'journal-private.json';t=p.with_name('journal-'+str(os.getpid())+'.tmp');t.write_text(raw);t.replace(p);return x
def wait_controls(record):
 until=time.monotonic()+8*3600
 while time.monotonic()<until:
  controls={}
  for c in ('P11','P12'):
   p=S/c/'run/host-private.json';controls[c]=json.loads(p.read_text())['status'] if p.exists() else 'NOT_STARTED'
  if 'FAILED' in controls.values():raise RuntimeError('A fixed control failed; repair and preserve receipts before native launch')
  if all(v=='COLLECTED' for v in controls.values()):return
  record.update(status='WAITING_FIXED_CONTROLS_NO_VM',controls=controls);save(record);time.sleep(30)
 raise TimeoutError('Fixed controls did not finish before bounded controller deadline')
def main():
 assert not OUT.exists(),'Never overwrite a native attempt';OUT.mkdir(mode=0o700);subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 record={'status':'WAITING_FIXED_CONTROLS_NO_VM','local_controller_pid':os.getpid(),'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cleanup_errors':[],'official_TEST_rows':0,'native_completed':False};made=False;stop=threading.Event();t=None;token=''
 try:
  wait_controls(record);config=build_task(OUT)
  obj=m.manifest();obj['metadata']['name']=NAME;obj['spec']['template']['spec']['volumes'][1]['emptyDisk']['capacity']='20Gi';obj['spec']['template']['spec']['volumes'][2]['cloudInitNoCloud']['userData']=obj['spec']['template']['spec']['volumes'][2]['cloudInitNoCloud']['userData'].replace('+20','+1080')
  k('create','--dry-run=server','-f','-',payload=json.dumps(obj));assert call(m.BASE+['get','vm',NAME]).returncode!=0;k('create','-f','-',payload=json.dumps(obj));made=True;record['status']='VM_STARTING';save(record);print('FORMAL_NATIVE_VM_CREATED',flush=True)
  until=time.monotonic()+420
  while time.monotonic()<until:
   r=call(m.BASE+['get','vmi',NAME,'-o','json'])
   if r.returncode==0 and json.loads(r.stdout).get('status',{}).get('phase')=='Running':break
   time.sleep(5)
  else:raise TimeoutError('VM scheduling')
  until=time.monotonic()+600
  readiness=[]
  while time.monotonic()<until:
   attempt=ssh('true',timeout=25);readiness.append({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'returncode':attempt.returncode,'stderr':attempt.stderr[-700:]});(OUT/'ssh-readiness-private.json').write_text(json.dumps(readiness,indent=2)+'\n')
   if attempt.returncode==0:break
   time.sleep(5)
  else:raise TimeoutError('SSH readiness')
  # Reuse the exact checksum-tested Conda/install/one-line dispatch repair recipe.
  from kali8b_remote_install import install
  install(sys.modules[__name__],record)
  data={'config':config,'task':{p.name:p.read_text() for p in (OUT/'task').iterdir()}}
  stage="import json,pathlib,sys;r=pathlib.Path('/mnt/aba-scratch/study');r.mkdir();x=json.load(sys.stdin);(r/'task').mkdir();[(r/'task'/k).write_text(v) for k,v in x['task'].items()];(r/'config.json').write_text(json.dumps(x['config'],indent=2)+'\\n');(r/'playground').mkdir();(r/'cli-state').mkdir(mode=0o700)"
  r=ssh('python3 -c '+shlex.quote(stage),payload=json.dumps(data));assert r.returncode==0
  for src,dest in [('nrp_anthropic_transport.py','transport.py'),('kali8b_native_mailbox.py','mailbox_server.py')]:
   r=ssh('mkdir -p /mnt/aba-scratch/.tools; cat > '+REMOTE+'/'+dest,payload=(ROOT/'scripts'/src).read_text());assert r.returncode==0
  preflight="from aibuildai_version import preload_source_runtime;preload_source_runtime();import json,copy;from pathlib import Path;from config import AgentConfig;from infra.model_catalog import canonical_key_for,is_routable_model_id;assert canonical_key_for('deepseek-v4-flash')=='deepseek/deepseek-v4-flash' and is_routable_model_id('deepseek-v4-flash');raw=json.loads(Path('/mnt/aba-scratch/study/config.json').read_text());new=AgentConfig.model_validate(raw);assert new.llm.default.model=='deepseek-v4-flash' and new.llm.endpoint_provider=='deepseek';old=copy.deepcopy(raw);old['llm']['default']['model']='gpt-oss';rejected=False\ntry:AgentConfig.model_validate(old)\nexcept Exception as e:rejected='not in the model catalog' in str(e)\nassert rejected;print(json.dumps({'status':'PINNED_FULL_AGENT_CONFIG_PASS','old_short_alias_rejected':True,'catalog_model':new.llm.default.model,'provider':new.llm.endpoint_provider,'transport_alias':'identity:deepseek-v4-flash','training_model_unchanged':True}))"
  result=ssh('cd /mnt/aba-scratch/aba && /mnt/aba-scratch/conda/envs/manager/bin/python -',payload=preflight,timeout=90);(OUT/'config-preflight-private.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout[-3000:],'stderr':result.stderr[-3000:]},indent=2)+'\n');assert result.returncode==0 and 'PINNED_FULL_AGENT_CONFIG_PASS' in result.stdout,'Pinned framework config preflight failed;no native/GPU submission'
  t=threading.Thread(target=bridge,args=(sys.modules[__name__],stop),daemon=True);t.start()
  from kali8b_native_daemon import start_and_wait
  token=(ROOT/'.secrets/nrp_api_key').read_text().strip();assert token and '\n' not in token;record.update(status='NATIVE_STARTING',config_sha256=hashlib.sha256((OUT/'config.json').read_bytes()).hexdigest());save(record)
  state=start_and_wait(sys.modules[__name__],token,record)
  (OUT/'client-private.json').write_text(json.dumps({'transport':'detached_systemd','exit':state['exit'],'SSH_reconnect_failures':record.get('SSH_reconnect_failures',0),'credential_source_removed':state['credential_source_removed']}))
  collect="import json,pathlib,hashlib;r=pathlib.Path('/mnt/aba-scratch/study');files={str(p.relative_to(r)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text':p.read_text(errors='replace')} for p in (r/'playground').rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size<200000 and 'deliverable' in p.parts};print(json.dumps({'files':files,'exit':json.loads((r/'exit.json').read_text()) if (r/'exit.json').exists() else None,'log_tail':(r/'native.log').read_text(errors='replace')[-5000:]}))"
  a=ssh('python3 -c '+shlex.quote(collect));assert a.returncode==0;raw=a.stdout.replace(token,'[REDACTED]');(OUT/'native-artifacts-private.json').write_text(raw);art=json.loads(raw)
  j=collect_journal();freeze=json.loads((OUT/'native-task-freeze-private.json').read_text());assert j['task_hashes']==freeze['task_sha256'],'Native task mutated'
  assert j['head']['result']=='completed' and not j['failures'],'Native run did not complete'
  selected=next(x['output']['output'] for x in reversed(j['actions']) if x['target']=='search_1');directory=selected['output_dir'];files=j['scored_outputs'][directory]
  names=['run.py','README.md','train_metrics.json','final_model/model.json'];assert set(files)==set(names)
  deliveries={}
  for name in names:
   matches=[v for p,v in art['files'].items() if p.endswith('/deliverable/'+name)];assert len(matches)==1;assert matches[0]==files[name];deliveries[name]=matches[0]['sha256']
  p=json.loads(files['final_model/model.json']['text']);cid=p['candidate_id'];expected=BROKER.call({'action':'score','pointer':p});assert abs(selected['score']-expected['score'])<1e-8
  assert set(BROKER.started)=={'P13','P14'} and all(BROKER.states[c]['status']=='REAL_GPU_TRAINING_COMPLETE' for c in BROKER.started),'Two real ABA candidates required'
  candidates=[(c,BROKER.call({'action':'score','pointer':BROKER.states[c]['pointer']})['score']) for c in BROKER.started]
  assert expected['score']==max(s for _,s in candidates),'Native final selection is not highest-scoring certified ABA candidate'
  # Pinned nb_tree initializes selected_output=None; baseline verification is
  # not baseline admission. Keep the native winner distinct from host retention.
  available=[(BROKER.baseline['candidate_id'],BROKER.baseline['score'])]+candidates
  retained_cid,retained_score=max(available,key=lambda a:a[1])
  retained_pointer=BROKER.baseline['pointer'] if retained_cid==BROKER.baseline['candidate_id'] else BROKER.states[retained_cid]['pointer']
  assert hashlib.sha256((ROOT/'scripts/check-kali8b-study-consistency.py').read_bytes()).hexdigest()==freeze['runtime_source_sha256']['check-kali8b-study-consistency.py'];assert hashlib.sha256((S/'placement-amendment-private.json').read_bytes()).hexdigest()==freeze['placement_amendment_sha256']
  consistency=subprocess.run([sys.executable,str(ROOT/'scripts/check-kali8b-study-consistency.py'),'--study',str(S),'--output',str(S/'four-arm-consistency-aggregate.json')],capture_output=True,text=True);assert consistency.returncode==0,'Four-arm numerical consistency gate failed;sealed64 must remain untouched'
  selection={'status':'NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN','candidate_id':retained_cid,'pointer':retained_pointer,'native_selected_candidate':cid,'native_selected_pointer':p,'native_run_id':j['run_id'],'DEV_score':retained_score,'native_selected_DEV_score':expected['score'],'all_available_scores':available,'deliverable_sha256':deliveries,'native_deliverable_candidate':cid,'retention_policy':'Native winner competes with preregistered fixed champion/E0 on DEV;ties retain the fixed champion. Never choose using final64.','final64_used':False,'official_TEST_rows':0}
  (S/'native-selection-private.json').write_text(json.dumps(selection,indent=2)+'\n');record.update(status='COMPLETE_VERIFIED_NATIVE_8B_STUDY',native_completed=True,native_selected_candidate=cid,retained_candidate=retained_cid,native_run_id=j['run_id']);save(record)
 except BaseException as e:
  record.update(status='FAILED',error_type=type(e).__name__,error=str(e)[:300]);print(json.dumps({'status':'FAILED','error_type':type(e).__name__,'error':str(e)[:200]}),flush=True)
  if made:
   try:collect_journal()
   except Exception:pass
 finally:
  stop.set()
  if t:t.join(timeout=120)
  if made:
   for args in [('delete','vm',NAME,'--ignore-not-found=true','--wait=true','--timeout=60s'),('wait','--for=delete','vmi/'+NAME,'--timeout=60s')]:
    r=call(m.BASE+list(args),timeout=75)
    if r.returncode:record['cleanup_errors'].append(r.stderr[-200:])
  KNOWN.unlink(missing_ok=True);save(record);print(json.dumps(record),flush=True)
if __name__=='__main__':main()
