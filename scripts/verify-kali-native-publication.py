#!/usr/bin/env python3
"""Check released numeric evidence and input guards; no fresh model reproduction."""
import hashlib,json,math
from pathlib import Path
from kali_native_completion import encode_verified_continuation

R=Path(__file__).resolve().parents[1];D=R/'results/kali-native-family-2026-10-25'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=read(D/'publication-manifest.json')
 for f,h in manifest['file_sha256'].items():
  p=R/f;assert p.resolve().is_relative_to(R) and not p.is_symlink() and sha(p)==h,f
 s=read(D/'summary.json');a=s['alignment'];assert a['legacy_nf4_final_only_strict']==8 and a['bf16_native_strict']==13 and a['rows']==24;assert a['native_nf4_bridge']==4 and a['native_bf16_bridge']==5 and a['bridge_rows']==6;assert a['new_generations']==33 and a['new_optimizer_steps']==0 and a['legacy_controls_exact_match'];assert not a['official_vllm_reproduction'] and not a['single_factor_causal_claim']
 data=s['data'];assert data['split_rows']=={'train':64,'dev':12,'validation':12} and data['gold_passed']==88 and data['negative_controls_passed']==4;assert data['TRAIN_generated']==64 and data['TRAIN_reviewed_executed']==56 and data['TRAIN_verified']==50 and data['TRAIN_executed_failed']==6 and data['TRAIN_not_executed']==8;assert data['TRAIN_accepted_rows']==42 and data['TRAIN_accepted_families']==6 and data['supervised_tokens']==891 and data['max_sequence_tokens']==390 and data['TRAIN_execution_pass_but_constraint_rejected']==8;assert not data['independent_expert_or_official_gold'] and not data['reasoning_tokens_supervised'] and not data['responses_repaired'];assert s['rollouts']['generations']==79 and s['rollouts']['native_controls_match']
 e=read(D/'developer-execution-audit.json');assert e==s['developer_execution_audit'] and e['records']==36 and e['actual_command_executions']==30 and e['not_executed_records']==6 and e['verified_order_equivalent_OpenSSL_pairs']==2 and e['execution_verified_true_regressions_among_those2']==0 and not e['developer_gate_changed'] and not e['sealed_validation_queries'];assert all(e['models'][arm]=={'rows':12,'executed':9,'passed':4} for arm in ['base','candidate'])
 n=s['native_ABA'];assert n['completed'] and n['setup_verifier_reviewer_passed'] and n['task_bytes_unchanged'] and n['four_selected_files_exact'] and n['agent_DEV_rows']==n['agent_validation_rows']==0;assert not n['autonomous_data_or_hyperparameter_search'];assert n['final_delivery_verified_via_cached_controller_replay'] and n['controller_replay_new_optimizer_steps']==n['controller_replay_new_GPU_jobs']==0 and n['public_zero_step_baseline_snapshot_files']==4
 train=read(D/'training-receipt.json');assert train['optimizer_steps']==len(train['losses'])==42 and train['learning_rate']==5e-6 and train['seed']==42 and train['changed_parameter_tensors']>0 and train['adapter_reload_max_logit_delta']<=1e-4;assert all(math.isfinite(v) for v in train['losses']);assert train['dev_or_validation_gradient_rows']==0
 score=s['developer'];gate=score['candidate_dev_exact']>score['base_dev_exact'] and score['candidate_retention_strict']>=score['base_retention_strict'] and score['format_or_truncation_failures']==0;assert score['base_dev_exact']==4 and score['base_retention_strict']==13 and score['adoption_gate_passed']==gate;assert n['selected_model']==('E2' if gate else 'E0')
 if gate:assert s['validation']['rows_each']==12 and s['validation']['used_for_gradient_or_candidate_tuning'] is False
 else:assert s['validation']['status']=='NOT_QUERIED_CANDIDATE_FAILED_DEVELOPER_GATE' and s['validation']['model_rows']==0
 assert s['official_test_rows']==0 and not s['old_scientific_results_rewritten'];assert s['cleanup']['remaining_new_jobs_pods_configmaps']==0 and s['cleanup']['VM_Halted'] and s['cleanup']['VM_instances']==0
 # Synthetic character tokenizer exercises refusal/masking invariants only.
 # Actual pinned tokenizer checks have a separate numerical receipt.
 class T:
  eos_token_id=999999;eos_token='<eos>'
  def apply_chat_template(self,messages,**kw):return 'USER:'+messages[-1]['content']+'\nASSISTANT:<think>'
  def encode(self,text,**kw):return [ord(c) for c in text]
  def decode(self,ids,**kw):return ''.join(self.eos_token if i==self.eos_token_id else chr(i) for i in ids)
 t=T();row={'split':'train','training_eligible':True,'official_test':False};messages=[{'role':'user','content':'Synthetic input-boundary test, never training data.'}];response='\nSynthetic context.\n<output>\nexample\n</output>';ids=t.encode(response);x=encode_verified_continuation(t,row,messages,response,ids);assert x['labels'][:x['prompt_tokens']+x['context_only_generated_tokens']]==[-100]*(x['prompt_tokens']+x['context_only_generated_tokens']);assert x['labels'][-1]==t.eos_token_id
 bad=[({**row,'split':'dev','training_eligible':False},messages,response,ids,2048),({**row,'official_test':True},messages,response,ids,2048),(row,messages,response+'x',ids,2048),(row,messages+[{'role':'assistant','content':'bad'}],response,ids,2048),(row,messages,response,ids,1)]
 for r,m,raw,tokens,limit in bad:
  try:encode_verified_continuation(t,r,m,raw,tokens,max_length=limit)
  except ValueError:pass
  else:raise AssertionError('Invalid supervision input accepted')
 print(json.dumps({'status':'PASS_PUBLIC_NATIVE_PILOT_EVIDENCE_AND_BOUNDARY_GUARDS','files_verified':len(manifest['file_sha256']),'optimizer_steps':42,'selected_model':n['selected_model'],'official_test_rows':0,'fresh_model_or_private_prediction_reproduction':False},indent=2))

if __name__=='__main__':main()
