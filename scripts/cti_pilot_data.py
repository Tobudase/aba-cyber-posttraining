"""Strict frozen-pilot loader and assistant-only supervision; no official data."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROMPT='Classify the primary software weakness described below. Reply with exactly one CWE identifier, with no explanation.\n\n'
def sha(b): return hashlib.sha256(b).hexdigest()

def load_pilot(root=ROOT):
    manifest=json.loads((root/'data/manifests/cti-source-pilot-v1.json').read_text())
    if manifest['status']!='FROZEN_EXTERNAL_SOURCE_SILVER_EXPLORATORY_V1':
        raise ValueError('Not a frozen source-silver pilot')
    output={}
    for split in ['train','dev']:
        spec=manifest['artifacts'][split]
        path=root/spec['path']
        if not path.resolve().is_relative_to((root/'data/raw/cti-pilot-v1').resolve()):
            raise ValueError('Path outside explicitly allowed external pilot')
        raw=path.read_bytes()
        if sha(raw)!=spec['sha256']: raise ValueError('Pilot checksum mismatch')
        rows=list(map(json.loads,raw.decode().splitlines()))
        if len(rows)!=spec['rows']: raise ValueError('Pilot row count mismatch')
        for r in rows:
            if r['split']!=split or r['official_benchmark'] or r['label_quality']!='SOURCE_SILVER_ASSISTANT_REVIEWED':
                raise ValueError('Invalid pilot provenance or split')
            if r['training_eligible']!=(split=='train'): raise ValueError('Incorrect training eligibility')
        output[split]=rows
    for key in ['id','group_id','description']:
        if {r[key] for r in output['train']}&{r[key] for r in output['dev']}:
            raise ValueError('Train/dev overlap: '+key)
    return manifest,output

def encode_row(tokenizer,row,max_tokens=1024):
    messages=[{'role':'user','content':PROMPT+row['description']}]
    prefix=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
    full=tokenizer.apply_chat_template(messages+[{'role':'assistant','content':row['label']}],tokenize=False,add_generation_prompt=False,enable_thinking=False)
    if not isinstance(prefix,str) or not isinstance(full,str) or not full.startswith(prefix):
        raise ValueError('Chat template does not preserve prompt prefix')
    p=tokenizer.encode(prefix,add_special_tokens=False)
    ids=tokenizer.encode(full,add_special_tokens=False)
    if ids[:len(p)]!=p or len(ids)<=len(p): raise ValueError('Missing assistant target or token prefix mismatch')
    if len(ids)>max_tokens: raise ValueError('Sequence exceeds cap; silent truncation forbidden')
    labels=[-100]*len(p)+ids[len(p):]
    if not any(x!=-100 for x in labels): raise ValueError('All targets masked')
    return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':labels,'prompt_tokens':len(p)}
