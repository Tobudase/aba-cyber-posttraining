"""One post-selection internal384 confirmation; never retrain or reselect."""
import base64,datetime,gzip,hashlib,json,time,collections
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,cleanup,write
from kali_two_model_submit_20261115 import submit_pilot
from kali_qwen_aba_jobs_20261115 import DATA,FIXED,sha
from kali_qwen_supplement_cpu_20261115 import run as cpu,bounds
from kali_qwen_gpu_placement_20261115 import eligible_nodes
from benchkit import native_kali,strict_option_values
NAME='miw113-qwen-confirm384-1115';REL=ROOT/'data/benchkit/kali-data-release-2026-11-14/release'

def prepare():
 assert json.loads((DATA/'native-controller/host-private.json').read_text())['native_completed']
 selection=json.loads((DATA/'native-selection-private.json').read_text());assert selection['status']=='NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN'
 dest=DATA/'confirmation384';dest.mkdir(exist_ok=True)
 if (dest/'freeze.json').exists():
  assert json.loads((dest/'freeze.json').read_text())['selection_sha256']==sha(DATA/'native-selection-private.json');return
 audit=json.loads((DATA/'confirmation-eligibility-audit.json').read_text());assert audit['eligible_as_family_disjoint_confirmation'] and audit['eligible_as_selection_group_disjoint_confirmation'] and audit['protected_confirmation_model_queries']==0
 sums=json.loads((REL/'SHA256SUMS.json').read_text())
 for name in ['evaluation/private/confirm384.jsonl','evaluation/private/confirm-fixtures.jsonl']:assert sha(REL/name)==sums[name]
 records=[json.loads(s) for s in (REL/'evaluation/private/confirm384.jsonl').read_text().splitlines()];fixtures=[json.loads(s) for s in (REL/'evaluation/private/confirm-fixtures.jsonl').read_text().splitlines()];assert len(records)==len(fixtures)==384 and {r['id'] for r in records}=={r['id'] for r in fixtures};assert all(r['split']=='confirm' and r['official_test'] is False and not r['training_eligible'] for r in records)
 inputs=[{'id':r['id'],'native_messages':r['messages']} for r in records];assert all(all(m['role'] in ['user','system'] for m in r['native_messages']) for r in inputs)
 trainids={r['id'] for r in json.loads((DATA/'train-encoded-private.json').read_text())};devids={r['id'] for r in json.loads((DATA/'eval-inputs-private.json').read_text())};assert not {r['id'] for r in inputs}&(trainids|devids)
 source=ROOT/'data/benchkit/kali-functional-repair-v2-2026-11-15';train=json.loads((source/'new-records-private.json').read_text())['train']+json.loads((source/'replay-selected-private.json').read_text());norm=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'));assert not {norm(r['native_messages']) for r in inputs}&{norm(r['native_messages']) for r in train}
 write(dest/'inputs-private.json',inputs);write(dest/'fixtures-private.json',fixtures);write(dest/'references-private.json',{r['id']:r['native_label'] for r in records});write(dest/'freeze.json',{'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'selection_sha256':sha(DATA/'native-selection-private.json'),'native_selected_candidate':selection['native_selected_candidate'],'comparison_cohort':['E0','fixedSFT256','A1','A2'],'scope_amendment_sha256':sha(DATA/'confirmation-scope-amendment.json'),'records_sha256':sums['evaluation/private/confirm384.jsonl'],'fixtures_sha256':sums['evaluation/private/confirm-fixtures.jsonl'],'rows':384,'groups':len({r['constraint_group'] for r in fixtures}),'tools':dict(collections.Counter(r['tool'] for r in fixtures)),'source':'Internal authored constraint-combination holdout;same generator/author,not external expert gold or official TEST','no_retraining_or_reselection':True,'exact_train_ID_and_message_overlap':0,'score_source':'Pinned native partial+project strict plus V9 behavioral review;UNKNOWN unresolved'})
 audit.update(protected_confirmation_rows_read=384,protected_gold_rows_read=384,protected_confirmation_model_queries=0,query_count_status='OPENED_POST_SELECTION_NOT_YET_MODEL_QUERIED');write(DATA/'confirmation-eligibility-audit.json',audit)

def controls():
 prepare();dest=DATA/'confirmation384'
 if (dest/'linux-controls-audit.json').exists():return
 import shlex
 fixtures=json.loads((dest/'fixtures-private.json').read_text());pred={name:[{'id':r['id'],'response':'<output>\n'+shlex.join(r[key])+'\n</output>','truncated':False} for r in fixtures] for name,key in [('reference','argv'),('alternate','alternate_argv')]};result=cpu(fixtures,pred,'confirm-controls');assert all(v=='fixture_pass' for rr in result['details'].values() for v in rr.values()),result['counts'];write(dest/'linux-controls-audit.json',{'all384_reference_alternate_and_all_provided_mutations_pass':True,'full_style_base_and_extra_controls':len(result['full_style_controls']),'model_queries':0,'network_isolation_verified':True,'control_artifact_sha256':sha(DATA/'confirm-controls-v9-private.json')})

def compute():
 controls();dest=DATA/'confirmation384';freeze=json.loads((dest/'freeze.json').read_text());assert freeze['selection_sha256']==sha(DATA/'native-selection-private.json');d=OUT/NAME
 if (dest/'receipt.json').exists():return
 placement=json.loads((DATA/'placement-amendment-private.json').read_text());selection=json.loads((DATA/'native-selection-private.json').read_text());cid=selection['native_selected_candidate'];pointers={c:json.loads((DATA/c/'adapter-pointer-private.json').read_text()) for c in ['A1','A2']}
 if not d.exists():
  p=json.loads((FIXED/'model-protocols.json').read_text())['qwen'];p['allowed_GPU_models']=p['allowed_GPU_models']+['NVIDIA A10'];allinputs=json.loads((DATA/'eval-inputs-private.json').read_text());devfixtures=json.loads((DATA/'dev-fixtures-private.json').read_text());lookid=next(r['id'] for r in devfixtures if r['tool']=='look');index=next(i for i,r in enumerate(allinputs) if r['id']==lookid);diagnostic=allinputs[index//4*4:index//4*4+4];assert len(diagnostic)==4;raw=gzip.compress(json.dumps({'panels':{'confirmation384':json.loads((dest/'inputs-private.json').read_text())},'diagnostic_rows':diagnostic},separators=(',',':')).encode(),mtime=0);worker=ROOT/'scripts/kali_qwen_confirmation_worker_20261115.py';names=['kali_command_ngram_guard_20261115.py','kali_stable_objective_20261114.py','kali_exact_adapter_loading_20261115.py'];modules={n:(ROOT/'scripts'/n).read_text() for n in names};cfg={'mode':'confirmation','model_protocols':{'qwen':p},'worker_sha256':sha(worker),'inputs_sha256':hashlib.sha256(raw).hexdigest(),'module_sha256':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in modules.items()},'durable_output':'/cache/kali-qwen-aba-20261115/confirmation384','confirmation_adapters':[{'label':'fixedSFT256','adapter_name':'fixed','path':'/cache/kali-two-model-sft-20261115/miw113-kali-two-model-sft-r3-1115/qwen_step256/adapter','sha256':json.loads((DATA/'protocol.json').read_text())['fixed_comparator']['weights_sha256']},*({'label':c,'adapter_name':{'A1':'candidateone','A2':'candidatetwo'}[c],'path':pointers[c]['cache_adapter'],'sha256':pointers[c]['adapter_sha256']} for c in ['A1','A2'])],'selection_sha256':sha(DATA/'native-selection-private.json')}
  product=json.loads((DATA/'controls/receipt.json').read_text())['GPU'].replace(' ','-');nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];eligible=eligible_nodes(nodes,[product],placement['region']);assert eligible;write(dest/'gpu-freeze.json',cfg);print(json.dumps(submit_pilot(NAME,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg),**modules},{'cpu':'2','memory':'16Gi','ephemeral-storage':'24Gi','nvidia.com/gpu':'1'},cache=True,readonly=False,cache_claim=placement['claim'],cache_region=placement['region'],gpu_products=[product],node_names=eligible,binary_files={'inputs.json.gz':raw},runtime=7200)),flush=True)
 if not (d/'host.json').exists():
  from kali_qwen_submission_recovery_20261115 import recover
  recover(NAME)
 audit=json.loads((DATA/'confirmation-eligibility-audit.json').read_text());audit.update(protected_confirmation_model_queries=None,query_count_status='SUBMITTED_ACTUAL_COUNTER_PENDING_COLLECTION');write(DATA/'confirmation-eligibility-audit.json',audit)
 deadline=time.monotonic()+9400;last=None
 while time.monotonic()<deadline:
  state=poll(NAME);log=(d/'worker.log').read_text() if (d/'worker.log').exists() else '';lines=[x for x in log.splitlines() if x.startswith(('TWO_MODEL_INFER ','TWO_MODEL_STAGED '))];current=(state['status'],lines[-1] if lines else 'setup')
  if current!=last:print('CONFIRM384 '+json.dumps(current),flush=True);last=current
  if state['status']=='FAILED':raise RuntimeError('Confirmation compute failed;preserve outputs,never silently repeat queried cases')
  if state['status']=='SUCCEEDED':
   assert 'CONFIRMATION_COMPLETE' in log;found=[x.split('=',1)[1] for x in log.splitlines() if x.startswith('TWO_MODEL_ARTIFACT=')];assert len(found)==1;result=json.loads(gzip.decompress(base64.b64decode(found[0],validate=True)));r=result['receipt'];cfg=json.loads((dest/'gpu-freeze.json').read_text());assert r['status']=='QWEN_CONFIRMATION_COMPLETE' and r['models']['qwen']['optimizer_steps']==0 and r['worker_sha256']==cfg['worker_sha256'] and r['confirmation_model_queries']==1536 and r['inputs_sha256']==cfg['inputs_sha256'] and r['GPU']==json.loads((DATA/'controls/receipt.json').read_text())['GPU'];assert all(a['exact_load_audit']['exact_source_equality'] for a in r['models']['qwen']['adapters']);assert r['diagnostic_model_queries']==32;write(dest/'receipt.json',r);write(dest/'predictions-private.json',{a:rr for a,rr in result['predictions'].items() if len(rr)==384});write(dest/'diagnostic-predictions-private.json',{a:rr for a,rr in result['predictions'].items() if len(rr)==4});audit=json.loads((DATA/'confirmation-eligibility-audit.json').read_text());audit.update(protected_confirmation_rows_read=384,protected_gold_rows_read=384,protected_confirmation_model_queries=1536,adaptive_DEV_diagnostic_model_queries=32,query_count_status='ALL1536_PROTECTED_AND32_DEV_DIAGNOSTIC_RESPONSES_COLLECTED');write(DATA/'confirmation-eligibility-audit.json',audit);cleanup(NAME);break
  time.sleep(20)
 else:raise TimeoutError('Confirmation bounded queue/compute window')

def score():
 compute();dest=DATA/'confirmation384';pred=json.loads((dest/'predictions-private.json').read_text());fixtures=json.loads((dest/'fixtures-private.json').read_text());refs=json.loads((dest/'references-private.json').read_text());sc=native_kali();native={};detail={}
 for label,rr in pred.items():
  assert len(rr)==384 and {r['id'] for r in rr}==set(refs);values=[];detail[label]={}
  for r in rr:
   v=sc.score_one(refs[r['id']],r['response']);strict=not r['truncated'] and bool(strict_option_values(refs[r['id']],r['response'],sc));item={'native':v['total_score'],'strict':strict,'truncated':r['truncated'],'early_EOS':r['early_EOS_first_two']};detail[label][r['id']]=item;values.append(item)
  native[label]={'native_points':sum(x['native'] for x in values)/384*100,'strict':sum(x['strict'] for x in values),'truncated':sum(x['truncated'] for x in values),'early_EOS':sum(x['early_EOS'] for x in values),'rows':384}
 result=cpu(fixtures,pred,'confirm-models');summary={'status':'POST_SELECTION_CONFIRM384_COMPLETE_NO_RESELECTION','freeze':json.loads((dest/'freeze.json').read_text()),'native':native,'behavior':bounds(fixtures,result),'model_queries':1536,'additional_adaptive_DEV_guard_diagnostic_queries':32,'new_optimizer_updates':0,'official_TEST_queries':0,'selection_unchanged':sha(DATA/'native-selection-private.json')==json.loads((dest/'freeze.json').read_text())['selection_sha256'],'actual_GPU':json.loads((dest/'receipt.json').read_text())['GPU']};assert summary['selection_unchanged'];write(dest/'native-details-private.json',detail);write(dest/'summary.json',summary);print('CONFIRM384_COMPLETE '+json.dumps(summary),flush=True)
if __name__=='__main__':score()
