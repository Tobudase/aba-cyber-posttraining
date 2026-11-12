#!/usr/bin/env python3
"""Read-only posthoc coverage audit on exposed DEV, never sealed confirmation."""
import gzip,hashlib,json
from pathlib import Path
from benchkit import native_kali
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'data/benchkit';S=B/'kali-8b-verified64-study-2026-11-12'
def main():
 scorer=native_kali();trainfile=B/'kali-fixture-train-v2-2026-11-12/train.jsonl';train=[json.loads(x) for x in trainfile.read_text().splitlines()];refs=[r for panel in ['kali-redsage-publisher-holdout-2026-11-10','kali-redsage-publisher-confirm64-2026-11-10'] for r in json.loads((B/panel/'references-private.json').read_text())];rows=[]
 publisher={r['custom_id']:r for r in map(json.loads,(ROOT/'.tools/benchkit/kali/KaliBench_data/kalibench_verified_train_3504.jsonl').open())};new_by_id={r['id']:r['native_label'] for r in train};arm_labels={}
 for cid in ['P11','P12']:
  encoded=json.loads(gzip.decompress((S/cid/'payload-private.json.gz').read_bytes()))['train_rows'];arm_labels[cid]=[new_by_id[r['id']] if r['id'] in new_by_id else publisher[r['id']] for r in encoded]
 for tool in ['hardlink','dnstwist','pyi-makespec','virtualenv']:
  selected=[r for r in train if r['native_label']['tool_name']==tool];ref=[r for r in refs if r['tool_name']==tool];assert len(ref)==1
  required=[set(k.split('|')) for k in scorer.parse_optional_args(ref[0]['optional_args'])]
  trainflags=[set(a for k in scorer.parse_optional_args(r['native_label']['optional_args']) for a in k.split('|')) for r in selected]
  covered=[any(g&f for f in trainflags) for g in required]
  arm_coverage={}
  for cid,labels in arm_labels.items():
   relevant=[r for r in labels if r['tool_name']==tool];flags=[set(a for k in scorer.parse_optional_args(r.get('optional_args')) for a in k.split('|')) for r in relevant];arm_coverage[cid]={'training_rows_for_tool':len(relevant),'required_groups_covered':sum(any(g&f for f in flags) for g in required),'rows_covering_all_groups_together':sum(all(g&f for g in required) for f in flags)}
  rows.append({'tool':tool,'full_training_arm_coverage':arm_coverage,'new_training_rows':len(selected),'exposed_DEV_rows':1,'reference_required_option_groups':len(required),'required_groups_with_any_new_TRAIN_example':sum(covered),'new_TRAIN_rows_covering_all_required_groups_together':sum(all(g&f for g in required) for f in trainflags),'P11_P12_strict_correct':0,'P11_P12_output_unchanged':True})
 p11={r['id']:r['response'] for r in json.loads((S/'P11/run/candidate-predictions-private.json').read_text())};p12={r['id']:r['response'] for r in json.loads((S/'P12/run/candidate-predictions-private.json').read_text())}
 for ref in refs:
  if ref['tool_name'] in {r['tool'] for r in rows}:
   assert p11[ref['custom_id']]==p12[ref['custom_id']]
   for cid in ['P11','P12']:assert not json.loads((S/cid/'run/score-detail-private.json').read_text())['candidate'][ref['custom_id']]['strict']
 result={'status':'POSTHOC_TARGET_SKILL_COVERAGE_AUDIT','model_calls':0,'training_calls':0,'official_TEST_rows':0,'sealed64_rows_read':0,'selection_or_data_changed':False,'new_train_sha256':hashlib.sha256(trainfile.read_bytes()).hexdigest(),'tools':rows,'required_groups':sum(r['reference_required_option_groups'] for r in rows),'covered_groups':sum(r['required_groups_with_any_new_TRAIN_example'] for r in rows),'interpretation':'Behavior-valid single-skill examples do not establish coverage of the option combinations and special argument semantics required by these four exposed DEV cases. Counts do not establish a unique causal explanation or imply the model must see exact evaluation answers. Do not add held-out answers or retune after confirmation.'}
 (S/'target-skill-coverage-aggregate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
