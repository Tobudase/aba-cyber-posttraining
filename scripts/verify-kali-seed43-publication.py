#!/usr/bin/env python3
"""Verify released aggregates/integrity; not private prediction or runtime reproduction."""
import hashlib,json,math
from pathlib import Path
from kali_target_envelope import convert_train_row,newline_target
R=Path(__file__).resolve().parents[1];D=R/'results/kali-seed43-replication-2026-10-25'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=read(D/'publication-manifest.json')
 for name,h in m['file_sha256'].items():
  p=R/name;assert p.resolve().is_relative_to(R) and not p.is_symlink();assert sha(p)==h,name
 s=read(D/'summary.json');n=read(D/'numerical-receipts.json')['arms'];assert s['official_test_rows']==s['confirmation_rows']==0 and not s['old_scientific_scores_rewritten']
 expected={'base':(2,52,8,10,22),'seed42_compact':(3,36,7,10,21),'seed42_newline':(5,54,8,10,22),'seed43_compact':(3,36,7,11,22),'seed43_newline':(4,54,8,10,22)}
 for arm,(domain,retention,transfer,passed,executed) in expected.items():
  g=s['scores'][arm];t=s['transfer'][arm];assert g['domain']['rows']==36 and g['domain']['strict_correct']==domain;assert g['retention']['rows']==72 and g['retention']['strict_correct']==retention;assert g['transfer']['rows']==t['rows']==24 and g['transfer']['strict_correct']==t['strict_correct']==transfer;assert t['execution_passed']==passed and t['executed']==executed and t['unverified']==24-executed
 old=read(R/'results/kali-causal-findings-2026-10-25/summary.json')
 for arm,prior in [('base','base'),('seed42_compact','V3_compact'),('seed42_newline','target_newline')]:
  for group in ['domain','retention']:
   for key in ['rows','strict_correct','native_exact_correct','native_total']:assert s['scores'][arm][group][key]==old['scores'][prior][group][key]
 for seed in ['42','43']:
  assert s['paired_strict_changes'][seed]['retention']==18
  assert s['scores']['seed'+seed+'_newline']['retention']['strict_correct']-s['scores']['seed'+seed+'_compact']['retention']['strict_correct']==18
 r=s['replication'];assert r['seed']==43 and r['new_optimizer_steps']==256 and r['new_generations']==450;assert r['all_historical_controls_passed'] and r['initial_LoRA_parameters_identical'] and r['training_orders_identical'];assert len(set(r['training_order_sha256'].values()))==1
 assert r['target_token_counts']=={'compact':3222,'newline':3374}
 assert len(n)==2
 for arm,x in n.items():assert x['status']=='COMPLETE' and x['seed']==43 and x['optimizer_steps']==len(x['losses'])==128 and all(math.isfinite(v) for v in x['losses']) and x['changed_parameter_tensors']==144 and x['trainable_parameters']==7667712 and x['adapter_reload_max_logit_delta']==0 and x['train_order_sha256']==r['training_order_sha256'][arm]
 assert len({x['adapter_sha256'] for x in n.values()})==2
 t=s['transfer_panel'];assert t['rows']==24 and t['tools']==8 and t['gold_prevalidation_passed']==24 and t['frozen_before_model_calls'] and not t['used_for_training_or_tuning'] and not t['independent_official_or_expert_validation'];assert t['postvalidation_check_records']==144 and t['postvalidation_commands_executed']==24+sum(x['executed'] for x in s['transfer'].values())==133;assert t['postvalidation_not_executed']==11
 assert not any(s['all_internal_checks_passed'].values());assert s['decision']['formal_default_remains_original_base'] and not s['decision']['independent_validation_complete'] and not s['decision']['larger_formal_training_or_official_evaluation_started']
 f=s['formatter'];assert sha(R/f['file'])==f['source_sha256']
 row={'id':'example','split':'train','training_eligible':True,'official_test':False,'target':'<output>example_command file.txt</output>','messages':[{'role':'user','content':'example'}]};out=convert_train_row(row);assert out['target']=='<output>\nexample_command file.txt\n</output>' and {k:v for k,v in out.items() if k!='target'}=={k:v for k,v in row.items() if k!='target'};assert convert_train_row(out)==out
 for bad in [{**row,'split':'dev_search'},{**row,'official_test':True}]:
  try:convert_train_row(bad)
  except ValueError:pass
  else:raise AssertionError('Noneligible role accepted')
 for bad in ['<output>x</output><output>y</output>','<output>x\ny</output>']:
  try:newline_target(bad)
  except ValueError:pass
  else:raise AssertionError('Malformed envelope accepted')
 allowed={'kali-cuda-2026-10-24':{'README.md'},'kali-replay-v3-2026-10-24':{'README.md','results/kali-cuda-2026-10-24/publication-manifest.json'},'kali-causal-findings-2026-10-25':{'README.md','results/kali-cuda-2026-10-24/publication-manifest.json','results/kali-replay-v3-2026-10-24/publication-manifest.json'}}
 for folder,changes in allowed.items():
  path=R/'results'/folder;before=read(path/'publication-manifest.at-9b8adb8.json')['file_sha256'];after=read(path/'publication-manifest.json')['file_sha256'];assert set(before)==set(after) and {k for k in before if before[k]!=after[k]}==changes
 print(json.dumps({'status':'PASS_PUBLIC_SEED43_PUBLICATION','files_verified':len(m['file_sha256']),'paired_retention_delta_seed43':18,'candidate_adopted':False,'independent_validation_complete':False,'private_runtime_or_prediction_reproduction':False},indent=2))
if __name__=='__main__':main()
