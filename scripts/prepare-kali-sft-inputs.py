#!/usr/bin/env python3
"""Encode reviewed TRAIN only; never load DEV/confirmation or invent reasoning."""
import argparse,ast,hashlib,json
from pathlib import Path
from kali_structural_completion import encode_structural_completion

def load_prompt_constants(source):
 names={'SYSTEM_PROMPT_UNRESTRICTED_THINKING','USER_PROMPT_UNRESTRICTED_THINKING_TEMPLATE'};values={}
 for node in ast.parse(source).body:
  if isinstance(node,ast.Assign):
   for target in node.targets:
    if isinstance(target,ast.Name) and target.id in names:
     if target.id in values:raise ValueError('Duplicate prompt constant')
     value=ast.literal_eval(node.value)
     if not isinstance(value,str):raise ValueError('Prompt must be a literal string')
     values[target.id]=value
 if set(values)!=names:raise ValueError('Missing pinned prompt constants')
 return values

def main():
 a=argparse.ArgumentParser();a.add_argument('--train',type=Path,required=True);a.add_argument('--tokenizer',type=Path,required=True);a.add_argument('--prompt-source',type=Path,required=True);a.add_argument('--prompt-sha256',required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
 if args.output.exists():raise ValueError('No overwriting original/encoded data')
 source=args.prompt_source.read_bytes()
 if hashlib.sha256(source).hexdigest()!=args.prompt_sha256:raise ValueError('Pinned prompt source mismatch')
 rows=[json.loads(t) for t in args.train.read_text().splitlines()]
 if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate TRAIN IDs')
 for r in rows:
  if r.get('split')!='train' or r.get('training_eligible') is not True or r.get('official_test') is not False:raise ValueError('Explicit TRAIN only')
 from transformers import AutoTokenizer
 tokenizer=AutoTokenizer.from_pretrained(args.tokenizer,local_files_only=True,trust_remote_code=False,fix_mistral_regex=False);ns=load_prompt_constants(source);encoded=[]
 for r in rows:
  messages=[{'role':'system','content':ns['SYSTEM_PROMPT_UNRESTRICTED_THINKING']},{'role':'user','content':ns['USER_PROMPT_UNRESTRICTED_THINKING_TEMPLATE'].format(query=r['query'])}];value=encode_structural_completion(tokenizer,r,messages,'<output>\n'+r['gold_command']+'\n</output>');encoded.append({'id':r['id'],'split':'train','training_eligible':True,'official_test':False,'TRAIN_fixture_execution_verified':r['TRAIN_fixture_execution_verified'],'TRAIN_explicit_constraints_verified':r['TRAIN_explicit_constraints_verified'],**value})
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with args.output.open('x') as f:json.dump(encoded,f);f.write('\n')
 print(json.dumps({'status':'ENCODED_TRAIN_ONLY','rows':len(encoded),'supervised_tokens':sum(r['target_tokens'] for r in encoded),'maximum_sequence_tokens':max(len(r['input_ids']) for r in encoded),'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'model_calls':0}))

if __name__=='__main__':main()
