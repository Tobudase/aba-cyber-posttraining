#!/usr/bin/env python3
"""Public fixed-recipe client. GPU execution is constrained by the host broker."""
import json,os,sys,urllib.request
from pathlib import Path
URL='http://127.0.0.1:18742/v1/frozen'
def call(action):
 req=urllib.request.Request(URL,data=json.dumps({'action':action}).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=2100) as response:return json.load(response)
def train(output):
 p=Path(output);p.mkdir(parents=True,exist_ok=True);result=call('train')
 (p/'final_model').mkdir(exist_ok=True);(p/'final_model/model.json').write_text(json.dumps(result['pointer'],indent=2)+'\n')
 (p/'train_metrics.json').write_text(json.dumps(result['training_receipt'],indent=2)+'\n')
 (p/'run.py').write_bytes(Path(__file__).read_bytes())
 (p/'README.md').write_text('Frozen CUDA 8B LoRA engineering integration. Model pointer references private persistent adapter; no weights redistributed. One candidate, no generated data or adaptive search.\n')
 return {'status':'REAL_GPU_TRAINING_COMPLETE','optimizer_steps':result['training_receipt']['optimizer_steps'],'adapter_sha256':result['pointer']['adapter_sha256']}
if __name__=='__main__':
 if len(sys.argv)==2 and sys.argv[1]=='health':print(json.dumps(call('health')))
 else:print(json.dumps(train(os.environ['OUTPUT_DIR'])))
