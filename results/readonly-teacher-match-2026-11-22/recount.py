"""Recount the primary single-source diagnostic and multi-source admission from sanitized per-draw results."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def main():
    single=read('single-aligned-results.json')
    labels=read('labels.json')
    assert len({labels[a]['effective_answer_hash'] for a in 'ABC'})==1
    assert len({r['initial_state'] for r in single['checkpoints'].values()})==1
    for arm,r in single['checkpoints'].items():
        assert r['token_counts']==labels[arm]['counts'] and set(r['hashes'])=={'16','32','64'}
    rows=single['details']
    original=read('single-aligned-replay.json')
    recovery=read('envelope-replay.json')
    for key,val in rows.items():
        native=original[key]['passed']
        assert val['strict']==(val['format'] and native)
        if key in ('B64-contrast','C64-fresh'):
            native=recovery[key[0]+'-format-only']['passed']
        assert val['behavior']==native,(key,val,native)
    for f in ('train','fresh','contrast'):
        assert original['control-gold-'+f]['passed'] and not original['control-wrong-'+f]['passed']
    assert len(rows)==33 and {k.rsplit('-',1)[1] for k in rows}=={'train','fresh','contrast'}
    for label in ['base','base_recheck',*(a+str(s) for a in 'ABC' for s in (16,32,64))]:
        vals=[rows[label+'-'+k] for k in ('train','fresh','contrast')]
        print(label,'strict',sum(v['strict'] for v in vals),'/ 3','behavior',sum(v['behavior'] for v in vals),'/ 3')
    combined=read('screen-summary.json')
    evidence=combined['rows']
    confirmed=[i for i,r in evidence.items() if r['admitted']]
    assert len(evidence)==19 and len(confirmed)==combined['qualified_count']
    teacher=read('teacher-scores.json')
    student=read('student-scores.json')
    assert set(teacher)==set(student)==set(evidence)-{'sample_6137'}
    for i,r in evidence.items():
        if i in teacher:
            scored={**teacher[i],**student[i]}
            assert r['draws']=={m:{seed:row['result'] for seed,row in trials.items()} for m,trials in scored.items()}
            assert r['native_pass']=={m:sum(v=='pass' for v in trial.values()) for m,trial in r['draws'].items()}
        for m in ('student','qwen','deepseek'):assert len(r['draws'][m])==3
        if r['admitted']:
            assert r['students_same_diagnosis']>=2 and all(r['native_pass'][m]>=2 for m in ('qwen','deepseek'))
            assert r['raw_review']['qwen'] and r['raw_review']['deepseek']
    assert combined['run_nine']==(len(confirmed)>=8 and len({evidence[i]['skill'] for i in confirmed})>=3)
    print('verified common independent source questions',len(confirmed),'/ 19')
if __name__=='__main__':main()
