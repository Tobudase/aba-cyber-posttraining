#!/usr/bin/env python3
"""Verify public aggregate consistency only; does not reproduce private experiments."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'results/kali-causal-findings-2026-10-25'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=read(P/'publication-manifest.json')
 for name,h in m['file_sha256'].items():
  p=ROOT/name;assert p.resolve().is_relative_to(ROOT) and not p.is_symlink();assert sha(p)==h,name
 s=read(P/'summary.json');r=read(P/'numerical-receipts.json')['studies'];assert s['official_test_rows']==s['confirmation_rows']==0
 expected={'base':(2,52),'V3_compact':(3,36),'learning_rate_half':(3,36),'query_directive_removal':(4,36),'target_newline':(5,54)}
 for arm,(domain,retention) in expected.items():
  for group,n,correct in [('domain',36,domain),('retention',72,retention)]:assert s['scores'][arm][group]['rows']==n and s['scores'][arm][group]['strict_correct']==correct
 old=read(ROOT/'results/kali-replay-v3-2026-10-24/comparison.json')
 for group,n in [('domain',36),('retention',72)]:
  for name,arm in [('base','baseline'),('V3_compact','post')]:assert round(old['comparisons'][group][arm]['strict_option_value_correct']*n/100)==s['scores'][name][group]['strict_correct']
 oldr=read(ROOT/'results/kali-replay-v3-2026-10-24/numerical-receipts.json')['phases']['E2/train']['numerical_receipt']
 for name,x in r.items():
  assert x['status']=='COMPLETE' and x['optimizer_steps']==len(x['losses'])==128 and all(math.isfinite(v) for v in x['losses'])
  assert x['changed_parameter_tensors']==144 and x['trainable_parameters']==7667712 and x['adapter_reload_max_logit_delta']==0
  assert x['adapter_sha256']!=oldr['adapter_sha256']
 assert len({x['adapter_sha256'] for x in r.values()})==3
 assert sum(a!=b for a,b in zip(r['target_newline']['losses'],oldr['losses']))==128
 t=s['target_format_treatment'];assert t['supervised_tokens_before']==3222 and t['supervised_tokens_after']==3374 and t['old_strict_regressions_recovered']==18
 assert t['output_only_newline_rescoring']['retention']=={'correct':36,'rows':72}
 assert t['fresh_Linux_checks']==288+96+192+3==579 and t['fixed_fixture_counts']=={'gold':72,'base':58,'V3':54,'latest':60}
 assert t['wc_edge_checks']['latest']=={'passed':48,'rows':48} and t['wc_edge_checks']['V3']=={'passed':0,'rows':48}
 assert t['formal_default_remains_original_base'] and not t['independent_validation_complete']
 p=s['fixed_weight_prefix_intervention'];assert p['generations']==18 and p['optimizer_steps']==0 and p['fresh_Linux_checks']==108
 for key,count in {'E0/original':3,'E0/forced_compact':0,'E0/forced_newline':3,'E2/original':0,'E2/forced_compact':0,'E2/forced_newline':3}.items():assert p['groups'][key]=={'rows':3,'strict_pass':count,'Linux_reply_pass':count}
 assert all(p['historical_controls'].values()) and p['bidirectional_same_bad_good_commands'] and not p['DNS_TLS_prefix_mechanism_separately_tested']
 # Current-tree hash maintenance must not rewrite earlier scientific release bytes.
 for folder,allowed in [('kali-cuda-2026-10-24',{'README.md'}),('kali-replay-v3-2026-10-24',{'README.md','results/kali-cuda-2026-10-24/publication-manifest.json'})]:
  d=ROOT/'results'/folder;a=read(d/'publication-manifest.at-8369c70.json')['file_sha256'];b=read(d/'publication-manifest.json')['file_sha256'];assert set(a)==set(b);assert {k for k in a if a[k]!=b[k]}==allowed
 print(json.dumps({'status':'PASS_PUBLIC_CAUSAL_FINDINGS','files_verified':len(m['file_sha256']),'prior_scientific_artifacts_unchanged':True,'independent_runtime_or_score_reproduction':False,'independent_validation_complete':False},indent=2))
if __name__=='__main__':main()
