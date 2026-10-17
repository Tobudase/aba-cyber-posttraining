#!/usr/bin/env python3
"""Count native Qwen chat tokens on held intake; never create training data."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model-key',choices=['qwen14_model','qwen38_model'],default='qwen14_model')
args=parser.parse_args()
directory=ROOT/'.tools/cti-review'/args.model_key
candidate=json.loads((ROOT/'configs/cti-candidates.lock.json').read_text())['models'][args.model_key]
manifest=json.loads((ROOT/'configs/cti-reviewed-files.lock.json').read_text())
expected=manifest[args.model_key+'/tokenizer.json']['sha256']
assert hashlib.sha256((directory/'tokenizer.json').read_bytes()).hexdigest()==expected
tokenizer=AutoTokenizer.from_pretrained(directory,local_files_only=True,trust_remote_code=False)
source=ROOT/'data/raw/cti-nvd-week/candidates.jsonl'
rows=[json.loads(x) for x in source.read_text().splitlines()]
lengths=[];prompt_lengths=[]
start=time.monotonic()
for row in rows:
    assert row['status']=='HOLD_RESEARCH_REVIEW' and not row['training_eligible']
    user='Classify the primary software weakness described below. Reply with exactly one CWE identifier, with no explanation.\n\n'+row['description']
    prompt_text=tokenizer.apply_chat_template([{'role':'user','content':user}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    complete_text=tokenizer.apply_chat_template([{'role':'user','content':user},{'role':'assistant','content':row['label']}],tokenize=False,add_generation_prompt=False,enable_thinking=False)
    assert isinstance(prompt_text,str) and isinstance(complete_text,str)
    # Transformers5 may return a mapping from apply_chat_template(tokenize=True).
    # Render then encode explicitly, so len() counts IDs rather than mapping keys.
    prompt=tokenizer.encode(prompt_text,add_special_tokens=False)
    complete=tokenizer.encode(complete_text,add_special_tokens=False)
    assert isinstance(prompt,list) and isinstance(complete,list)
    assert all(type(t) is int for t in prompt+complete) and len(prompt)>20
    # Length analysis only: no loss mask, optimizer, training eligibility or split is implied.
    prompt_lengths.append(len(prompt));lengths.append(len(complete))
def stats(values):
    return {'min':int(min(values)),'median':float(np.median(values)),'p95':float(np.percentile(values,95)),
            'max':int(max(values)),'total':int(sum(values)),
            'records_over_tokens':{str(cap):sum(x>cap for x in values) for cap in [256,512,1024,2048]}}
result={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASSED_LENGTH_ANALYSIS_ONLY',
        'model_id':candidate['id'],'revision':candidate['revision'],
        'tokenizer_sha256':expected,'records':len(rows),
        'intake_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'enable_thinking':False,'input_prompt_tokens':stats(prompt_lengths),
        'complete_label_only_chat_tokens':stats(lengths),
        'elapsed_seconds':time.monotonic()-start,'remote_code':False,
        'official_test_rows':0,'training_data_created':False,'model_weights_loaded':False,
        'limitations':['Classification-only, non-reasoning candidate template; research protocol not frozen.',
                       'These token counts do not measure GPU memory or training throughput.',
                       'All source descriptions and labels remain held for independent review.']}
(ROOT/f'docs/verification/cti-{args.model_key.removesuffix("_model")}-context-lengths.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
