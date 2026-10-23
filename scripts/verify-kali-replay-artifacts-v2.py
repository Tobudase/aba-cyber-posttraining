"""Recheck public raw-token/prompt evidence without model generation."""
from pathlib import Path
import argparse,json,re
from benchkit import ROOT,load_jsonl,load_tokenizer,sha,final_text,write_json
from kali_prompt_policy import generation_prompt
from kali_decode_policy import audit_stream_text

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 tok=load_tokenizer('redsage');counts={}
 for arm in ['domain_control','domain_plus_replay']:
  protocol_path=ROOT/f'configs/kali-replay-v2-{arm}.protocol.json';protocol=json.loads(protocol_path.read_text())
  root=ROOT/'docs/verification/kali-replay-v2'/arm
  for phase in ['train','evaluation']:
   receipt=json.loads((root/phase/'receipt.json').read_text());runner=root/phase/'executed-runner.py'
   if receipt['status']!='COMPLETE' or sha(runner.read_bytes())!=protocol['runner_sha256'] or sha(runner.read_bytes())!=receipt['runner_sha256']:raise ValueError('Executed runner mismatch')
   if sha((root/phase/'frozen-protocol.json').read_bytes())!=sha(protocol_path.read_bytes()):raise ValueError('Protocol snapshot mismatch')
  for name,check in protocol['evaluation'].items():
   spec=json.loads((ROOT/check['manifest']).read_text());part=spec['splits'][check['split']]
   rows=load_jsonl((ROOT/check['manifest']).parent/part['file']);indexed={r['id']:r for r in rows}
   predictions=load_jsonl(root/'evaluation'/name/'predictions.jsonl')
   if {r['id'] for r in predictions}!=set(indexed):raise ValueError('Different IDs')
   for pred in predictions:
    prompt=generation_prompt(tok,indexed[pred['id']]['messages'],'sft-aligned');ids=tok.encode(prompt,add_special_tokens=False)
    if sha(prompt.encode())!=pred['prompt_sha256'] or len(ids)!=pred['input_tokens']:raise ValueError('Prompt/token mismatch')
    text=tok.decode(pred['generated_token_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False)
    if text!=pred['response'] or pred['truncated']:raise ValueError('Stored decoding/truncation mismatch')
    audit_stream_text(text,pred['stream_response'])
    if pred['output_tokens'] not in [len(pred['generated_token_ids']),len(pred['generated_token_ids'])+1]:raise ValueError('Unexpected EOS accounting')
    if not re.fullmatch(r'<output>\s*.+?\s*</output>',final_text(text),re.S):raise ValueError('Incomplete output format')
   counts[arm+'/'+name]=len(predictions)
 r={'status':'PASS_PUBLIC_TOKEN_PROMPT_ARTIFACT_AUDIT','prediction_rows_verified':sum(counts.values()),'sets':counts,'new_model_calls':0,'checks':['Exact executed runner hash matches frozen protocol and receipt','Protocol snapshots match frozen bytes','Input prompt SHA and native tokenizer lengths','Raw native token decoding equals saved response','Stream-render policy, EOS accounting and completeXML','No truncations'],'scope':'Published search predictions; no unpublished adapter/confirmation access or semantic gold review'}
 write_json(a.output,r);print(json.dumps(r,indent=2))
if __name__=='__main__':main()
