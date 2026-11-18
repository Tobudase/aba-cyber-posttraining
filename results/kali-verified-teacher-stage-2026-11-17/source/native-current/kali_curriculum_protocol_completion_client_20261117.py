"""Revalidate two real existing native-trained adapters; zero new optimization."""
import argparse,base64,gzip,hashlib,json,os,time,urllib.request,urllib.error
from pathlib import Path
URL='http://127.0.0.1:29847/candidate'
ARTIFACT_README='Native protocol completion: A1 and A2 are existing original-native-dispatched adapters, each with32 actual prior updates and0new updates in this completion run. Exact reload checked; original versus current update counts are explicit in train_metrics.json. Internal diagnostics only; official TEST untouched.\n'
def call(req,timeout=100):
 r=urllib.request.Request(URL,data=json.dumps(req).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=timeout) as response:x=json.load(response)
 if x.get('status')=='FAILED':raise RuntimeError(str(x))
 return x
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['health','export-train','submit','wait','finalize']);p.add_argument('--candidate',choices=['A1','A2']);p.add_argument('--lr',type=float,choices=[5e-6,1e-5,2e-5]);p.add_argument('--seconds',type=int,default=420);a=p.parse_args()
 if a.action=='health':r=call({'action':'health'})
 elif a.action=='export-train':
  m=Path(os.environ['DATA_DIR'])/'training_manifest.json';meta=json.loads(m.read_text());r=call({'action':'train_data','manifest_sha256':hashlib.sha256(m.read_bytes()).hexdigest()});raw=gzip.decompress(base64.b64decode(r['train_gzip_base64'],validate=True));assert hashlib.sha256(raw).hexdigest()==meta['train_encoded_sha256'] and len(json.loads(raw))==meta['training_rows']
  out=Path(os.environ['OUTPUT_DIR']);out.mkdir(parents=True,exist_ok=True);(out/'train-encoded.json').write_bytes(raw);r={'status':'TRAIN_ONLY_EXPORTED','rows':meta['training_rows'],'DEV_rows':0}
 else:
  assert a.candidate
  if a.action=='submit':
   assert a.lr;manifest=Path(os.environ['DATA_DIR'])/'training_manifest.json';r=call({'action':'submit','candidate_id':a.candidate,'learning_rate':a.lr,'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
  else:
   assert 0<=a.seconds<=480;deadline=time.monotonic()+(a.seconds if a.action=='wait' else 0)
   while True:
    try:r=call({'action':'status','candidate_id':a.candidate},timeout=min(80,max(1,deadline-time.monotonic())) if a.action=='wait' else 80)
    except (TimeoutError,urllib.error.URLError):
     if time.monotonic()>=deadline:
      if a.action=='wait':
       r={'status':'IN_PROGRESS','candidate_id':a.candidate,'transport_state':'UNAVAILABLE','completion_unverified':True};break
      raise
     time.sleep(min(5,max(0,deadline-time.monotonic())));continue
    if r['status']!='IN_PROGRESS' or time.monotonic()>=deadline:break
    time.sleep(min(20,max(0,deadline-time.monotonic())))
  if a.action=='finalize':
   assert r['status']=='REAL_GPU_TRAINING_COMPLETE';receipt=r['training_receipt'];assert receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==json.loads((Path(os.environ['DATA_DIR'])/'training_manifest.json').read_text())['max_updates_each'] and receipt['reload_probe_identical']
   expected_new=json.loads((Path(os.environ['DATA_DIR'])/'training_manifest.json').read_text())['current_run_updates_by_candidate'][a.candidate];assert receipt['new_optimizer_steps_in_current_native_run']==expected_new
   out=Path(os.environ['OUTPUT_DIR']);(out/'final_model').mkdir(parents=True,exist_ok=True);(out/'final_model/model.json').write_text(json.dumps(r['pointer'],indent=2)+'\n');(out/'train_metrics.json').write_text(json.dumps(receipt,indent=2)+'\n');(out/'run.py').write_bytes(Path(__file__).read_bytes());(out/'README.md').write_text(ARTIFACT_README);r={'status':'ARTIFACTS_WRITTEN','candidate_id':a.candidate,'new_optimizer_steps_in_current_native_run':receipt['new_optimizer_steps_in_current_native_run'],'optimizer_steps_in_adapter':receipt['optimizer_steps']}
 if a.action=='wait' and r.get('status')=='REAL_GPU_TRAINING_COMPLETE':r={k:v for k,v in r.items() if k!='training_receipt'}
 print(json.dumps(r))
if __name__=='__main__':main()
