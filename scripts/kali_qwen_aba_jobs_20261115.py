"""Fresh original-Qwen candidate backend; frozen metric and bounded GPU/CPU Jobs."""
import base64,datetime,gzip,hashlib,json,math,subprocess,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,poll,cleanup,write,BASE
from kali_two_model_submit_20261115 import submit_pilot
from kali_qwen_validation_cpu_20261115 import run as behavior
from kali_qwen_aba_grade_20261115 import grade
from benchkit import native_kali,strict_option_values
DATA=ROOT/'data/benchkit/kali-qwen-aba-validation-2026-11-15';FIXED=ROOT/'data/benchkit/kali-two-model-sft-2026-11-15';CLAIM='miw113-kali-two-model-cache-1115'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def native(pred):
 refs=json.loads((DATA/'references-private.json').read_text());sc=native_kali();details={}
 for a,rr in pred.items():
  if len(rr)!=110:continue
  assert len(rr)==110 and {r['id'] for r in rr}==set(refs)
  details[a]={}
  for r in rr:
   v=sc.score_one(refs[r['id']],r['response']);details[a][r['id']]={'native':v['total_score'],'strict':not r['truncated'] and bool(strict_option_values(refs[r['id']],r['response'],sc)),'format_error':bool(v['format_error']),'truncated':r['truncated'],'early_EOS':r['early_EOS_first_two'],'generated_tokens':r['generated_tokens']}
 return details

def run(label,lr=None):
 assert label=='controls' and lr is None or label in ['A1','A2'] and lr in [1e-5,3e-5,5e-5]
 dest=DATA/label;dest.mkdir(exist_ok=True)
 if (dest/'score.json').exists():return json.loads((dest/'score.json').read_text())
 name='miw113-qwen-aba-'+label.lower()+'-1115';jobdir=OUT/name
 placement=json.loads((DATA/'placement-amendment-private.json').read_text());claim=placement.get('claim',CLAIM);region=placement.get('region','us-west');products=placement['allowed_products'] if label=='controls' else [json.loads((DATA/'controls/receipt.json').read_text())['GPU'].replace(' ','-')]
 if region=='us-central':assert json.loads((DATA/'central-stage-audit.json').read_text())['claim']==claim,'No GPU before completed verified regional CPU staging'
 freeze=json.loads((DATA/'launch-freeze.json').read_text());assert all(sha(DATA/n)==h for n,h in freeze['data_sha256'].items());assert sha(ROOT/'scripts/kali_qwen_aba_grade_20261115.py')==freeze['score_sha256']
 assert json.loads((DATA/'controls-audit.json').read_text())['fixture_count']==46
 if not all((dest/n).exists() for n in ['receipt.json','predictions-private.json','native-details-private.json']):
  if not jobdir.exists():
   model_protocol=json.loads((FIXED/'model-protocols.json').read_text())['qwen'];model_protocol['allowed_GPU_models']=model_protocol['allowed_GPU_models']+['NVIDIA A10'];rows=json.loads((DATA/'eval-inputs-private.json').read_text());prior=json.loads(gzip.decompress((FIXED/'gpu-inputs.json.gz').read_bytes()))
   payload={'panels':{'new_dev46':rows[:46],'old64':rows[46:]},'encoded':{'qwen':json.loads((DATA/'train-encoded-private.json').read_text())},'epoch_orders':prior['epoch_orders'][:2]};raw=gzip.compress(json.dumps(payload,separators=(',',':')).encode(),mtime=0)
   names=['kali_command_ngram_guard_20261115.py','kali_stable_objective_20261114.py','kali_exact_adapter_loading_20261115.py'];modules={n:(ROOT/'scripts'/n).read_text() for n in names};worker=ROOT/'scripts/kali_qwen_aba_worker_20261115.py'
   cfg={'mode':'controls' if label=='controls' else 'train','learning_rate':lr,'model_protocols':{'qwen':model_protocol},'worker_sha256':sha(worker),'inputs_sha256':hashlib.sha256(raw).hexdigest(),'module_sha256':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in modules.items()},'durable_output':'/cache/kali-qwen-aba-20261115/'+label,'fixed_adapter':'/cache/kali-two-model-sft-20261115/miw113-kali-two-model-sft-r3-1115/qwen_step256/adapter','fixed_adapter_sha256':json.loads((DATA/'protocol.json').read_text())['fixed_comparator']['weights_sha256'],'protocol_sha256':sha(DATA/'protocol.json')}
   from kali_qwen_gpu_placement_20261115 import eligible_nodes
   nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];eligible=eligible_nodes(nodes,products,region)
   assert eligible,'No ordinary Ready same-product host; no unauthorized fallback'
   write(dest/'gpu-freeze.json',{'config':cfg,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'eligible_nodes':eligible,'max_new_updates':0 if label=='controls' else 128})
   print(json.dumps(submit_pilot(name,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg),**modules},{'cpu':'2','memory':'16Gi','ephemeral-storage':'24Gi','nvidia.com/gpu':'1'},cache=True,readonly=False,cache_claim=claim,cache_region=region,gpu_products=products,node_names=eligible,binary_files={'inputs.json.gz':raw},runtime=5400)),flush=True)
  if not (jobdir/'host.json').exists():
   from kali_qwen_submission_recovery_20261115 import recover
   recover(name)
  deadline=time.monotonic()+7400;last=None
  while time.monotonic()<deadline:
   try:state=poll(name)
   except Exception as e:print('GPU_API_RETRY '+type(e).__name__,flush=True);time.sleep(10);continue
   log=(jobdir/'worker.log').read_text() if (jobdir/'worker.log').exists() else ''
   lines=[x for x in log.splitlines() if x.startswith(('TWO_MODEL_STAGED ','TWO_MODEL_INFER ','TWO_MODEL_TRAIN ','TWO_MODEL_ARM_COMPLETE '))];current=(state['status'],lines[-1] if lines else 'queue/setup')
   if current!=last:print(json.dumps({'label':label,'state':current,'node':state.get('node')}),flush=True);last=current
   if state['status']=='FAILED':raise RuntimeError('GPU failed; preserve original partial artifacts '+str(jobdir))
   if state['status']=='SUCCEEDED':
    found=[x.split('=',1)[1] for x in log.splitlines() if x.startswith('TWO_MODEL_ARTIFACT=')];assert len(found)==1
    artifact=json.loads(gzip.decompress(base64.b64decode(found[0],validate=True)));r=artifact['receipt'];cfg=json.loads((dest/'gpu-freeze.json').read_text())['config'];assert r['worker_sha256']==cfg['worker_sha256'] and r['inputs_sha256']==cfg['inputs_sha256'] and r['GPU'].replace(' ','-') in products
    if label!='controls':assert r['models']['qwen']['optimizer_steps']==r['models']['qwen']['nonzero_gradient_steps']==128 and r['models']['qwen']['reload_complete_responses_identical']
    write(dest/'receipt.json',r);write(dest/'predictions-private.json',artifact['predictions']);write(dest/'native-details-private.json',native(artifact['predictions']));cleanup(name);break
   time.sleep(20)
  else:raise TimeoutError('Bounded GPU backend deadline')
 pred=json.loads((dest/'predictions-private.json').read_text());dd=json.loads((dest/'native-details-private.json').read_text());beh=behavior({a:rr for a,rr in pred.items() if len(rr)==110},'paired-controls' if label=='controls' else label.lower());meta=json.loads((DATA/'grading-metadata-private.json').read_text())
 if label=='controls':base=dd['qwen_base'];basebeh=beh['details']['qwen_base']
 else:
  base=json.loads((DATA/'controls/native-details-private.json').read_text())['qwen_base'];basebeh=json.loads((DATA/'paired-controls-behavior-private.json').read_text())['details']['qwen_base'];assert pred['qwen_base']==json.loads((DATA/'controls/predictions-private.json').read_text())['qwen_base'],'Fresh E0 differs: no claim of numerical identity; investigate before selecting'
 grades={a:grade(meta,d,beh['details'][a],base,basebeh) for a,d in dd.items() if a in beh['details']};write(dest/'score.json',grades)
 if label!='controls':
  r=json.loads((dest/'receipt.json').read_text());cfg=json.loads((dest/'gpu-freeze.json').read_text())['config']
  cp=r['models']['qwen']['checkpoints']['qwen_step128'];write(dest/'adapter-pointer-private.json',{'candidate_id':label,'model_id':'Qwen/Qwen3-8B','model_revision':cfg['model_protocols']['qwen']['model_revision'],'adapter_sha256':cp['weights_sha256'],'optimizer_steps':128,'protocol_sha256':sha(DATA/'protocol.json'),'cache_adapter':cfg['durable_output']+'/qwen_step128/adapter'})
 print('QWEN_BACKEND_SCORED '+label+' '+json.dumps(grades),flush=True);return grades
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('label',choices=['controls','A1','A2']);p.add_argument('--lr',type=float);a=p.parse_args();run(a.label,a.lr)
