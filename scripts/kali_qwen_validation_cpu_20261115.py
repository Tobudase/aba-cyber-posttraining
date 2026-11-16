"""Run expanded frozen validation on bounded CPU Jobs, with verified egress deny."""
import base64,datetime,gzip,hashlib,json,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,cleanup,write
from kali_two_model_submit_20261115 import submit_pilot
from kali_behavior_execution_20261114 import PRELUDE,isolate
DATA=ROOT/'data/benchkit/kali-qwen-aba-validation-2026-11-15'
NAMES=['kali_qwen_validation_behavior_v8_20261115.py','kali_qwen_aux_admission_20261115.py','kali_hardlink_oracle_v6_20261115.py','kali_data_release_20261114.py','kali_functional_data_20261115.py','kali_functional_data_v2_20261115.py','kali_fit64_behavior_review_v5_20261115.py','kali-behavior-fixture-worker-v2-20261112.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(predictions,label):
 target=DATA/(label+'-behavior-private.json')
 if target.exists():return json.loads(target.read_text())
 fixtures=json.loads((DATA/'dev-fixtures-private.json').read_text());ii={r['id'] for r in fixtures};predictions={a:[r for r in rr if r['id'] in ii] for a,rr in predictions.items()};assert all({r['id'] for r in rr}==ii for rr in predictions.values())
 payload=json.dumps({'fixtures':fixtures,'predictions':predictions},separators=(',',':')).encode();files={n:(ROOT/'scripts'/n).read_text() for n in NAMES};cfg={'module_sha256':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()},'payload_sha256':hashlib.sha256(payload).hexdigest(),'official_TEST_rows':0,'model_queries':0}
 freeze=json.loads((DATA/'launch-freeze.json').read_text());assert cfg['module_sha256']==freeze['behavior_modules']
 prelude=PRELUDE.replace("'dnstwist==20240812'","'dnstwist==20240812','clang-format==18.1.8'")
 prelude=prelude.replace("ip=socket.gethostbyname('pypi.org')","subprocess.run(['apt-get','update','-qq'],check=True,timeout=180)\nsubprocess.run(['apt-get','install','-y','-qq','--no-install-recommends','bsdextrautils','curl'],check=True,timeout=180)\nprint('AUX_BINARIES '+json.dumps({t:__import__('shutil').which(t) for t in ['column','look','curl','ls','clang-format']}),flush=True)\nip=socket.gethostbyname('pypi.org')")
 program=prelude+"\nimport sys\nsys.path.insert(0,'/input')\nfrom kali_qwen_validation_behavior_v8_20261115 import main\nmain()\n"
 name='miw113-qwen-aba-v9-'+label+'-1115';d=OUT/name
 if not d.exists():print(json.dumps(submit_pilot(name,{'worker.py':program,'config.json':json.dumps(cfg),**files},{'cpu':'2','memory':'3Gi','ephemeral-storage':'3Gi'},binary_files={'payload.json.gz':gzip.compress(payload,mtime=0)},runtime=2400)),flush=True)
 if not (d/'host.json').exists():
  from kali_qwen_submission_recovery_20261115 import recover
  recover(name)
 released=(d/'network-policy.json').exists();deadline=time.monotonic()+4200;last=None
 while time.monotonic()<deadline:
  try:state=poll(name)
  except Exception as e:print('CPU_API_RETRY '+type(e).__name__,flush=True);time.sleep(10);continue
  log=(d/'worker.log').read_text() if (d/'worker.log').exists() else ''
  if not released and 'READY_FOR_NETWORK_ISOLATION ' in log:isolate(name);released=True
  current=(state['status'],log.splitlines()[-1][:160] if log else 'setup')
  if current!=last:print(json.dumps({'cpu_validation':current}),flush=True);last=current
  if state['status']=='SUCCEEDED':
   assert 'NETWORK_ISOLATION_VERIFIED ' in log
   items=[x.split('=',1)[1] for x in log.splitlines() if x.startswith('FUNCTIONAL_BEHAVIOR_ARTIFACT=')];assert len(items)==1
   result=json.loads(gzip.decompress(base64.b64decode(items[0],validate=True)));assert result['config']==cfg and all(result['preview_controls'].values()) and all(all(v.values()) for v in result['controls'].values())
   write(target,result);cleanup(name);k('delete','networkpolicy',name,'--ignore-not-found=true','--wait=true','--timeout=20s');return result
  if state['status']=='FAILED':raise RuntimeError('Expanded validation failed; preserve raw log '+str(d))
  time.sleep(10)
 raise TimeoutError('Bounded CPU validation window expired')
def controls():
 rows=json.loads((DATA/'dev-fixtures-private.json').read_text());pred={'reference':[{'id':r['id'],'response':'<output>\n'+__import__('shlex').join(r['argv'])+'\n</output>','truncated':False} for r in rows],'alternate':[{'id':r['id'],'response':'<output>\n'+__import__('shlex').join(r['alternate_argv'])+'\n</output>','truncated':False} for r in rows]}
 result=run(pred,'controls');assert all(x=='fixture_pass' for dd in result['details'].values() for x in dd.values()),result['counts']
 write(DATA/'controls-audit.json',{'status':'ALL46_REFERENCE_ALTERNATE_AND_ALL_PROPERTY_MUTATIONS_PASS','fixture_count':46,'reference_and_alternate_scored':92,'model_queries':0,'behavior_sources':result['config']['module_sha256'],'network_isolation_verified':True});print('EXPANDED46_CONTROLS_VERIFIED',flush=True)
if __name__=='__main__':controls()
