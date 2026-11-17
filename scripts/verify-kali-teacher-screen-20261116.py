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
    for key in ['training_updates','official_TEST_queries','development_queries','confirmation_queries','admitted_reasoning_SFT_rows','generated_tool_commands_executed']:
        assert s[key]==0,key
    for arm,a in s['arms'].items():
        assert a['recorded']==a['returned']==a['requested']==67
        assert 0<=a['strict']<=a['native_exact']<=67
        assert 0<=a['native_total_all_requested']<=1
        assert 0<=a['truncated']<=67 and a['native_exact']+a['truncated']<=67
    assert s['max_concurrent_stage_GPUs']==1
    if 'student_thinking' not in s['arms']:assert s['status']=='IN_PROGRESS'
    print(json.dumps({'result':'PASS','public_files_verified':len(manifest),'status':s['status'],
      'scope':'Aggregate consistency only; private per-case evidence not publicly disclosed'},indent=2))
if __name__=='__main__':main()
