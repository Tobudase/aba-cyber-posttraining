#!/usr/bin/env python3
"""Real tiny CPU optimizer check plus rejection guards; not 8B/cyber training."""
import copy,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from kali_sft_recipe import validate_recipe,train_fixed_sft

def main():
 import torch
 from torch import nn
 from torch.nn import functional as F
 class Toy(nn.Module):
  def __init__(self):
   super().__init__();self.embedding=nn.Embedding(32,8);self.base=nn.Linear(8,32,bias=False)
   for p in self.parameters():p.requires_grad=False
   self.lora_A=nn.Parameter(torch.randn(4,8)*0.1);self.lora_B=nn.Parameter(torch.zeros(32,4))
  def forward(self,input_ids,labels=None,**kw):
   h=self.embedding(input_ids);logits=self.base(h)+(h@self.lora_A.T)@self.lora_B.T
   return SimpleNamespace(logits=logits,loss=F.cross_entropy(logits[:,:-1].reshape(-1,32),labels[:,1:].reshape(-1),ignore_index=-100) if labels is not None else None)
 torch.manual_seed(42);torch.set_num_threads(1);model=Toy();rows=[{'id':str(i),'split':'train','training_eligible':True,'official_test':False,'TRAIN_fixture_execution_verified':True,'TRAIN_explicit_constraints_verified':True,'input_ids':[1,i+2,12,13,14],'labels':[-100,-100,12,13,14],'prompt_tokens':2} for i in range(4)];c={'schema':'kali.sft.optimizer.v1','seed':42,'epochs':4,'max_optimizer_steps':16,'batch_size':1,'gradient_accumulation_steps':1,'max_sequence_tokens':64,'learning_rate':1e-3,'weight_decay':0,'betas':[0.9,0.999],'eps':1e-8,'max_grad_norm':None}
 def nll():
  with torch.inference_mode():return sum(float(model(input_ids=torch.tensor([r['input_ids']]),labels=torch.tensor([r['labels']])).loss) for r in rows)/len(rows)
 base=[p.detach().clone() for n,p in model.named_parameters() if 'lora_' not in n];before=nll();receipt=train_fixed_sft(model,rows,c,'cpu');after=nll();assert after<before and receipt['optimizer_steps']==16 and receipt['changed_tensors']==2 and receipt['nonzero_gradient_steps']==16
 assert all(torch.equal(a,b) for a,b in zip(base,[p for n,p in model.named_parameters() if 'lora_' not in n]))
 probe=torch.tensor([[1,2,3]]);ref=model(input_ids=probe).logits.detach().clone()
 with tempfile.TemporaryDirectory() as td:
  path=Path(td)/'toy.pt';torch.save(model.state_dict(),path);fresh=Toy();fresh.load_state_dict(torch.load(path,weights_only=True));assert torch.equal(fresh(input_ids=probe).logits,ref)
 rejected=0
 for changes in [{'extra_setting':True},{'learning_rate':0},{'learning_rate':float('nan')},{'max_optimizer_steps':17},{'gradient_accumulation_steps':2},{'max_grad_norm':-1}]:
  try:validate_recipe({**c,**changes},rows)
  except ValueError:rejected+=1
  else:raise AssertionError('Invalid recipe accepted')
 for mutate in [lambda r:r.update(split='dev'),lambda r:r.update(official_test=True),lambda r:r.update(TRAIN_fixture_execution_verified=False),lambda r:r['labels'].__setitem__(0,1)]:
  bad=copy.deepcopy(rows);mutate(bad[0])
  try:validate_recipe(c,bad)
  except ValueError:rejected+=1
  else:raise AssertionError('Protected/invalid supervision accepted')
 badmodel=Toy();badmodel.embedding.weight.requires_grad=True
 try:train_fixed_sft(badmodel,rows,c,'cpu')
 except ValueError:rejected+=1
 else:raise AssertionError('Unfrozen base accepted')
 result={'status':'PASS_REAL_TINY_CPU_OPTIMIZER_AND_BOUNDARIES','torch':torch.__version__,'optimizer_steps':16,'base_weights_unchanged':True,'changed_toy_LoRA_tensors':2,'TRAIN_NLL_before':before,'TRAIN_NLL_after':after,'gradient_norms_finite':True,'reload_max_logit_delta':0,'invalid_inputs_rejected':rejected,'pretrained_8B_training':False,'cybersecurity_model_gain':False,'GPU_allocations':0};print(json.dumps(result,indent=2))

if __name__=='__main__':main()
