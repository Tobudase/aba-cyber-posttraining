"""Verify published aggregates/integrity; raw response audit remains private."""
import argparse,hashlib,json,math
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--result-dir',type=Path,default=Path('results/kali-rationale-sft-results-2026-11-17'));a=p.parse_args()
 for name,digest in json.loads((a.result_dir/'manifest.json').read_text()).items():assert hashlib.sha256((a.result_dir/name).read_bytes()).hexdigest()==digest,name
 d=json.loads((a.result_dir/'summary.json').read_text());assert d['status']=='COMPLETE_VERIFIED'
 for name in ['initial_adapters_identical','adapter_reload_hashes_verified','training_order_verified','local_rescoring_matches_cluster','GPU_resources_cleaned']:assert d[name]
 assert d['official_TEST_queries']==d['confirmation_queries']==0
 for arm,tokens in [('answer_only',5184),('reasoning',19744)]:
  aa=d['adapter_tensor_checks'][arm];assert aa['tensor_count']==144 and aa['trainable_parameters']==7667712 and aa['all_finite'] and aa['all_72_B_matrices_nonzero'] and aa['receipt_hash_matches'] and aa['dtypes']==['torch.float32']
  t=d['training'][arm];assert t['updates']==48 and t['epochs']==4 and t['supervised_tokens']==tokens and t['gradients_finite_nonzero']
  for key in ['epoch_mean_loss','epoch_mean_command_loss']:assert len(t[key])==4 and all(math.isfinite(x) and x>0 for x in t[key])
 metrics={**d['summary'],'base_nonthinking':d['nonthinking_control']['summary']}
 for arm,panels in metrics.items():
  for name,n in [('development24',24),('old64',64)]:
   x=panels[name];assert x['n']==n and 0<=x['strict']<=n-x['invalid'] and 0<=x['truncated']<=x['invalid']<=n and 0<=x['native_partial']<=1 and x['tokens']>=0
 for arm,panels in d['alias_sensitivity']['summary'].items():
  actual='base_nonthinking' if arm=='base-nonthinking' else arm
  for panel,x in panels.items():
   assert x['n']==metrics[actual][panel]['n'] and x['frozen_strict']==metrics[actual][panel]['strict'] and x['frozen_strict']<=x['alias_normalized_strict']<=x['n']
 assert d['alias_sensitivity']['frozen_primary_unchanged'] and d['alias_sensitivity']['new_model_queries']==0
 for arm,panels in d['native_score_components'].items():
  for panel,x in panels.items():assert abs(sum(x.values())/3-metrics[arm][panel]['native_partial'])<1e-12
 for old,new in [('base','answer_only'),('base','reasoning'),('answer_only','reasoning')]:
  for panel in ['development24','old64']:
   pair=d['paired'][old+'_to_'+new][panel];assert pair['net']==pair['gain']-pair['loss']==metrics[new][panel]['strict']-metrics[old][panel]['strict']
   assert pair['gain']==sum(pair[k] for k in ['gain_from_truncated','gain_from_other_invalid','gain_from_valid_wrong'])
   assert pair['loss']==sum(pair[k] for k in ['loss_to_truncated','loss_to_other_invalid','loss_to_valid_wrong'])
   n=pair['gain']+pair['loss'];pval=min(1.,2*sum(math.comb(n,k) for k in range(min(pair['gain'],pair['loss'])+1))/2**n) if n else 1.
   assert abs(pval-pair['paired_exact_p_two_sided'])<1e-12
 for arm,r in d['retention'].items():
  assert r['base_correct']==metrics['base']['old64']['strict'] and 0<=r['kept']<=r['base_correct']
  expected=bool(r['base_correct'] and r['kept']>=math.ceil(.95*r['base_correct']) and metrics[arm]['old64']['invalid']<=metrics['base']['old64']['invalid'] and metrics[arm]['old64']['truncated']<=metrics['base']['old64']['truncated'])
  assert r['guard_pass']==expected
 print(json.dumps({'status':'PASS','scope':'Published aggregate math and artifact hashes; raw data, teacher responses and per-case provenance remain private.'},indent=2))
if __name__=='__main__':main()
