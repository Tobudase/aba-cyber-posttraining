#!/usr/bin/env python3
"""Offline aggregate consistency checks; no private prediction reproduction."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'results/kali-bf16-confirmation-2026-10-26'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=read(D/'publication-manifest.json')
 for name,digest in m['file_sha256'].items():
  p=ROOT/name;assert p.resolve().is_relative_to(ROOT) and not p.is_symlink() and sha(p)==digest,name
 s=read(D/'summary.json');c=read(ROOT/'configs/kali-bf16-confirmation-executed.json');f=read(D/'evidence-provenance.json');a=read(D/'adapter-identity.json')
 assert sha(ROOT/'scripts/check-kali-bf16-confirmation.py')==f['worker_sha256']
 parent=read(ROOT/'results/kali-bf16-240-sft-2026-10-26/training-receipt.json')
 assert a['adapter_sha256']==s['adapter_sha256']==c['adapter_sha256']==parent['adapter_sha256']
 assert a['exact_tensor_match'] and a['loaded_tensor_count']==144
 assert s['new_optimizer_steps']==c['budget']['max_optimizer_steps']==0
 assert s['new_generations']==c['budget']['max_generations']==192
 assert c['inference']['batch_size']==4 and c['inference']['max_new_tokens']==1024
 assert c['inference']['do_sample'] is False and not c['inference']['forced_prefix'] and not c['inference']['output_repair']
 cc=s['CONFIRMATION'];assert len(cc['by_group'])==12
 for arm in ['base','sft']:
  assert cc[arm]['rows']==72 and s['retention'][arm]['rows']==24 and s['formats'][arm]['rows']==96
  for k in ['correct','unsupported']:assert sum(g[arm+'_'+k] for g in cc['by_group'].values())==cc[arm][k]
  assert all(g['rows_per_arm']==6 for g in cc['by_group'].values())
 lower=cc['sft']['correct']-cc['base']['correct']-cc['base']['unsupported']
 positive=sum(g['sft_correct']-g['base_correct']-g['base_unsupported']>0 for g in cc['by_group'].values())
 g=s['confirmation_gate'];assert g['conservative_gain_lower_bound']==lower and g['conservative_positive_groups']==positive
 checks={'conservative_confirmation_gain_at_least4':lower>=4,'conservative_positive_groups_at_least2':positive>=2,'retention_strict_not_decreased':s['retention']['sft']['strict_correct']>=s['retention']['base']['strict_correct'],'candidate_complete_outputs':s['formats']['sft']['complete_output_blocks']==96,'candidate_think_closure':s['formats']['sft']['think_closed']==96,'candidate_no_truncation':s['formats']['sft']['truncated']==0,'exact_saved_adapter_no_training':True}
 assert g['checks']==checks and g['passes_confirmation_gate']==all(checks.values())
 assert cc['sft']['correct']-cc['base']['correct']==s['paired']['new_verified_passes']-s['paired']['old_verified_passes_lost']
 assert s['official_TEST_calls']==s['external_teacher_calls']==0 and not s['ABA_search_executed']
 assert not s['candidate_promoted'] and s['formal_default']=='original_base' and s['confirmation_now_exposed']
 assert s['resources']['all_owned_resources_remaining']==0 and not s['resources']['cleanup_errors']
 cpu=read(D/'CPU-preflight.json');assert cpu['overlap_with_TRAIN_or_DEV_ids_queries_groups']==0 and cpu['confirmation_groups']==12 and cpu['confirmation_rows']==72
 sem=read(D/'semantic-scoring.json');assert sem['records']==144 and sem['gold_controls']==sem['gold_controls_passed'] and sem['model_calls']==0
 print(json.dumps({'status':'PASS_PUBLIC_FIXED_ADAPTER_CONFIRMATION','files_verified':len(m['file_sha256']),'confirmation_gate_passed':all(checks.values()),'private_predictions_independently_recomputed':False}))
if __name__=='__main__':main()
