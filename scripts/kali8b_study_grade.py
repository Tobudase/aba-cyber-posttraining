"""Frozen private grading for the verified64 8B study; no generation or training."""
import hashlib,json
from pathlib import Path
from benchkit import native_kali,strict_option_values
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'data/benchkit';STUDY=B/'kali-8b-verified64-study-2026-11-12'
REFS=[B/'kali-redsage-publisher-holdout-2026-11-10/references-private.json',B/'kali-redsage-publisher-confirm64-2026-11-10/references-private.json']
SOURCE_TOOLS={'hardlink','virtualenv','dnstwist','pyi-makespec'}
def summarize(detail,ids):
 return {'rows':len(ids),'native_total_mean':sum(detail[i]['native_total'] for i in ids)/len(ids),'strict_correct':sum(detail[i]['strict'] for i in ids),'format_errors':sum(detail[i]['format_error'] for i in ids),'truncations':sum(detail[i]['truncated'] for i in ids)}
def score_arm(candidate_id,folder=None):
 folder=Path(folder or STUDY/candidate_id/'run');lock=json.loads((STUDY/'grading-lock-private.json').read_text());assert lock['grade_module_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 refpanels=[json.loads(p.read_text()) for p in REFS];refs={r['custom_id']:r for panel in refpanels for r in panel};assert len(refs)==128
 for p,h in zip(REFS,lock['reference_sha256']):assert hashlib.sha256(p.read_bytes()).hexdigest()==h
 panels={'combined':set(refs),'dev1':{r['custom_id'] for r in refpanels[0]},'dev2':{r['custom_id'] for r in refpanels[1]},'untargeted':{i for i,r in refs.items() if r['tool_name'] not in SOURCE_TOOLS}}
 scorer=native_kali();arms={};detail={}
 for name,file in [('base','base-predictions-private.json'),('candidate','candidate-predictions-private.json')]:
  rows=json.loads((folder/file).read_text());assert len(rows)==len({r['id'] for r in rows})==128 and {r['id'] for r in rows}==set(refs)
  detail[name]={}
  for r in rows:
   v=scorer.score_one(refs[r['id']],r['response']);detail[name][r['id']]={'native_total':v['total_score'],'strict':bool(not r['truncated'] and strict_option_values(refs[r['id']],r['response'],scorer)),'format_error':bool(v['format_error']),'truncated':r['truncated']}
  arms[name]={k:summarize(detail[name],sorted(ids)) for k,ids in panels.items()}
 base,cand=arms['base'],arms['candidate'];delta=cand['combined']['native_total_mean']-base['combined']['native_total_mean'];g=lock['decision_gates']
 gates={'native_gain':delta>=g['minimum_native_mean_gain'],'strict_retained':cand['combined']['strict_correct']>=base['combined']['strict_correct'],'format_retained':cand['combined']['format_errors']<=base['combined']['format_errors'],'truncation_retained':cand['combined']['truncations']<=base['combined']['truncations'],'DEV_panel_retention':all(cand[p]['native_total_mean']>=base[p]['native_total_mean']-g['maximum_panel_native_drop'] for p in ['dev1','dev2']),'untargeted_retention':cand['untargeted']['native_total_mean']>=base['untargeted']['native_total_mean']-g['maximum_untargeted_native_drop']}
 result={'status':'FROZEN_INTERNAL_DEV_STUDY_SCORE','candidate_id':candidate_id,'summary':arms,'native_delta':delta,'selection_gates':gates,'passes_all_gates':all(gates.values()),'ABA_score':round(100*delta,9) if all(gates.values()) else -1.0,'paired_strict':{'gained':sum(not detail['base'][i]['strict'] and detail['candidate'][i]['strict'] for i in refs),'lost':sum(detail['base'][i]['strict'] and not detail['candidate'][i]['strict'] for i in refs)},'official_TEST_rows':0,'sealed_final64_used':False,'scope':'Exposed publisher-TRAIN DEV diagnosis; not independent or official score.'}
 (folder/'score-detail-private.json').write_text(json.dumps(detail,indent=2)+'\n');(folder/'scores-private.json').write_text(json.dumps(result,indent=2)+'\n');return result
