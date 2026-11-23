"""Calculate paired contrasts without treating decoding seeds or files as new source questions."""
from collections import Counter
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ARMS=['answer_only','background','rule','background_copy','rule_copy']
PAIRS=[('rule','background'),('rule_copy','background_copy'),
       ('background_copy','background'),('rule_copy','rule')]

def load(name):
    return json.loads((HERE/name).read_text())

def check_fit(data):
    seeds=data['training_seeds']
    controls=data['native_controls']
    assert set(controls)=={'gold','reverse','bad_format','wrong_file'}
    for kind,cases in controls.items():
        assert set(cases)=={'original','same','opposite','distractor'}
        assert all(r['strict']==(kind=='gold') for r in cases.values())
    assert all(r['behavior'] and not r['format'] for r in controls['bad_format'].values())
    assert seeds==[3407,3413,3433] and data['decoding_seeds']==[11341,11351]
    counts={}; paired={}
    for seed in seeds:
        arms=data['training'][str(seed)]['arms']
        assert set(arms)==set(ARMS) and len({a['init_sha256'] for a in arms.values()})==1
        by_arm={}
        for arm,r in arms.items():
            assert set(r['checkpoints'])=={'1','16','32','64'}
            assert all(len(r['checkpoints'][str(t)]['weights'])==64 for t in (16,32,64))
            ds=r['evaluations']
            assert set(ds)=={'11341','11351'}
            row=Counter()
            for s,d in ds.items():
                assert set(d)=={'original','same','opposite','distractor'}
                for name,v in d.items():
                    assert v['strict']==bool(v['behavior'] and v['format'])
                    if v['behavior']:assert v['fixture_matches']==[True]*3
                    row[name]+=int(v['strict'])
                    if name!='original':
                        row['probes']+=int(v['strict'])
                        row['native']+=int(v['behavior'])
                        row['tokens']+=v['tokens']
                        row['truncated']+=int(not v['ended'])
                    else:
                        row['exact_aux']+=int(v['auxiliary_exact'] and v['ended'])
            by_arm[arm]=dict(row)
        counts[seed]=by_arm
        paired[seed]={a+' minus '+b:by_arm[a]['probes']-by_arm[b]['probes'] for a,b in PAIRS}
    assert len({data['training'][str(s)]['arms']['rule']['init_sha256'] for s in seeds})==3
    assert all(r['released'] for r in data['job_records'])
    return counts,paired

def check_screen(data):
    assert set(data['sources'])=={'sample_7395','sample_6402','sample_7538'}
    result={}
    for uid,record in data['sources'].items():
        assert set(record['models'])=={'student','A64','B64','C64','qwen','deepseek'}
        for who,trials in record['models'].items():
            assert set(trials)=={'22103','22109','22111'}
            for r in trials.values():
                assert len(r['results'])==2 and r['strict']==(r['results']==['pass','pass'])
        result[uid]={m:sum(r['strict'] for r in trials.values()) for m,trials in record['models'].items()}
    assert all(r['released'] for r in data['jobs'])
    return result

if __name__=='__main__':
    counts,paired=check_fit(load('factor-results.json'))
    for s,arms in counts.items():print(s,{a:v['probes'] for a,v in arms.items()},paired[s])
    for uid,arms in check_screen(load('prospective-results.json')).items():print(uid,arms)
