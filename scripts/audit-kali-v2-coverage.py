"""Descriptive training option coverage, never relabel or infer on confirmation."""
from collections import defaultdict
from benchkit import ROOT,load_jsonl,write_json,sha
import json

def main():
 dev=load_jsonl(ROOT/'data/benchkit/kali-domain-dev-v1/dev_search.jsonl');out={}
 for tag,path in [('v1','data/benchkit/kali-doc-train-v1/train.jsonl'),('v2_available','data/benchkit/kali-doc-train-v2/train.jsonl'),('v2_common96','data/benchkit/kali-replay-ablation-v2/domain_control/train.jsonl')]:
  rows=load_jsonl(ROOT/path)
  if tag=='v2_common96':rows=rows[:96]
  seen=defaultdict(set)
  for row in rows:
   lab=row['native_label']
   for key in lab['optional_args']:seen[lab['tool_name']].update(key.split('|'))
  detail=[]
  for row in dev:
   lab=row['native_label'];missing=[k for k in lab['optional_args'] if not seen[lab['tool_name']].intersection(k.split('|'))]
   detail.append({'id':row['id'],'tool_seen':lab['tool_name'] in {r['native_label']['tool_name'] for r in rows},'missing_required_option_groups':missing,'option_groups_total':len(lab['optional_args'])})
  out[tag]={'training_rows':len(rows),'training_sha256':sha((ROOT/path).read_bytes()),'dev_rows':len(dev),'rows_with_missing_required_flag':sum(bool(x['missing_required_option_groups']) for x in detail),'rows_tool_and_flags_seen':sum(x['tool_seen'] and not x['missing_required_option_groups'] for x in detail),'details':detail}
 report={'status':'DESCRIPTIVE_COVERAGE_ONLY','sets':out,'limitations':['Lexical flag coverage ignores parameter semantics, order and composition; not proof of learned knowledge.','No-option tasks counted separately by option_groups_total.','V2 was designed after V1 diagnostics; this is exposed development, not independent testing.']}
 write_json(ROOT/'docs/verification/kali-v2-option-coverage.json',report)
 print(json.dumps({k:{a:v for a,v in x.items() if a!='details'} for k,x in out.items()},indent=2))
if __name__=='__main__':main()
