#!/usr/bin/env python3
"""Execute only the preregistered 8B recipes; asynchronous GPU queue and training."""
import argparse,base64,gzip,hashlib,json,os,urllib.request
from pathlib import Path
URL='http://127.0.0.1:29847/candidate'
def call(req):
 r=urllib.request.Request(URL,data=json.dumps(req).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=100) as s:result=json.load(s)
 if result.get('status')=='FAILED':raise RuntimeError('Backend failed: '+result.get('error_type','unknown'))
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['health','export-train','submit','wait','finalize']);p.add_argument('--candidate',choices=['P13','P14']);a=p.parse_args()
 if a.action=='health':result=call({'action':'health'})
 elif a.action=='export-train':
  manifest=Path(os.environ['DATA_DIR'])/'training_manifest.json';metadata=json.loads(manifest.read_text());result=call({'action':'train_data','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()});raw=gzip.decompress(base64.b64decode(result['train_gzip_base64'],validate=True));assert hashlib.sha256(raw).hexdigest()==metadata['train_encoded_sha256'];rows=json.loads(raw);assert len(rows)==733 and all(r['split']=='train' and r['official_test'] is False for r in rows)
  out=Path(os.environ['OUTPUT_DIR']);out.mkdir(parents=True,exist_ok=True);(out/'train-encoded.json').write_bytes(raw);result={'status':'TRAIN_DATA_EXPORTED','rows':733,'train_sha256':metadata['train_encoded_sha256'],'DEV_rows':0}
 else:
  assert a.candidate,'Explicit frozen recipe required'
  if a.action=='submit':
   manifest=Path(os.environ['DATA_DIR'])/'training_manifest.json'
   result=call({'action':'submit','candidate_id':a.candidate,'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
  else:result=call({'action':'status','candidate_id':a.candidate})
  if a.action=='finalize':
   assert result['status']=='REAL_GPU_TRAINING_COMPLETE','Wait for actual optimizer updates and verified adapter collection'
   r=result['training_receipt'];assert r['optimizer_steps']==r['nonzero_gradient_steps']==733 and r['changed_tensors']>0 and r['adapter_reload_max_logit_delta']<=1e-4
   out=Path(os.environ['OUTPUT_DIR']);(out/'final_model').mkdir(parents=True,exist_ok=True)
   (out/'final_model/model.json').write_text(json.dumps(result['pointer'],indent=2)+'\n')
   (out/'train_metrics.json').write_text(json.dumps(r,indent=2)+'\n');(out/'run.py').write_bytes(Path(__file__).read_bytes())
   (out/'README.md').write_text('Real native ABA-dispatched 8B LoRA candidate. The adapter was recovered and SHA256 verified by the host. Internal TRAIN-derived DEV only; official TEST untouched.\n')
   result={'status':'ARTIFACTS_WRITTEN','candidate_id':a.candidate,'adapter_sha256':result['pointer']['adapter_sha256'],'optimizer_steps':733}
 print(json.dumps(result))
if __name__=='__main__':main()
