#!/usr/bin/env python3
"""Future synthetic DEV entrypoint: explicit contract-v2, no official/test loader."""
import argparse,json
from pathlib import Path
from benchkit import native_kali
from kali_command_contract import compare_command

def score_rows(rows,predictions,extract_command):
 gold={r['id']:r for r in rows};actual={r['id']:r for r in predictions}
 if len(gold)!=len(rows) or len(actual)!=len(predictions) or set(gold)!=set(actual):raise ValueError('Missing/duplicate/extraIDs;no silent subset scoring')
 if any(r.get('split')!='dev' or r.get('training_eligible') is not False or r.get('official_test') is not False for r in rows):raise ValueError('Only explicitly non-training synthetic DEV allowed')
 details=[]
 for i,r in gold.items():
  p=actual[i];v=compare_command(extract_command(p['response']),r);details.append({'id':i,'correct':bool(v['correct'] and not p.get('truncated') and not p.get('error')),'status':v['status']})
 return {'metric':'reviewed-command-contract-v2','rows':len(rows),'correct':sum(r['correct'] for r in details),'unsupported_rows':sum(r['status']=='UNSUPPORTED' for r in details),'official_metric':False,'details':details}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--policy',required=True,choices=['reviewed-command-contract-v2']);parser.add_argument('--rows',required=True);parser.add_argument('--predictions',required=True);parser.add_argument('--arm',required=True);parser.add_argument('--output',required=True);a=parser.parse_args();rows=[json.loads(s) for s in Path(a.rows).read_text().splitlines()];p=json.loads(Path(a.predictions).read_text())['predictions'][a.arm];sc=native_kali();out=score_rows(rows,p,sc.extract_command_from_output);target=Path(a.output)
 if target.exists():raise ValueError('No rewriting historical scores')
 target.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='details'}))

if __name__=='__main__':main()
