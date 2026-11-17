"""Verify public aggregate math and snapshots; no private data required."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'results/kali-verified-teacher-stage-2026-11-17';s=json.loads((p/'preparation-summary.json').read_text())
for n,h in json.loads((p/'manifest.json').read_text()).items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h,n
correction=json.loads((p/'gap-evidence-correction.json').read_text())
assert correction['original_low_success_gap_candidates']==3 and correction['both_modes_repeated_failure_certified']==1 and correction['uncertain_candidates']==2
assert correction['unknown_is_not_certified_failure'] and not correction['raw_cases_public']
certified=0
for candidate in correction['anonymized_candidate_counts']:
    assert candidate['teacher_passes_of_three']>=2
    for counts in candidate['student_counts'].values():assert sum(counts.values())==3 and counts['PASS']<=1
    actual=all(counts['FAIL']>=2 for counts in candidate['student_counts'].values())
    assert actual==candidate['repeated_failure_in_both_modes_certified'];certified+=actual
assert certified==1
a=s['admission'];assert a['main_independent_teacher_rows']+a['publisher_replay_rows']==s['encoding']['rows']==29
assert sum(a['main_tools'].values())==23 and len(a['main_tools'])==8 and sum(a['all_tools'].values())==29 and len(a['all_tools'])==12
assert a['strong_gaps']==3 and a['strong_gaps']<=a['main_independent_teacher_rows']
assert abs(a['actual_replay_fraction']-6/29)<1e-12
assert s['accepted_task_counts']=={'teacher_U_0':42,'teacher_U_1':45,'teacher_H_0':67,'student_thinking':30,'student_nonthinking':14}
assert s['positive_reference_checks']==134 and s['negative_checks']==286 and s['false_passed_negative_checks']==0
assert s['training_protocol']['optimizer_updates_per_arm']==s['training_protocol']['epochs']*((s['encoding']['rows']+7)//8)==32
assert s['encoding']['arms']['answer_only']['target_tokens_per_epoch']==569 and s['encoding']['arms']['reasoning']['target_tokens_per_epoch']==6377
assert s['official_TEST_queries']==0 and not s['raw_cases_public'] and s['not_final_SFT_or_ABA_results']
snap=ROOT/'code-snapshots/teacher-sft-20261117';manifest=json.loads((snap/'manifest.json').read_text())
for n,h in manifest['snapshots'].items():assert hashlib.sha256((snap/n).read_bytes()).hexdigest()==h,n
assert hashlib.sha256((snap/'retention_metric.py').read_bytes()).hexdigest()==manifest['derived_metric_sha256']
for f in snap.glob('*.py'):ast.parse(f.read_text())
print('PASS: aggregate arithmetic, scientific scope, source hashes and Python syntax; no claim of private-case reexecution.')
