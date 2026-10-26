#!/usr/bin/env python3
"""Verify eight released TRAIN fixtures; optional Linux gold-command replay."""
import argparse,hashlib,json,os,platform,subprocess,tempfile
from pathlib import Path

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');a=parser.parse_args();r=Path(__file__).resolve().parents[1];d=r/'data/benchkit/kali-verified-sft-v1';m=json.loads((d/'manifest.json').read_text());train={x['id']:x for x in [json.loads(t) for t in (d/'train.jsonl').read_text().splitlines()]};cases=json.loads((d/'examples/cases.json').read_text())['cases'];assert len(cases)==8 and len({x['tool'] for x in cases})==8
 for name,digest in m['released_data_sha256'].items():assert hashlib.sha256((d/name).read_bytes()).hexdigest()==digest
 checked=executed=0
 if a.execute and platform.system()!='Linux':raise ValueError('Linux tool versions required;default file check works without Linux')
 for case in cases:
  assert case['id'] in train and case['argv']==train[case['id']]['gold_argv'] and case['tool']==case['argv'][0];assert case['tool'] in ['wc','head','tail','grep','jq','openssl','tshark','tcpdump'];name=case['filename'];assert Path(name).name==name;body=(d/'examples'/name).read_bytes();assert hashlib.sha256(body).hexdigest()==case['fixture_sha256'];checked+=1
  if a.execute:
   with tempfile.TemporaryDirectory() as td:
    cwd=Path(td);(cwd/name).write_bytes(body);env={**os.environ,'LC_ALL':'C.UTF-8','TZ':'UTC','HOME':str(cwd)};result=subprocess.run(case['argv'],cwd=cwd,capture_output=True,timeout=12,env=env);assert result.returncode==0 and hashlib.sha256(result.stdout).hexdigest()==case['expected_stdout_sha256'],'Gold replay differs;check recorded Linux tool versions';executed+=1
 print(json.dumps({'status':'PASS_PUBLIC_TRAIN_FIXTURES','fixture_files_checked':checked,'Linux_gold_commands_executed':executed,'model_calls':0,'GPU_allocations':0,'confirmation_bodies_read':0}))

if __name__=='__main__':main()
