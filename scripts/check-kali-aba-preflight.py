#!/usr/bin/env python3
"""Read-only readiness probe through SSH and pinned native ABA bwrap; no LLM."""
import json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from kali_cuda_jobs import ROOT,canonical,frozen,sha
from benchkit import write_json
REMOTE=r'''
import hashlib,json,pathlib,sys,subprocess,urllib.request
r=pathlib.Path('/home/minhao/kali-aba-cuda-20261023');m=json.loads((r/'task/manifest.json').read_text())
assert all(hashlib.sha256((r/'task'/f).read_bytes()).hexdigest()==h for f,h in m['files'].items())
sys.path.insert(0,'/home/minhao/aba-synthetic-20261016/source/aibuildai-llm-posttrain-agent')
from config import AgentConfig
from infra.sandbox.bwrap import build_bwrap_argv
c=AgentConfig.model_validate_json((r/'task-config.json').read_text())
code="import urllib.request,json; q=urllib.request.Request('http://127.0.0.1:18742/v1/frozen',data=b'{\"action\":\"health\"}',headers={'Content-Type':'application/json'},method='POST'); print(urllib.request.urlopen(q,timeout=10).read().decode())"
args=['bwrap']+build_bwrap_argv([],[],hard_ro=['/usr','/etc'])+['--','/usr/bin/python3','-c',code]
p=subprocess.run(args,capture_output=True,text=True,timeout=20)
if p.returncode:raise SystemExit('Pinned bwrap bridge health failed')
print(json.dumps({'status':'PASS','manifest':m,'native_config_schema_valid':True,'sandbox_enabled':c.resources.sandbox.enable,'native_bwrap_health':json.loads(p.stdout),'task_manifest_dev_or_test_files':sum('dev' in n or 'test' in n for n in m['files']),'TRAIN_rows':len((r/'task/train.jsonl').read_text().splitlines()),'native_ABA_started':(r/'native-run.log').exists(),'GPU_jobs_triggered':0,'source_bwrap_sha256':hashlib.sha256(pathlib.Path('/home/minhao/aba-synthetic-20261016/source/aibuildai-llm-posttrain-agent/infra/sandbox/bwrap.py').read_bytes()).hexdigest()}))
'''
def main():
 p,_=frozen()
 r=subprocess.run(['bash',str(ROOT/'scripts/vm-ssh.sh'),'--local-ssh-opts=-R 127.0.0.1:18742:127.0.0.1:18741','--local-ssh-opts=-o ExitOnForwardFailure=yes','--command','/home/minhao/aba-synthetic-20261016/manager/bin/python -'],input=REMOTE,capture_output=True,text=True,timeout=60)
 if r.returncode:raise SystemExit('Remote readiness check failed; raw output withheld')
 result=json.loads(r.stdout);assert result['native_bwrap_health']['protocol_sha256']==sha(canonical(p))
 result.update(checked_at_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=sha(canonical(p)),scope='Native config and bwrap emitter connectivity preflight, not a full ABA role-policy or training run.')
 write_json(ROOT/'docs/verification/kali-cuda-aba-preflight.json',result)
 print(json.dumps({k:result[k] for k in ['status','native_config_schema_valid','sandbox_enabled','TRAIN_rows','native_ABA_started','GPU_jobs_triggered','protocol_sha256']}))
if __name__=='__main__':main()
