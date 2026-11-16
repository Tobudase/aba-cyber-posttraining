"""Post-selection stronger review; never overwrite V8 native selection scores."""
import base64,collections,datetime,gzip,hashlib,json,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,cleanup,write
from kali_two_model_submit_20261115 import submit_pilot
from kali_behavior_execution_20261114 import PRELUDE,isolate
from kali_qwen_aba_jobs_20261115 import DATA,sha
NAMES=['kali_qwen_supplement_behavior_v9_20261115.py','kali_qwen_full_style_oracle_20261115.py','kali_qwen_confirm_admission_20261115.py','kali_qwen_aux_admission_20261115.py','kali_hardlink_oracle_v6_20261115.py','kali_data_release_20261114.py','kali_functional_data_20261115.py','kali_functional_data_v2_20261115.py','kali_fit64_behavior_review_v5_20261115.py','kali-behavior-fixture-worker-v2-20261112.py']
def run(fixtures,predictions,label):
 assert json.loads((DATA/'native-selection-private.json').read_text())['status']=='NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN','No supplementary DEV or protected confirmation review before selection freeze'
 target=DATA/(label+'-v9-private.json');ii={r['id'] for r in fixtures};pred={a:[r for r in rr if r['id'] in ii] for a,rr in predictions.items()};assert all({r['id'] for r in rr}==ii for rr in pred.values())
 payload=json.dumps({'fixtures':fixtures,'predictions':pred},separators=(',',':')).encode();files={n:(ROOT/'scripts'/n).read_text() for n in NAMES};cfg={'module_sha256':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()},'payload_sha256':hashlib.sha256(payload).hexdigest(),'selection_sha256':sha(DATA/'native-selection-private.json'),'official_TEST_rows':0,'model_queries':0,'purpose':'Post-selection independent oracle refinement,not native scoring or checkpoint choice'}
 if target.exists():
  result=json.loads(target.read_text());assert result['config']==cfg;return result
 freeze=DATA/'supplement-v9-freeze.json'
 if freeze.exists():
  old=json.loads(freeze.read_text());assert old['module_sha256']==cfg['module_sha256'] and old['selection_sha256']==cfg['selection_sha256']
 else:write(freeze,{'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'module_sha256':cfg['module_sha256'],'selection_sha256':cfg['selection_sha256'],'native_metric_changed':False,'no_retraining_or_reselection':True})
 prelude=PRELUDE.replace("'dnstwist==20240812'","'dnstwist==20240812','clang-format==18.1.8'").replace("ip=socket.gethostbyname('pypi.org')","subprocess.run(['apt-get','update','-qq'],check=True,timeout=180)\nsubprocess.run(['apt-get','install','-y','-qq','--no-install-recommends','bsdextrautils','curl'],check=True,timeout=180)\nip=socket.gethostbyname('pypi.org')")
 program=prelude+"\nimport sys\nsys.path.insert(0,'/input')\nfrom kali_qwen_supplement_behavior_v9_20261115 import main\nmain()\n";name='miw113-qwen-v9-'+label+'-1115';d=OUT/name
 if not d.exists():print(json.dumps(submit_pilot(name,{'worker.py':program,'config.json':json.dumps(cfg),**files},{'cpu':'2','memory':'3Gi','ephemeral-storage':'3Gi'},binary_files={'payload.json.gz':gzip.compress(payload,mtime=0)},runtime=3600)),flush=True)
 if not (d/'host.json').exists():
  from kali_qwen_submission_recovery_20261115 import recover
  recover(name)
 deadline=time.monotonic()+5400;released=(d/'network-policy.json').exists();last=None
 while time.monotonic()<deadline:
  try:state=poll(name)
  except Exception as e:print('SUPPLEMENT_CPU_API_RETRY '+type(e).__name__,flush=True);time.sleep(10);continue
  log=(d/'worker.log').read_text() if (d/'worker.log').exists() else ''
  if not released and 'READY_FOR_NETWORK_ISOLATION ' in log:isolate(name);released=True
  lines=[x for x in log.splitlines() if x.startswith(('FULL_STYLE_CONTROLS ','FUNCTIONAL_CONTROLS_PASS ','FUNCTIONAL_BEHAVIOR '))];current=(state['status'],lines[-1] if lines else 'setup')
  if current!=last:print('SUPPLEMENT_V9 '+label+' '+json.dumps(current),flush=True);last=current
  if state['status']=='FAILED':raise RuntimeError('V9 control/review failure;preserve logs,no changed native selection')
  if state['status']=='SUCCEEDED':
   assert 'NETWORK_ISOLATION_VERIFIED ' in log;items=[x.split('=',1)[1] for x in log.splitlines() if x.startswith('FUNCTIONAL_BEHAVIOR_ARTIFACT=')];assert len(items)==1;result=json.loads(gzip.decompress(base64.b64decode(items[0],validate=True)));assert result['config']==cfg and len(result['controls'])==len(ii) and all(all(v.values()) for v in result['controls'].values());assert all(all(r[k] for k in ['full_effective_config','wrong_base_rejected','extra_setting_rejected']) for r in result['full_style_controls'].values());write(target,result);cleanup(name);k('delete','networkpolicy',name,'--ignore-not-found=true','--wait=true','--timeout=20s');return result
  time.sleep(10)
 raise TimeoutError('Supplemental CPU bounded window expired')
def bounds(fixtures,result):
 summary={}
 for arm,dd in result['details'].items():
  groups=collections.defaultdict(list)
  for row in fixtures:groups[row['constraint_group']].append(dd[row['id']])
  lower=sum(sum(x=='fixture_pass' for x in vv)/len(vv) for vv in groups.values())/len(groups)*100;upper=sum(sum(x=='fixture_pass' or x.startswith('unknown') for x in vv)/len(vv) for vv in groups.values())/len(groups)*100
  summary[arm]={'rows':len(fixtures),'groups':len(groups),'confirmed_utility_points':lower,'unresolved_upper_points':upper,'counts':dict(collections.Counter(dd.values())),'by_tool':{tool:dict(collections.Counter(dd[r['id']] for r in fixtures if r['tool']==tool)) for tool in sorted({r['tool'] for r in fixtures})}}
 return summary

def dev():
 fixtures=json.loads((DATA/'dev-fixtures-private.json').read_text());pred0=json.loads((DATA/'controls/predictions-private.json').read_text());pred={'E0':pred0['qwen_base'],'fixedSFT256':pred0['qwen_fixed']}
 for cid in ['A1','A2']:pred[cid]=json.loads((DATA/cid/'predictions-private.json').read_text())['qwen_step128']
 r=run(fixtures,pred,'dev');write(DATA/'supplement-v9-summary.json',{'status':'POST_SELECTION_SUPPLEMENTAL_REVIEW','scope':'Same frozen DEV outputs,0 new model queries;full effective style checks;does not change native score/selection','bounds':bounds(fixtures,r),'selection_sha256':sha(DATA/'native-selection-private.json')});return r
if __name__=='__main__':dev()
