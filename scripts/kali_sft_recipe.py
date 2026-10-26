"""Explicit, bounded SFT recipe and shared optimizer loop. No inherited defaults."""
import copy,hashlib,json,math,random

FIELDS={'schema','seed','epochs','max_optimizer_steps','batch_size','gradient_accumulation_steps','max_sequence_tokens','learning_rate','weight_decay','betas','eps','max_grad_norm'}

def validate_recipe(config,rows):
 if set(config)!=FIELDS:raise ValueError('Unknown or missing effective recipe fields')
 c=copy.deepcopy(config)
 if c['schema']!='kali.sft.optimizer.v1':raise ValueError('Unknown recipe schema')
 for key in ['seed','epochs','max_optimizer_steps','batch_size','gradient_accumulation_steps','max_sequence_tokens']:
  if type(c[key]) is not int:raise ValueError('Integer fields must be explicit')
 if c['batch_size']!=1 or c['gradient_accumulation_steps']!=1:raise ValueError('This reviewed loop supports one example per optimizer update')
 if not rows or not 1<=c['epochs']<=32 or len(rows)*c['epochs']!=c['max_optimizer_steps'] or c['max_optimizer_steps']>512:raise ValueError('Exact finite step/epoch/data budget required')
 if not 1<=c['max_sequence_tokens']<=2048:raise ValueError('Invalid sequence budget')
 for key in ['learning_rate','weight_decay','eps']:
  if type(c[key]) not in [int,float] or not math.isfinite(c[key]):raise ValueError('Finite optimizer settings required')
 if not 0<c['learning_rate']<=1e-3 or c['weight_decay']<0 or c['eps']<=0:raise ValueError('Invalid optimizer setting')
 if len(c['betas'])!=2 or any(type(v) not in [int,float] or not math.isfinite(v) or not 0<=v<1 for v in c['betas']):raise ValueError('Invalid Adam betas')
 if c['max_grad_norm'] is not None and (type(c['max_grad_norm']) not in [int,float] or not math.isfinite(c['max_grad_norm']) or c['max_grad_norm']<=0):raise ValueError('Invalid gradient clipping setting')
 if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate TRAIN IDs')
 for r in rows:
  if r.get('split')!='train' or r.get('training_eligible') is not True or r.get('official_test') is not False:raise ValueError('Explicit eligible TRAIN only')
  if not all(r.get(k) is True for k in ['TRAIN_fixture_execution_verified','TRAIN_explicit_constraints_verified']):raise ValueError('Unverified TRAIN record')
  a,b,n=r['input_ids'],r['labels'],r['prompt_tokens']
  if not 0<n<len(a)<=c['max_sequence_tokens'] or len(a)!=len(b) or b[:n]!=[-100]*n or b[n:]!=a[n:]:raise ValueError('Invalid completion mask/length')
 return c

def train_fixed_sft(model,rows,config,device,progress=None):
 import torch
 c=validate_recipe(config,rows);model.train();params={name:value for name,value in model.named_parameters() if value.requires_grad}
 if not params or any('lora_' not in name for name in params):raise ValueError('Only LoRA parameters may be trainable')
 before={n:p.detach().cpu().clone() for n,p in params.items()};optimizer=torch.optim.AdamW(params.values(),lr=c['learning_rate'],weight_decay=c['weight_decay'],betas=tuple(c['betas']),eps=c['eps']);trace=[];order=[]
 for epoch in range(c['epochs']):
  permutation=list(range(len(rows)));random.Random(c['seed']+epoch).shuffle(permutation)
  for i in permutation:
   row=rows[i];ids=row['input_ids'];batch={'input_ids':torch.tensor([ids],device=device),'attention_mask':torch.ones((1,len(ids)),dtype=torch.long,device=device),'labels':torch.tensor([row['labels']],device=device)};optimizer.zero_grad(set_to_none=True);loss=model(**batch,use_cache=False).loss
   if not math.isfinite(float(loss.detach())):raise ValueError('Nonfinite training loss')
   loss.backward();grads=[v.grad for v in params.values() if v.grad is not None]
   if not grads:raise ValueError('No LoRA gradients')
   norm=torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(g.detach().float()) for g in grads]));gn=float(norm)
   if not math.isfinite(gn):raise ValueError('Nonfinite gradient norm')
   if c['max_grad_norm'] is not None:torch.nn.utils.clip_grad_norm_(params.values(),c['max_grad_norm'],error_if_nonfinite=True)
   optimizer.step();step={'step':len(trace)+1,'epoch':epoch+1,'loss':float(loss.detach()),'gradient_norm_before_clip':gn,'supervised_tokens':len(ids)-row['prompt_tokens']};trace.append(step);order.append(row['id'])
   if progress:progress(step)
 changed=sum(not torch.equal(before[n],v.detach().cpu()) for n,v in params.items())
 if not changed or len(trace)!=c['max_optimizer_steps']:raise ValueError('No actual parameter update or wrong step count')
 return {'effective_optimizer_recipe':c,'optimizer_steps':len(trace),'trainable_parameters':sum(v.numel() for v in params.values()),'changed_tensors':changed,'trace':trace,'epoch_order_sha256':hashlib.sha256(json.dumps(order).encode()).hexdigest(),'TRAIN_presentations':len(order),'supervised_token_presentations':sum(x['supervised_tokens'] for x in trace),'all_gradient_norms_finite':True,'nonzero_gradient_steps':sum(x['gradient_norm_before_clip']>0 for x in trace),'DEV_or_validation_gradient_rows':0}
