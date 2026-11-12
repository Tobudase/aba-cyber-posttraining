#!/usr/bin/env python3
"""Verify dataset hashes, source recipes, paired checks, and optional fresh run."""
import argparse,hashlib,importlib.util,json,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--runtime-receipt',type=Path);args=p.parse_args()
 d=ROOT/'results/kali-behavior-train-2026-11-12';train=ROOT/'data/kali-behavior-train-2026-11-12/train.jsonl';worker=ROOT/'scripts/kali-behavior-fixture-worker-v2-20261112.py'
 m=json.loads((d/'manifest.json').read_text());checks={r['id']:r for r in json.loads((d/'checks.json').read_text())['candidate_checks']}
 assert hashlib.sha256(train.read_bytes()).hexdigest()==m['train_sha256']
 assert hashlib.sha256(worker.read_bytes()).hexdigest()==m['fixture_program_sha256']
 spec=importlib.util.spec_from_file_location('fixtures',worker);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 recipes={f'kali-fixture-{t}-{k}-{v}':(q,shlex.join(cmd)) for t,k,v,q,cmd,bad in mod.cases()}
 rows=list(map(json.loads,train.open()));assert len(rows)==len({r['id'] for r in rows})==64
 for r in rows:
  assert r['training_eligible'] and not r['official_test'] and r['split']=='train'
  assert recipes[r['id']]==(r['native_label']['query'],r['native_label']['ground_truth_command'])
  c=checks[r['id']];assert c['admitted'] and c['reference_behavior_pass'] and c['mutation_rejected']
 assert len({r['template_family'] for r in rows})==32
 if args.runtime_receipt:
  x=json.loads(args.runtime_receipt.read_text());x=x.get('result',x);fresh={r['id']:r for r in x['receipts']}
  for r in rows:
   f=fresh[r['id']];assert f['admitted'] and f['reference']['oracle_pass'] and not f['mutation']['oracle_pass']
 print(json.dumps({'status':'RELEASE_VERIFIED','rows':64,'families':32,'fresh_runtime_checked':bool(args.runtime_receipt)}))
if __name__=='__main__':main()
