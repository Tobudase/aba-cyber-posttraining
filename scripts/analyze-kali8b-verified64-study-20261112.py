#!/usr/bin/env python3
"""Posthoc DEV diagnosis only. Does not change data, training, selection or score."""
import json
from collections import Counter
from pathlib import Path
from benchkit import native_kali
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'data/benchkit';S=B/'kali-8b-verified64-study-2026-11-12'
def main():
 panels=[json.loads((B/p/'references-private.json').read_text()) for p in ['kali-redsage-publisher-holdout-2026-11-10','kali-redsage-publisher-confirm64-2026-11-10']];refs={r['custom_id']:r for panel in panels for r in panel};targeted={i for i,r in refs.items() if r['tool_name'] in {'hardlink','virtualenv','dnstwist','pyi-makespec'}};groups={'combined':set(refs),'DEV1':{r['custom_id'] for r in panels[0]},'DEV2':{r['custom_id'] for r in panels[1]},'targeted_tools':targeted,'other_tools':set(refs)-targeted};scorer=native_kali();preds={};strict={}
 for cid in ['P11','P12','P13','P14']:
  run=S/cid/'run';f=run/'host-private.json'
  if not f.exists() or json.loads(f.read_text())['status']!='COLLECTED':continue
  d=json.loads((run/'score-detail-private.json').read_text());preds[cid]={r['id']:r['response'] for r in json.loads((run/'candidate-predictions-private.json').read_text())};strict[cid]=d['candidate']
  base={r['id']:r['response'] for r in json.loads((run/'base-predictions-private.json').read_text())}
  if 'E0' in preds:assert preds['E0']==base
  else:preds['E0']=base;strict['E0']=d['base']
 scores={cid:{i:scorer.score_one(refs[i],r) for i,r in p.items()} for cid,p in preds.items()};metrics={}
 for cid in preds:
  metrics[cid]={}
  for group,ids in groups.items():
   assert ids;metrics[cid][group]={'rows':len(ids),**{k:sum(scores[cid][i][k] for i in ids)/len(ids) for k in ['tool_score','optional_f1','positional_f1','total_score']},'strict_correct':sum(strict[cid][i]['strict'] for i in ids)}
 result={'status':'POSTHOC_EXPOSED_DEV_COMPONENT_DIAGNOSIS','selection_rules_changed':False,'model_calls':0,'official_TEST_rows':0,'sealed64_used':False,'targeted_DEV_tool_counts':dict(Counter(refs[i]['tool_name'] for i in targeted)),'groups':metrics,'limits':'Descriptions of observed failures,not unique causal proof or independent validation;fixed replacement changes both added and removed contents.'}
 if {'P11','P12'}<=set(preds):
  effect={}
  for group,ids in groups.items():
   c,t=metrics['P11'][group],metrics['P12'][group];d={k:t[k]-c[k] for k in ['tool_score','optional_f1','positional_f1','total_score']};assert abs(d['total_score']-(d['tool_score']+d['optional_f1']+d['positional_f1'])/3)<1e-12
   effect[group]={'rows':len(ids),'component_deltas':d,'responses_changed':sum(preds['P11'][i]!=preds['P12'][i] for i in ids),'strict_gained':sum(not strict['P11'][i]['strict'] and strict['P12'][i]['strict'] for i in ids),'strict_lost':sum(strict['P11'][i]['strict'] and not strict['P12'][i]['strict'] for i in ids)}
  result['P12_minus_P11']=effect
 (S/'DEV-diagnosis-aggregate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'targeted_counts':result['targeted_DEV_tool_counts'],'P12_minus_P11':result.get('P12_minus_P11')}))
if __name__=='__main__':main()
