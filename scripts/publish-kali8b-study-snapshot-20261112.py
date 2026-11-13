#!/usr/bin/env python3
"""Export allowlisted aggregates only; never questions, predictions, keys or tensors."""
import argparse,datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--publication-root',type=Path,required=True);p.add_argument('--study-root',type=Path,default=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12');p.add_argument('--require-complete',action='store_true');a=p.parse_args();s=a.study_root;out=a.publication_root/'results/kali-8b-verified64-study-2026-11-12';assert out.is_dir();f=json.loads((s/'protocol-freeze-private.json').read_text());result={'status':'IN_PROGRESS','updated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_id':'RISys-Lab/RedSage-K-SFT-GRPO','model_revision':'843e2e3096e7de68f5c35eb16238f4909f21695a','study_protocol_freeze_sha256':sha(s/'protocol-freeze-private.json'),'DEV_rows':128,'official_TEST_rows':0,'GPU_parallel_limit':1,'arms':{},'limitations':['Internal publisher-TRAIN DEV has been exposed and used for development.','New data:64 locally behavior-verified AI silver rows,32 correlated families,4 tools.','Replacement matches supervised tokens and updates;prompt tokens and FLOPs differ.','ABA has two recipe candidates;each fixed control has one. No equal-search-budget superiority claim.','Final64 is previously unqueried TRAIN-derived publisher silver,not expert gold or source-separated official TEST.','A passing internal gate alone is not model release or leaderboard validation.']}
 for cid in ['P11','P12','P13','P14']:
  run=s/cid/'run';host=json.loads((run/'host-private.json').read_text()) if (run/'host-private.json').exists() else {'status':'NOT_STARTED'};entry={'status':host['status'],'protocol_sha256':f['protocol_sha256'][cid]}
  if host['status']=='COLLECTED':
   receipt=json.loads((run/'receipt-private.json').read_text());export=json.loads((run/'adapter-export-private.json').read_text());assert receipt['protocol_sha256']==entry['protocol_sha256'] and receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==733 and receipt['supervised_token_presentations']==17439
   assert sha(run/'adapter-bundle-private/adapter/adapter_model.safetensors')==export['adapter_sha256']==receipt['adapter_sha256'];score=json.loads((run/'scores-private.json').read_text());assert not score['sealed_final64_used'] and score['official_TEST_rows']==0
   entry.update(node_name=host.get('node_name'),observed_pod_resources=host.get('observed_pod_resources'),score=score,receipt={k:receipt[k] for k in ['status','run_kind','initial_lora_sha256','adapter_sha256','adapter_config_sha256','optimizer_steps','nonzero_gradient_steps','changed_tensors','supervised_token_presentations','adapter_reload_max_logit_delta','GPU','GPU_count','deterministic_algorithms','attention_backend','wall_seconds','peak_cuda_allocated_bytes','quality_counts']},adapter_tensor_count=export['tensor_count'],cleanup_errors=host['cleanup_errors'])
  result['arms'][cid]=entry
 placement=s/'placement-amendment-private.json'
 if placement.exists():result['placement_amendment']=json.loads(placement.read_text());result['limitations'].append('P11/P12 originalhost/driver615.71.09/CPU2;ABA/confirmation central sameGPUproduct/driver615.71.10/CPU500m after zero-update queue cancellation. Report amended placement,not exact hardware equivalence.')
 consistency=s/'four-arm-consistency-aggregate.json'
 if consistency.exists():result['consistency']=json.loads(consistency.read_text())
 complete=all(x['status']=='COLLECTED' for x in result['arms'].values());selection=s/'native-selection-private.json'
 if selection.exists():
  selected=json.loads(selection.read_text());result['selection']={k:selected[k] for k in ['status','candidate_id','pointer','native_selected_candidate','native_selected_pointer','native_run_id','DEV_score','native_selected_DEV_score','all_available_scores','deliverable_sha256','native_deliverable_candidate','retention_policy','final64_used','official_TEST_rows']}
  folder=ROOT/'docs/verification/kali8b-native-v64-20261112';host=json.loads((folder/'host-private.json').read_text());journal=json.loads((folder/'journal-private.json').read_text());result['native']={'controller_requested_model':json.loads((folder/'config.json').read_text())['llm']['default']['model'],'controller_served_models':sorted({u['model'] for u in journal['usage_events']}),'controller_scope':'NRP-hosted orchestration only;fine-tuned model remains8B. Hosted controller weights are not trained here.','status':host['status'],'head':journal['head'],'event_counts':journal['event_counts'],'source_sha256':json.loads((folder/'native-task-freeze-private.json').read_text())['runtime_source_sha256'],'cleanup_errors':host['cleanup_errors']};complete=complete and host['native_completed'] and not host['cleanup_errors']
 else:complete=False
 confirmation=s/'confirmation'
 if (confirmation/'scores-private.json').exists():
  result['confirmation']=json.loads((confirmation/'scores-private.json').read_text());result['confirmation_receipt']=json.loads((confirmation/'receipt-private.json').read_text());ch=json.loads((confirmation/'host-private.json').read_text());result['confirmation_cleanup_errors']=ch['cleanup_errors'];complete=complete and ch['status']=='COMPLETE' and not ch['cleanup_errors']
 else:complete=False
 complete=complete and result.get('consistency',{}).get('status')=='PASS_REAL_FOUR_ARM_CONSISTENCY'
 result['research_experiment_complete']=complete
 if complete:
  result['status']='COMPLETE_BOUNDED_8B_STUDY';result['training_GPU_worker_hours']=sum(v['receipt']['wall_seconds'] for v in result['arms'].values())/3600;result['confirmation_GPU_worker_hours']=result['confirmation_receipt']['wall_seconds']/3600;result['cost_scope']='Worker elapsed time includes model staging,training and inference;excludes queue wait,CPU export and controllerVM. Not a GPU FLOP or billing measurement.'
 if 'score' in result['arms']['P11'] and 'score' in result['arms']['P12']:
  c=result['arms']['P11']['score']['summary']['candidate']['combined'];t=result['arms']['P12']['score']['summary']['candidate']['combined'];result['matched_replacement_effect_P12_minus_P11']={'native_mean_delta':t['native_total_mean']-c['native_total_mean'],'strict_count_delta':t['strict_correct']-c['strict_correct'],'interpretation':'Effect of replacing64 token-length-matched publisher records with64 verifiedsilver records;not isolated dataquality effect.'}
 if a.require_complete:assert complete,'Cannot publish completed claims from partial artifacts'
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'collected_arms':[c for c,v in result['arms'].items() if v['status']=='COLLECTED'],'complete':complete,'official_TEST_rows':0}))
if __name__=='__main__':main()
