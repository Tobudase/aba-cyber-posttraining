#!/usr/bin/env python3
"""Real two-candidate native ABA controller, with durable host-only GPU adapters."""
import datetime,hashlib,json,os,shlex,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_kali_curriculum_native_20261117 import build_task
from kali_curriculum_native_bridge_20261117 import S,bridge
PLANNED_UPDATES=json.loads((S/'paired-training-private.json').read_text())['protocol']['optimizer_updates_per_arm']
NAME='miw113-curriculum-native-aba-1117';REMOTE='/mnt/aba-scratch/study'
OUT=S/'native-controller';KNOWN=OUT/'ssh-known-private'
TASK_NAME='kali-verified-teacher-traces';BROKER=None
import kali8b_native_vm as m
SSH=[str(ROOT/'.tools/virtctl'),'--context','nautilus','-n','ecepxie','ssh','fedora@vm/'+NAME,'--identity-file',str(m.KEY),'--known-hosts',str(KNOWN),'--local-ssh-opts=-o StrictHostKeyChecking=accept-new','--local-ssh-opts=-o IdentitiesOnly=yes','--local-ssh-opts=-o ConnectTimeout=10']
# External OpenSSH must use this attempt's file, not the user's global file.
SSH+=['--local-ssh-opts=-o UserKnownHostsFile='+str(KNOWN)]
SSH+=['--local-ssh-opts=-o ServerAliveInterval=20','--local-ssh-opts=-o ServerAliveCountMax=6']
def call(args,payload=None,timeout=60):return subprocess.run(args,input=payload,text=True,capture_output=True,timeout=timeout,cwd=ROOT)
def ssh(command,payload=None,timeout=60):return call(SSH+['--command',command],payload,timeout)
def k(*args,payload=None):
 r=call(m.BASE+list(args),payload);assert r.returncode==0,r.stderr[-400:];return r.stdout
def save(record):
 p=OUT/'host-private.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(record,indent=2)+'\n');t.replace(p)
JOURNAL_LOCK=threading.Lock()
def collect_journal():
 program=(ROOT/'scripts/kali8b_native_journal.py').read_text().replace('kali8b-verified64',TASK_NAME)
 extra="""
import hashlib
errorlog=pathlib.Path('/mnt/aba-scratch/.tools/nrp-transport-errors.jsonl')
result['transport_errors']=[json.loads(line) for line in errorlog.read_text().splitlines()] if errorlog.is_file() else []
result['task_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('/mnt/aba-scratch/study/task').iterdir() if p.is_file()}
proxy=homes[0]/'private'/'score.py'
proxy_ok=proxy.is_file() and not proxy.is_symlink() and proxy.resolve().is_relative_to(homes[0].resolve())
result['grading_proxy_sha256']=hashlib.sha256(proxy.read_bytes()).hexdigest() if proxy_ok else None
result['grading_proxy_matches_found']=int(proxy_ok)
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
 until=time.monotonic()+7200
 while time.monotonic()<until:
  p=S/'runs/pair/score-private.json'
  if p.exists():return
  record.update(status='WAITING_EXPANDED_CONTROLS');save(record);time.sleep(20)
 raise TimeoutError('Expanded baseline scoring not ready')
def main():
 resume='--resume-pre-native' in sys.argv
 if resume:
  previous=json.loads((OUT/'host-private.json').read_text());assert previous['status'] in ['INSTALLING_DETACHED','WAITING_EXPANDED_CONTROLS'] and not (OUT/'config.json').exists() and not (OUT/'task').exists(),'Resume allowed only before native setup/search'
  (OUT/('pre-native-reload-'+str(previous['local_controller_pid'])+'-private.json')).write_text(json.dumps({'previous':previous,'reason':'Reload corrected scoring orchestration before any native action/candidate;reuse unchanged finite CPU installer VM,not model/training results.'},indent=2)+'\n')
 else:
  assert not OUT.exists(),'Never overwrite a native attempt';OUT.mkdir(mode=0o700)
 subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 record={'status':'WAITING_FIXED_CONTROLS_NO_VM','local_controller_pid':os.getpid(),'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cleanup_errors':[],'official_TEST_rows':0,'native_completed':False};made=False;stop=threading.Event();t=None;token=''
 try:
  if not resume:
   obj=m.manifest();obj['metadata']['name']=NAME;obj['spec']['template']['spec']['volumes'][1]['emptyDisk']['capacity']='20Gi';obj['spec']['template']['spec']['volumes'][2]['cloudInitNoCloud']['userData']=obj['spec']['template']['spec']['volumes'][2]['cloudInitNoCloud']['userData'].replace('+20','+600')
   k('create','--dry-run=server','-f','-',payload=json.dumps(obj));assert call(m.BASE+['get','vm',NAME]).returncode!=0
   created=json.loads(k('create','-f','-','-o','json',payload=json.dumps(obj)));made=True;record['VM_UID']=created['metadata']['uid'];record['status']='VM_STARTING';save(record);print('FORMAL_NATIVE_VM_CREATED',flush=True)
  else:
   actual=json.loads(k('get','vm',NAME,'-o','json'));assert actual['metadata']['labels']['app.kubernetes.io/managed-by']=='miw113' and actual['spec']['runStrategy']=='Once'
   assert not any('persistentVolumeClaim' in v for v in actual['spec']['template']['spec']['volumes']);assert actual['metadata']['uid']==previous['VM_UID'];made=True;record['VM_UID']=actual['metadata']['uid'];record['resumed_CPU_VM_UID']=actual['metadata']['uid'];save(record)
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
  wait_controls(record);config=build_task(OUT)
  data={'config':config,'task':{p.name:p.read_text() for p in (OUT/'task').iterdir()}}
  stage="import json,pathlib,sys;r=pathlib.Path('/mnt/aba-scratch/study');r.mkdir();x=json.load(sys.stdin);(r/'task').mkdir();[(r/'task'/k).write_text(v) for k,v in x['task'].items()];(r/'config.json').write_text(json.dumps(x['config'],indent=2)+'\\n');(r/'playground').mkdir();(r/'cli-state').mkdir(mode=0o700)"
  r=ssh('python3 -c '+shlex.quote(stage),payload=json.dumps(data));assert r.returncode==0
  for src,dest in [('nrp_anthropic_transport.py','transport.py'),('kali8b_native_mailbox.py','mailbox_server.py')]:
   r=ssh('mkdir -p /mnt/aba-scratch/.tools; cat > '+REMOTE+'/'+dest,payload=(ROOT/'scripts'/src).read_text());assert r.returncode==0
  preflight="from aibuildai_version import preload_source_runtime;preload_source_runtime();import json,copy;from pathlib import Path;from config import AgentConfig;from infra.model_catalog import canonical_key_for,is_routable_model_id;assert canonical_key_for('deepseek-v4-flash')=='deepseek/deepseek-v4-flash' and is_routable_model_id('deepseek-v4-flash');raw=json.loads(Path('/mnt/aba-scratch/study/config.json').read_text());new=AgentConfig.model_validate(raw);assert new.llm.default.model=='deepseek-v4-flash' and new.llm.endpoint_provider=='deepseek';old=copy.deepcopy(raw);old['llm']['default']['model']='gpt-oss';rejected=False\ntry:AgentConfig.model_validate(old)\nexcept Exception as e:rejected='not in the model catalog' in str(e)\nassert rejected;print(json.dumps({'status':'PINNED_FULL_AGENT_CONFIG_PASS','old_short_alias_rejected':True,'catalog_model':new.llm.default.model,'provider':new.llm.endpoint_provider,'transport_alias':'identity:deepseek-v4-flash','training_model_unchanged':True}))"
  result=ssh('cd /mnt/aba-scratch/aba && /mnt/aba-scratch/conda/envs/manager/bin/python -',payload=preflight,timeout=90);(OUT/'config-preflight-private.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout[-3000:],'stderr':result.stderr[-3000:]},indent=2)+'\n');assert result.returncode==0 and 'PINNED_FULL_AGENT_CONFIG_PASS' in result.stdout,'Pinned framework config preflight failed;no native/GPU submission'
  t=threading.Thread(target=bridge,args=(sys.modules[__name__],stop),daemon=True);t.start()
  from kali_curriculum_native_daemon_20261117 import start_and_wait
  token=(ROOT/'.secrets/nrp_api_key').read_text().strip();assert token and '\n' not in token;record.update(status='NATIVE_STARTING',config_sha256=hashlib.sha256((OUT/'config.json').read_bytes()).hexdigest());save(record)
  state=start_and_wait(sys.modules[__name__],token,record)
  (OUT/'client-private.json').write_text(json.dumps({'transport':'detached_systemd','exit':state['exit'],'SSH_reconnect_failures':record.get('SSH_reconnect_failures',0),'credential_source_removed':state['credential_source_removed']}))
  collect="import json,pathlib,hashlib;r=pathlib.Path('/mnt/aba-scratch/study');files={str(p.relative_to(r)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text':p.read_text(errors='replace')} for p in (r/'playground').rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size<200000 and 'deliverable' in p.parts};print(json.dumps({'files':files,'exit':json.loads((r/'exit.json').read_text()) if (r/'exit.json').exists() else None,'log_tail':(r/'native.log').read_text(errors='replace')[-5000:]}))"
  a=ssh('python3 -c '+shlex.quote(collect));assert a.returncode==0;raw=a.stdout.replace(token,'[REDACTED]');(OUT/'native-artifacts-private.json').write_text(raw);art=json.loads(raw)
  j=collect_journal();freeze=json.loads((OUT/'native-task-freeze-private.json').read_text());assert j['task_hashes']==freeze['task_sha256'],'Native task mutated'
  expected_proxy=hashlib.sha256(json.loads((OUT/'task/setup_payload.json').read_text())['score_py'].encode()).hexdigest()
  assert j['grading_proxy_sha256']==expected_proxy,'Native grading proxy differs from the operator-frozen host-score contract'
  assert j['head']['result']=='completed' and not j['failures'],'Native run did not complete'
  selected=next(x['output']['output'] for x in reversed(j['actions']) if x['target']=='search_1');directory=selected['output_dir'];files=j['scored_outputs'][directory]
  names=['run.py','README.md','train_metrics.json','final_model/model.json'];assert set(files)==set(names)
  deliveries={}
  for name in names:
   matches=[v for p,v in art['files'].items() if p.endswith('/deliverable/'+name)];assert len(matches)==1;assert matches[0]==files[name];deliveries[name]=matches[0]['sha256']
  p=json.loads(files['final_model/model.json']['text']);cid=p['candidate_id'];expected=BROKER.call({'action':'score','pointer':p});assert abs(selected['score']-expected['score'])<1e-8
  assert set(BROKER.started)=={'A1','A2'} and all(BROKER.states[c]['status']=='REAL_GPU_TRAINING_COMPLETE' for c in BROKER.started),'Two genuine new native candidates required'
  provenance={c:BROKER.states[c]['training_provenance'] for c in BROKER.started};assert all(p['new_optimizer_steps_this_run']==PLANNED_UPDATES and not p['reused_candidate_training'] for p in provenance.values())
  record['native_training_provenance']=provenance
  candidates=[(c,BROKER.call({'action':'score','pointer':BROKER.states[c]['pointer']})['score']) for c in BROKER.started];assert expected['score']==max(v for _,v in candidates)
  available=[(BROKER.baseline['candidate_id'],BROKER.baseline['score'])]+candidates;retained_cid,retained_score=max(available,key=lambda a:a[1]);retained_pointer=BROKER.baseline['pointer'] if retained_cid==BROKER.baseline['candidate_id'] else BROKER.states[retained_cid]['pointer']
  selection={'status':'NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN','candidate_id':retained_cid,'pointer':retained_pointer,'native_selected_candidate':cid,'native_selected_pointer':p,'native_run_id':j['run_id'],'DEV_score':retained_score,'native_selected_DEV_score':expected['score'],'all_available_scores':available,'native_recipes':BROKER.recipes,'new_optimizer_steps_total':2*PLANNED_UPDATES,'deliverable_sha256':deliveries,'retention_policy':'Best eligible E0/fixed/native on frozen expanded DEV+retention metric,ties keep existing.','confirmation_used':False,'official_TEST_rows':0}
  (S/'native-selection-private.json').write_text(json.dumps(selection,indent=2)+'\n');record.update(status='COMPLETE_VERIFIED_NATIVE_TEACHER_ABA',native_completed=True,native_selected_candidate=cid,retained_candidate=retained_cid,native_run_id=j['run_id']);save(record)
 except BaseException as e:
  record.update(status='FAILED',error_type=type(e).__name__,error=str(e)[:300],cleanup_pending=True);save(record);print(json.dumps({'status':'FAILED','error_type':type(e).__name__,'error':str(e)[:200]}),flush=True)
  if made:
   try:collect_journal()
   except Exception:pass
 finally:
  cleanup(record,made,stop,t)
def cleanup(record,made,stop,thread):
 stop.set()
 try:
  if thread:thread.join(timeout=120)
 finally:
  try:
   if made:
    try:
     current=call(m.BASE+['get','vm',NAME,'-o','json'])
     if current.returncode==0:
      assert json.loads(current.stdout)['metadata']['uid']==record['VM_UID'],'Refuse to delete a VM with a different UID'
      r=call(m.BASE+['delete','vm',NAME,'--ignore-not-found=true','--wait=true','--timeout=60s'],timeout=75)
      if r.returncode:record['cleanup_errors'].append(r.stderr[-200:])
     elif 'NotFound' not in current.stderr:record['cleanup_errors'].append('Unable to verify owned VM before cleanup')
     vmi=call(m.BASE+['get','vmi',NAME,'-o','json'])
     if vmi.returncode==0:
      assert any(o.get('uid')==record['VM_UID'] for o in json.loads(vmi.stdout)['metadata'].get('ownerReferences',[])),'Unexpected VMI owner; no destructive action'
      r=call(m.BASE+['wait','--for=delete','vmi/'+NAME,'--timeout=60s'],timeout=75)
      if r.returncode:record['cleanup_errors'].append(r.stderr[-200:])
     elif 'NotFound' not in vmi.stderr:record['cleanup_errors'].append('Unable to verify VMI cleanup')
    except Exception as e:record['cleanup_errors'].append(type(e).__name__+': '+str(e)[:180])
  finally:
   KNOWN.unlink(missing_ok=True);record['cleanup_pending']=False;save(record);print(json.dumps(record),flush=True)
if __name__=='__main__':main()
