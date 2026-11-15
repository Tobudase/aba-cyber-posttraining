"""Freeze two-original-model SFT pilot with native model-specific serialization."""
import gzip,hashlib,json,random,sys
from pathlib import Path
from transformers import AutoTokenizer
from tokenizers import Tokenizer
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/benchkit/kali-two-model-sft-2026-11-15'
SOURCE=ROOT/'data/benchkit/kali-functional-repair-v2-2026-11-15'
def digest(b):return hashlib.sha256(b).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def prepare():
 OUT.mkdir(exist_ok=False)
 new=json.loads((SOURCE/'new-records-private.json').read_text())['train'];old=json.loads((SOURCE/'replay-selected-private.json').read_text())
 oldpayload=json.loads(gzip.decompress((SOURCE/'gpu-inputs.json.gz').read_bytes()))
 panels={k:v for k,v in oldpayload['panels'].items() if k in ['old64','new_dev32','train_probe32']}
 assert sum(map(len,panels.values()))==128
 train=new+old;assert len(train)==256
 trainids={r['id'] for r in train};evalids={r['id'] for k,rr in panels.items() if k!='train_probe32' for r in rr};assert not trainids&evalids
 refs=json.loads((SOURCE/'references-private.json').read_text());encoded={};audits={};protocols={}
 cm=ROOT/'data/benchkit/kali-execution-2026-11-14/miw113-kali-functional-training-r3-1115/objects.json'
 reds=json.loads(json.loads(cm.read_text())[0]['data']['config.json'])['model_protocol']
 prefetch=json.loads((ROOT/'configs/kali-qwen-checkpoint-prefetch.private.json').read_text())
 qwen={**reds,'model_id':prefetch['model_id'],'model_revision':prefetch['revision'],'checkpoint_files':{f['name']:f['sha256'] for f in prefetch['files']}}
 for name,protocol,folder in [('redsage',reds,'redsage-k-843e2e3096e7'),('qwen',qwen,'qwen3-8b-b968826d9c46')]:
  tp=ROOT/'.tools/model-tokenizer'/folder;tok=AutoTokenizer.from_pretrained(tp,local_files_only=True,trust_remote_code=False,fix_mistral_regex=False)
  assert tok.eos_token_id==151645
  target_tokenizer=None
  if name=='redsage':
   js=json.loads((tp/'tokenizer.json').read_text());js['added_tokens']=[x for x in js['added_tokens'] if x['id']!=151668];target_tokenizer=Tokenizer.from_str(json.dumps(js))
  def template(messages):return tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,**({'enable_thinking':False} if name=='qwen' else {}))
  rows=[]
  for row in train:
   prompt=template(row['native_messages']);pi=tok.encode(prompt,add_special_tokens=False)
   completion=('\n</think>\n\n' if name=='redsage' else '')+row['target']
   ti=(target_tokenizer.encode(completion,add_special_tokens=False).ids if target_tokenizer else tok.encode(completion,add_special_tokens=False))+[tok.eos_token_id]
   assert tok.decode(ti,skip_special_tokens=False,clean_up_tokenization_spaces=False)==completion+tok.eos_token
   if name=='redsage':assert prompt.endswith('<think>') and 151668 not in ti
   else:assert prompt.endswith('<think>\n\n</think>\n\n')
   assert len(pi)+len(ti)<=2048
   rows.append({'id':row['id'],'input_ids':pi+ti,'labels':[-100]*len(pi)+ti,'prompt_tokens':len(pi),'target_tokens':len(ti),'origin':'new' if row['id'] in {x['id'] for x in new} else 'old_replay'})
  encoded[name]=rows;protocols[name]=protocol
  audits[name]={'rows':len(rows),'supervised_tokens_per_epoch':sum(r['target_tokens'] for r in rows),'prompt_tokens_per_epoch':sum(r['prompt_tokens'] for r in rows),'max_sequence':max(len(r['input_ids']) for r in rows),'tokenizer_sha256':digest((tp/'tokenizer.json').read_bytes()),'encoding_sha256':digest(json.dumps(rows,separators=(',',':')).encode()),'format':'Unchanged RedSage inference prefill plus explicitly declared BPE empty-think completion intervention' if name=='redsage' else 'Official Qwen native non-thinking prompt; direct output completion; no RedSage BPE patch'}
 # Identical sample exposures and order, not equal tokenizer token counts/FLOPs.
 orders=[]
 for epoch in range(4):
  rng=random.Random(42+epoch);a=list(range(128));b=list(range(128,256));rng.shuffle(a);rng.shuffle(b);orders.append([z for i in range(0,128,2) for z in [a[i],b[i],a[i+1],b[i+1]]])
 payload={'encoded':encoded,'panels':panels,'epoch_orders':orders}
 raw=gzip.compress(json.dumps(payload,separators=(',',':')).encode(),mtime=0);(OUT/'gpu-inputs.json.gz').write_bytes(raw)
 write(OUT/'references-private.json',{r['id']:refs[r['id']] for rr in panels.values() for r in rr})
 write(OUT/'model-protocols.json',protocols);write(OUT/'encoding-audit.json',audits)
 freeze={'status':'FROZEN_BEFORE_NEW_GPU_OUTPUTS','experiment':'Two-original-model model+native-recipe pilot, not a pure architecture causal ablation','models':{k:{'id':v['model_id'],'revision':v['model_revision']} for k,v in protocols.items()},'source':'Original publisher checkpoints, fresh zero-B q/v LoRA; no F22 adapter loaded','data':{'new_rows':128,'old_replay_rows':128,'source_sha256':digest((SOURCE/'gpu-inputs.json.gz').read_bytes()),'four_new_tools':True,'exposed_DEV32':True,'old_DEV64':True,'TRAINprobe32':True,'independent_confirmation_queried':False},'recipe':{'seed':42,'LoRA_r':16,'LoRA_alpha':32,'target_modules':['q_proj','v_proj'],'dropout':0,'lr':2e-5,'optimizer':'AdamW','betas':[.9,.999],'eps':1e-8,'weight_decay':0,'microbatch':1,'accumulation':4,'epochs':4,'updates':256,'checkpoints':[128,256],'grad_clip':1,'base_dtype':'BF16','adapter_dtype':'FP32','KL':0},'inference':{'greedy':True,'batch':4,'max_new_tokens':1024,'seed':3407,'primary':'Same command-only ngram8 guard for both baselines and both SFT models','raw_diagnostic':'DEV32 baseline and final only, no guard; no checkpoint selection using raw outputs'},'metrics':['v6 behavioral PASS/FAIL/UNKNOWN on DEV32 and TRAINprobe32','Old64 native partial score, strict total and baseline-correct retained/lost','format/EOS/truncation','actual training time, generation tokens and GPU memory'],'decision':'Report fixed final256 plus intermediate128 for every model; no best-checkpoint selection, no model promotion. Do not change recipes based on outputs. Stop each arm at256 updates even if scores are poor.','fairness':'Same sample exposure/update order and nominal LoRA hyperparameters; tokenizers and format differ, so not equal token/FLOP budget. Compare improvement relative to each model own paired baseline. One seed only.','gpu':'One GPU at a time; same GPU product for both model arms; <=4 allocated hours total for new model pilot, no priority/toleration bypass','validation':'V6 Linux oracle controls and uniform old-output review must pass before submitting GPU job. Input/source hashes, labels, real gradients, weight export/reload must be verified.','official_TEST_queries':0,'old_final64_queries':0,'protected_confirm384_queries':0,'new_confirm64_queries':0,'inputs_gzip_sha256':digest(raw),'encoding_audits':audits}
 write(OUT/'protocol.json',freeze);print(json.dumps({'prepared':True,'path':str(OUT),'encoding_audits':audits},indent=2))
if __name__=='__main__':prepare()
