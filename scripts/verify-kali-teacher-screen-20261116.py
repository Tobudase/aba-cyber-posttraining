"""Check sanitized aggregate consistency, not private per-case correctness."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'results/kali-teacher-screen-2026-11-16'
def main():
    manifest=json.loads((D/'manifest.json').read_text())
    assert set(manifest)=={'aggregate.json','RESULT_ZH.md','screening.png'}
    for name,digest in manifest.items():
        assert hashlib.sha256((D/name).read_bytes()).hexdigest()==digest,name
    s=json.loads((D/'aggregate.json').read_text())
    assert s['partition_rows']=={'train':67,'development':24,'confirmation':24}
    assert s['publisher_reference_terminal_labels']=={'PASS_RUNTIME_ERROR':67}
    for key in ['training_updates','official_TEST_queries','development_queries','confirmation_queries','admitted_reasoning_SFT_rows']:
        assert s[key]==0,key
    for arm,a in s['arms'].items():
        assert a['recorded']==a['returned']==a['requested']==67
        assert 0<=a['strict']<=a['native_exact']<=67
        assert 0<=a['native_total_all_requested']<=1
        assert 0<=a['truncated']<=67 and a['native_exact']+a['truncated']<=67
    assert s['max_concurrent_stage_GPUs']==1
    if 'student_thinking' not in s['arms']:
        assert s['status']=='IN_PROGRESS' and s['generated_tool_commands_executed']==0
    else:
        g=s['gap_review'];assert s['status']==g['status']=='BASELINES_AND_GAP_REVIEW_COMPLETE'
        assert len(s['arms'])==4 and sum(a['returned'] for a in s['arms'].values())==g['scored_response_samples']==268
        assert g['unique_reference_score_gaps']==g['confirmed_local_task_gaps']+g['reference_scope_holds']+g['tool_output_holds']==6
        assert g['confirmed_local_task_gaps']==g['clean_brief_explanation_seeds']+g['explanations_requiring_correction']==4
        paired=g['student_pairing']
        assert s['arms']['student_nonthinking']['strict']==paired['strict_both']+paired['thinking_losses']
        assert s['arms']['student_thinking']['strict']==paired['strict_both']+paired['thinking_rescues']
        assert s['screen_generated_tool_commands_executed']==0
        assert s['generated_tool_commands_executed']==g['fixture_model_command_invocations']==36
        assert len(g['fixture_checks'])==2 and all(c['confirmed_task_gap']==4 and c['valid_student_failures']==12 for c in g['fixture_checks'])
        assert g['generated_binaries_executed']==g['fixture_model_calls']==0
        assert s['student_resources_cleaned'] and g['all_student_and_review_resources_cleaned']
    print(json.dumps({'result':'PASS','public_files_verified':len(manifest),'status':s['status'],
      'scope':'Aggregate consistency only; private per-case evidence not publicly disclosed'},indent=2))
if __name__=='__main__':main()
