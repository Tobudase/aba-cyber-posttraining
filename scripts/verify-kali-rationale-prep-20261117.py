"""Public aggregate audit. Private raw data and responses are not distributed."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'results/kali-rationale-sft-prep-2026-11-17'
def main():
    for name,h in json.loads((D/'manifest.json').read_text()).items():
        assert Path(name).name==name and hashlib.sha256((D/name).read_bytes()).hexdigest()==h
    s=json.loads((D/'summary.json').read_text());p=json.loads((D/'protocol.json').read_text());e=json.loads((D/'evaluation-protocol.json').read_text());r=s['data_review']
    assert s['status']=='PREPARED_NOT_TRAINED' and s['actual_training_updates']==s['actual_student_eval_queries']==0
    assert sum(r['families'].values())==r['teacher_returned']==r['admitted_pilot_rows']==r['fixture_positive_pass']==r['fixture_negative_rejected']==48
    assert r['AI_edited_explanations']+r['unchanged_teacher_explanations']==48
    assert s['isolation']['held_schema_overlap']==s['isolation']['held_query_overlap']==0
    assert s['checks']['native_template_roundtrip_passed']==96 and s['checks']['unit_tests_passed']==5
    assert p['optimizer_updates_per_arm']==p['rows']*p['epochs']//p['effective_batch']==48
    assert e['planned_responses']==3*(e['development_rows']+e['exposed_retention_rows'])==264
    assert s['encoding']['reasoning']['supervised_tokens_per_epoch']>s['encoding']['answer_only']['supervised_tokens_per_epoch']
    assert s['CPU_fixture_resources_cleaned'] and not s['raw_training_data_public']
    print(json.dumps({'status':'PASS','scope':'Sanitized preparation aggregates; no training-performance claim'},indent=2))
if __name__=='__main__':main()
