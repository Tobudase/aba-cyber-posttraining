#!/usr/bin/env python3
"""Opt-in TRAIN-target envelope conversion. Never changes commands or inference.

This implements the researched treatment, not a guarantee of benchmark gains.
Original datasets and scoring must remain immutable for historical reproduction.
"""
import argparse,copy,json,re
from pathlib import Path

def newline_target(target):
    if not isinstance(target,str):raise TypeError('target must be text')
    match=re.fullmatch(r'<output>\s*([^\n\r]+?)\s*</output>',target)
    if not match:raise ValueError('Expected one nonempty command inside one output envelope')
    command=match.group(1).strip()
    if not command or '<output>' in command or '</output>' in command:raise ValueError('Expected one nonempty command and one envelope')
    return '<output>\n'+command+'\n</output>'

def convert_train_row(row):
    if row.get('official_test') or row.get('training_eligible') is False or row.get('split') in {'test','dev_search','dev_confirm','validation'}:
        raise ValueError('Only explicitly eligible TRAIN rows may be transformed')
    if row.get('split')!='train' or row.get('training_eligible') is not True:raise ValueError('Explicit TRAIN eligibility required')
    result=copy.deepcopy(row);result['target']=newline_target(row['target']);return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.input.resolve()==args.output.resolve() or args.output.exists():raise SystemExit('Refuse overwriting original or existing data')
    rows=[json.loads(line) for line in args.input.read_text().splitlines() if line.strip()];converted=[convert_train_row(row) for row in rows]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:
        for row in converted:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps({'rows':len(rows),'changed_field':'target only','original_file_preserved':True,'inference_and_scorer_unchanged':True,'note':'Freeze new manifest/data hashes and rerun token-boundary audit before training. Target token count/loss weighting change.'}))
if __name__=='__main__':main()
