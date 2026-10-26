"""TRAIN-only conditional supervision from a real, unchanged native continuation.

This helper never generates or repairs reasoning/answers. Callers must independently
verify the final command. Generated pre-output text is context only, not a target.
"""
import re

def encode_verified_continuation(tokenizer,row,messages,response,generated_ids,max_length=2048):
 if row.get('split')!='train' or row.get('training_eligible') is not True or row.get('official_test'):
  raise ValueError('Only eligible TRAIN records may become supervision')
 if not messages or any(m.get('role') not in ['system','user'] for m in messages):
  raise ValueError('Only input system/user messages allowed')
 if not generated_ids or any(type(x) is not int or x<0 for x in generated_ids):
  raise ValueError('Actual generated token IDs required')
 if tokenizer.eos_token_id in generated_ids:raise ValueError('Pass continuation before EOS; EOS is appended once')
 if tokenizer.decode(generated_ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)!=response:
  raise ValueError('Actual token IDs do not decode to the unchanged response')
 blocks=list(re.finditer(r'<output>\s*(.*?)\s*</output>',response,re.S))
 if len(blocks)!=1 or not blocks[0].group(1).strip():raise ValueError('One nonempty final output block required')
 if response[blocks[0].end():].strip():raise ValueError('Final output must be the last generated content')
 prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
 if not prompt.endswith('<think>'):raise ValueError('Expected pinned native thinking prefix; do not silently strip or replace it')
 pids=tokenizer.encode(prompt,add_special_tokens=False)
 offsets=[len(tokenizer.decode(generated_ids[:j],skip_special_tokens=False,clean_up_tokenization_spaces=False)) for j in range(len(generated_ids)+1)]
 boundary=next(j for j,pos in enumerate(offsets) if pos>=blocks[0].start())
 ids=pids+list(generated_ids)+[tokenizer.eos_token_id]
 if len(ids)>max_length:raise ValueError('Sequence too long; no silent truncation')
 labels=[-100]*(len(pids)+boundary)+list(generated_ids[boundary:])+[tokenizer.eos_token_id]
 if not any(v!=-100 for v in labels) or len(ids)!=len(labels):raise ValueError('Invalid supervision')
 expected=prompt+response+tokenizer.eos_token
 if tokenizer.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)!=expected:raise ValueError('Conditional concatenation changed text')
 return {'input_ids':ids,'labels':labels,'prompt_tokens':len(pids),'context_only_generated_tokens':boundary,'supervised_tokens':len(ids)-len(pids)-boundary}
