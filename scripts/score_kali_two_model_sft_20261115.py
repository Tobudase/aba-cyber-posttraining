"""Score saved pilot outputs and execute a uniform v6 CPU behavior review."""
import argparse,base64,collections,gzip,hashlib,json,math,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,submit,poll,write,cleanup,k
from kali_behavior_execution_20261114 import PRELUDE,isolate
from benchkit import native_kali,strict_option_values
DATA=ROOT/'data/benchkit/kali-two-model-sft-2026-11-15'
NAME='miw113-kali-two-model-v6-score-1115'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def native():
 freeze=json.loads((DATA/'launch-freeze.json').read_text())
 assert all(sha(ROOT/'scripts'/n)==h for n,h in freeze['config']['evaluation_sha256'].items()),'Frozen evaluation source changed'
 pred=json.loads((DATA/'predictions-private.json').read_text());refs=json.loads((DATA/'references-private.json').read_text());inputs=json.loads(gzip.decompress((DATA/'gpu-inputs.json.gz').read_bytes()));panels={p:{r['id'] for r in rr} for p,rr in inputs['panels'].items()};sc=native_kali();details={};scores={}
 for label,rows in pred.items():
  assert len({r['id'] for r in rows})==len(rows) and {r['id'] for r in rows}<=set(refs)
  details[label]={}
  for r in rows:
   val=sc.score_one(refs[r['id']],r['response']);details[label][r['id']]={'native':val['total_score'],'strict':not r['truncated'] and bool(strict_option_values(refs[r['id']],r['response'],sc)),'format_error':bool(val['format_error']),'complete':r['response'].count('<output>')==1 and r['response'].count('</output>')==1,'truncated':r['truncated'],'early_EOS':r['early_EOS_first_two'],'generated_tokens':r['generated_tokens']}
  scores[label]={}
  for panel,ii in panels.items():
   if not ii<=set(details[label]):continue
   dd=[details[label][i] for i in sorted(ii)];scores[label][panel]={'rows':len(ii),'native_points':math.fsum(r['native'] for r in dd)/len(ii)*100,**{key:sum(r[key] for r in dd) for key in ['strict','format_error','complete','truncated','early_EOS','generated_tokens']}}
 paired={}
 for model in ['redsage','qwen']:
  base=details[model+'_base'];old=panels['old64'];correct={i for i in old if base[i]['strict']}
  for step in [128,256]:
   label=model+'_step'+str(step);dd=details[label];got={i for i in old if dd[i]['strict']};paired[label]={'old_base_correct':len(correct),'old_retained':len(correct&got),'old_lost':len(correct-got),'old_gained':len(got-correct),'old_native_delta':scores[label]['old64']['native_points']-scores[model+'_base']['old64']['native_points'],'old_lost_ids':sorted(correct-got)}
 write(DATA/'native-details-private.json',details);write(DATA/'native-summary.json',scores);write(DATA/'paired-retention-private.json',paired);return scores

def behavior():
 if (DATA/'behavior-v6-private.json').exists():
  assert (DATA/'behavior-summary.json').exists(),'Interrupted collection: recover summaries from saved behavior artifact, without executing again'
  return
 pred=json.loads((DATA/'predictions-private.json').read_text());pred={a:[r for r in rr if not r['id'].startswith('sample_')] for a,rr in pred.items()}
 fixtures=json.loads((ROOT/'data/benchkit/kali-functional-repair-v2-2026-11-15/fixtures.json').read_text());rows=fixtures['train']+fixtures['dev']
 payload=json.dumps({'fixtures':rows,'predictions':pred},separators=(',',':')).encode();names=['kali_functional_behavior_worker_v6_20261115.py','kali_hardlink_oracle_v6_20261115.py','kali_data_release_20261114.py','kali_functional_data_20261115.py','kali_functional_data_v2_20261115.py','kali_fit64_behavior_review_v5_20261115.py','kali-behavior-fixture-worker-v2-20261112.py'];files={n:(ROOT/'scripts'/n).read_text() for n in names}
 freeze=json.loads((DATA/'launch-freeze.json').read_text());assert sha(ROOT/'scripts/kali_hardlink_oracle_v6_20261115.py')==freeze['config']['oracle_v6_source_sha256']
 assert all(sha(ROOT/'scripts'/n)==h for n,h in freeze['config']['evaluation_sha256'].items()),'Frozen evaluation source changed'
 cfg={'module_sha256':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()},'payload_sha256':hashlib.sha256(payload).hexdigest(),'source_predictions_sha256':sha(DATA/'predictions-private.json'),'official_TEST_rows':0,'model_queries':0}
 program=PRELUDE+"\nimport sys\nsys.path.insert(0,'/input')\nfrom kali_functional_behavior_worker_v6_20261115 import main\nmain()\n"
 if not (OUT/NAME).exists():print(json.dumps(submit(NAME,{'worker.py':program,'config.json':json.dumps(cfg),**files},{'cpu':'2','memory':'3Gi','ephemeral-storage':'3Gi'},binary_files={'payload.json.gz':gzip.compress(payload,mtime=0)},runtime=2400)),flush=True)
 released=(OUT/NAME/'network-policy.json').exists();last=None
 for _ in range(240):
  state=poll(NAME);log=(OUT/NAME/'worker.log').read_text() if (OUT/NAME/'worker.log').exists() else ''
  if not released and 'READY_FOR_NETWORK_ISOLATION ' in log:isolate(NAME);released=True
  lines=[x for x in log.splitlines() if x.startswith(('FUNCTIONAL_BEHAVIOR ','PREVIEW_ORACLE_CONTROLS ','FUNCTIONAL_CONTROLS_PASS '))];current=(state['status'],lines[-1] if lines else 'setup')
  if current!=last:print(json.dumps({'state':current}),flush=True);last=current
  if state['status']=='SUCCEEDED':
   assert 'NETWORK_ISOLATION_VERIFIED ' in log;items=[x.split('=',1)[1] for x in log.splitlines() if x.startswith('FUNCTIONAL_BEHAVIOR_ARTIFACT=')];assert len(items)==1
   result=json.loads(gzip.decompress(base64.b64decode(items[0],validate=True)));assert result['config']==cfg and all(result['preview_controls'].values()) and all(all(v.values()) for v in result['controls'].values())
   write(DATA/'behavior-v6-private.json',result);cleanup(NAME);k('delete','networkpolicy',NAME,'--wait=true','--timeout=20s');break
  if state['status']=='FAILED':raise RuntimeError('V6 behavior failed; preserve original worker output')
  time.sleep(10)
 else:raise TimeoutError('CPU behavior bounded window expired')

 def panelsummary():
  data=json.loads(gzip.decompress((DATA/'gpu-inputs.json.gz').read_bytes()));details=result['details'];summary={}
  tool_by_id={row['id']:row['tool'] for row in rows}
  for arm,dd in details.items():
   summary[arm]={}
   for panel in ['new_dev32','train_probe32']:
    ids={r['id'] for r in data['panels'][panel]}
    if not ids<=set(dd):continue
    counts=dict(collections.Counter(dd[i] for i in ids));passed=counts.get('fixture_pass',0);unknown=sum(n for k,n in counts.items() if k.startswith('unknown'));summary[arm][panel]={'rows':len(ids),'counts':counts,'lower':passed,'upper':passed+unknown}
    for tool in ['hardlink','pyi-makespec','virtualenv','dnstwist']:
     subset={i for i in ids if tool_by_id[i]==tool};cc=dict(collections.Counter(dd[i] for i in subset));pp=cc.get('fixture_pass',0);uu=sum(n for k,n in cc.items() if k.startswith('unknown'));summary[arm][panel+':'+tool]={'rows':len(subset),'counts':cc,'lower':pp,'upper':pp+uu}
  return summary
 write(DATA/'behavior-summary.json',panelsummary());write(DATA/'behavior-audit.json',{'network_isolation_verified':True,'all_fixture_controls_passed':True,'all_preview_regression_controls_passed':True,'versions':result['hardlink_version'],'prediction_sha256':cfg['source_predictions_sha256'],'oracle_sources':cfg['module_sha256'],'original_frozen_scores_overwritten':False})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['native','behavior','all']);a=p.parse_args()
 if a.action in ['native','all']:native()
 if a.action in ['behavior','all']:behavior()
 print('SCORING_COMPLETE',flush=True)
