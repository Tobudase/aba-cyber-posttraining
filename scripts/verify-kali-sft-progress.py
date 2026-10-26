#!/usr/bin/env python3
"""Check released SFT evidence and boundaries; no private model reproduction."""
import ast,hashlib,importlib.util,json,math,subprocess,sys
from pathlib import Path
from kali_sft_recipe import validate_recipe

R=Path(__file__).resolve().parents[1];D=R/'results/kali-sft-progress-2026-10-26'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=read(D/'publication-manifest.json')
 for name,digest in m['file_sha256'].items():
  p=R/name;assert p.resolve().is_relative_to(R) and p.is_file() and not p.is_symlink() and sha(p)==digest,name
 s=read(D/'stage-status.json');assert s['completed_8B_optimizer_steps']==256 and s['completed_8B_generations']>=216 and not s['new240_SFT_executed'] and not s['native_ABA_new_data_search_executed'];assert s['official_TEST_calls']==s['old_sealed_validation_calls']==s['new_confirmation_calls']==s['external_teacher_calls']==0 and s['formal_default']=='original_base'
 recall=read(D/'train-recall.json');assert recall['new_generations']==168 and recall['new_optimizer_steps']==0 and recall['next_branch']=='BOUNDED_TRAIN_ONLY_MICROFIT' and not recall['predeclared_learning_signal'];assert recall['sets']['NF4_base']['correction']['correct']==4 and recall['sets']['NF4_hardmix']['correction']['correct']==5;assert recall['sets']['BF16_base']['correction']['correct']==3 and recall['sets']['BF16_hardmix']['correction']['correct']==1
 for key,values in recall['sets'].items():assert values['easy_replay']['correct']==values['easy_replay']['rows']==20 and values['correction']['rows']==22
 micro=read(D/'microfit.json');assert micro['new_optimizer_steps']==256 and micro['new_generations']==48 and not micro['training_sanity_gate_passed'] and micro['selected_arm'] is None;assert micro['sets']['base_NF4_TRAIN']['correct']==0 and micro['sets']['base_BF16']['correct']==2;assert micro['sets']['lr5e6_NF4_TRAIN']['correct']==4 and micro['sets']['lr5e6_BF16']['correct']==0 and micro['sets']['lr2e5_NF4_TRAIN']['correct']==0 and micro['sets']['lr2e5_BF16']['correct']==5
 receipts=read(D/'microfit-training-receipts.json');assert len({x['initial_LoRA_sha256'] for x in receipts.values()})==1
 for name,tr in receipts.items():
  assert tr['optimizer_steps']==len(tr['trace'])==128 and tr['changed_tensors']==144 and tr['adapter_reload_max_logit_delta']==0 and tr['nonzero_gradient_steps']==128
  assert all(math.isfinite(x['loss']) and math.isfinite(x['gradient_norm_before_clip']) for x in tr['trace']);arm=micro['arms'][name];assert arm['relative_loss_drop']==(arm['token_weighted_NLL_before']-arm['token_weighted_NLL_after'])/arm['token_weighted_NLL_before']
 data=R/'data/benchkit/kali-verified-sft-v1';dm=read(data/'manifest.json');assert not (data/'confirmation.jsonl').exists();groups={};ids=set()
 for split,count in [('train',240),('dev',72)]:
  assert sha(data/f'{split}.jsonl')==dm['released_data_sha256'][f'{split}.jsonl'];rows=[json.loads(t) for t in (data/f'{split}.jsonl').read_text().splitlines()];assert len(rows)==count;groups[split]={x['template_group'] for x in rows}
  for row in rows:assert row['split']==split and row['training_eligible']==(split=='train') and row['official_test'] is False and row['independent_human_review'] is False and row['id'] not in ids;ids.add(row['id'])
 assert len(groups['train'])==40 and len(groups['dev'])==12 and not groups['train']&groups['dev']
 audit=read(D/'data-execution-audit.json');assert audit['status']=='PASS' and audit['gold']=={'train':{'rows':240,'passed':240},'dev':{'rows':72,'passed':72},'confirmation':{'rows':72,'passed':72}} and audit['negative_passed']==audit['negative_checks']==448
 ready=read(D/'data-readiness.json');assert ready['supervised_tokens']==6624 and ready['maximum_sequence_length']==375 and ready['new_dataset_model_calls']==0 and ready['independent_human_review'] is False;assert read(D/'portable-encoder-parity.json')['rows']==240
 preflight=read(D/'recipe-preflight.json');assert preflight['optimizer_source_sha256']==sha(R/'scripts/kali_sft_recipe.py') and preflight['recipe_sha256']==sha(R/'configs/kali-verified-sft-v1.optimizer.json');toy=read(D/'tiny-cpu-training-check.json');assert toy['optimizer_steps']==16 and toy['invalid_inputs_rejected']==11 and toy['TRAIN_NLL_after']<toy['TRAIN_NLL_before'] and toy['base_weights_unchanged'] and not toy['pretrained_8B_training'] and toy['GPU_allocations']==0
 row={'id':'invented','split':'train','training_eligible':True,'official_test':False,'TRAIN_fixture_execution_verified':True,'TRAIN_explicit_constraints_verified':True,'input_ids':[1,2,3],'labels':[-100,-100,3],'prompt_tokens':2};cfg=read(R/'configs/kali-verified-sft-v1.optimizer.json');small={**cfg,'epochs':1,'max_optimizer_steps':1};assert validate_recipe(small,[row])==small
 try:validate_recipe({**small,'unknown':True},[row])
 except ValueError:pass
 else:raise AssertionError('Unknown optimizer setting accepted')
 spec=importlib.util.spec_from_file_location('encoder',R/'scripts/prepare-kali-sft-inputs.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);text='SYSTEM_PROMPT_UNRESTRICTED_THINKING="system"\nUSER_PROMPT_UNRESTRICTED_THINKING_TEMPLATE="{query}"\nraise RuntimeError("must never execute")\n';assert mod.load_prompt_constants(text)['SYSTEM_PROMPT_UNRESTRICTED_THINKING']=='system'
 folders=['kali-cuda-2026-10-24','kali-replay-v3-2026-10-24','kali-causal-findings-2026-10-25','kali-seed43-replication-2026-10-25','kali-native-family-2026-10-25','kali-learning-diagnosis-2026-10-25'];allowed={'README.md'}
 for folder in folders:
  p=R/'results'/folder;before=read(p/'publication-manifest.at-3bf965b.json')['file_sha256'];after=read(p/'publication-manifest.json')['file_sha256'];assert set(before)==set(after) and {k for k in before if before[k]!=after[k]}<=allowed;allowed.add(str((p/'publication-manifest.json').relative_to(R)))
 cleanup=read(D/'resource-cleanup.json');assert cleanup['this_round_Jobs_Pods_ConfigMaps_remaining']==cleanup['research_VM_instances']==0 and cleanup['research_VM_runStrategy']=='Halted'
 subprocess.run([sys.executable,str(R/'scripts/verify-kali-sft-examples.py')],check=True)
 print(json.dumps({'status':'PASS_PUBLIC_STEPWISE_SFT_EVIDENCE','files_verified':len(m['file_sha256']),'public_authored_TRAIN':240,'public_authored_DEV':72,'private_confirmation_bodies_released':0,'training_sanity_gate_passed':False,'new240_training_executed':False,'private_model_reproduction':False}))

if __name__=='__main__':main()
