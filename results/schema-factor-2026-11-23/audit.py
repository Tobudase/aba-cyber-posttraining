"""Recompute observed changes at the same prompt, training seed and decoding seed."""
from collections import Counter
from recount import ARMS, load, check_fit, check_screen

def probes(data,arm):
    return {(seed,decode,variant):record for seed,train in data['training'].items()
            for decode,draw in train['arms'][arm]['evaluations'].items()
            for variant,record in draw.items() if variant!='original'}

def compare(left,right):
    assert set(left)==set(right)
    return Counter((a['strict'],right[k]['strict']) for k,a in left.items())

def edit_counts(data, edits):
    out={}
    for arm in ARMS:
        count=Counter()
        for (seed,decode,variant),initial in probes(data,arm).items():
            row=edits['results'][seed+'-'+arm][decode][variant]
            if initial['strict']:continue
            count['strict_misses']+=1
            if row['status']!='replayed':
                count[row['status']]+=1
                continue
            checks=row['forms']
            if checks['literal']:count['already_correct_native_output']+=1
            else:
                for key in ('spelling','condition','both'):
                    count[key]+=int(checks[key])
                count['no_edit_sufficient']+=int(not any(checks.values()))
        out[arm]=dict(count)
    return out

def stratify(trials):
    return dict(passes=sum(r['strict'] for r in trials.values()),
                truncated=sum(r.get('truncated',not r.get('ended',True)) for r in trials.values()),
                conditional=sum(all(v.get('after_binding_fixture') is True for v in
                    r.get('native',r.get('observations',[]))) for r in trials.values()
                    if r.get('native') or r.get('observations')))

def main():
    data=load('factor-results.json')
    check_fit(data)
    for a,b in [('rule','background'),('rule_copy','background_copy'),
                ('background_copy','background'),('rule_copy','rule'),('rule','answer_only')]:
        counts=compare(probes(data,a),probes(data,b))
        print(f'{a} vs {b}: wins={counts[True,False]} losses={counts[False,True]} '
              f'both pass={counts[True,True]} both miss={counts[False,False]}')
    print('Post hoc native edits',edit_counts(data,load('option-replay.json')))
    print('Prospective',check_screen(load('prospective-results.json')))
    supplement=load('reference-supplement.json')
    for uid,draws in supplement['models'].items():
        assert all(len(r)==3 for r in draws.values())
        print(uid,{model:stratify(trials) for model,trials in draws.items()})
    clar=load('clarification.json')
    assert len(clar['draws'])==6
    for key,trials in clar['draws'].items():
        assert len(trials)==3
        print(key,stratify(trials))
    raw=load('filename-replays.json')
    assert set(raw['results'])=={'2280','2281'} and raw['job']['released']
    assert all(len(draws)==3 and all(len(native)==2 and all(r['outcome']=='pass' for r in native)
               for native in draws.values()) for draws in raw['results'].values())
    tx=load('transfer-replays.json')
    assert tx['job']['released'] and len(tx['results']['6402'])==5
    for variants in tx['results']['6402'].values():
        assert all(v['status']=='different-output' for v in variants['raw'])
        assert all(v['status']=='pass' for v in variants['split_upper'])
    assert all(x['status']=='pass' for x in tx['results']['7395']['B64/22111']['as_input'])
    src=load('source-accounting.json')
    before=set(src['previous_model_screened'])
    added=set(src['new_model_screened'])
    assert not before & added and len(before|added)==src['primary_total']==32
    assert set(src['qualified_sources']).issubset(before) and len(src['qualified_sources'])==3
    assert all(x['original_student']>=2 for x in src['new_model_screened'].values())
    print('Verified 6 filename repairs, 6 cross-source command replays and the 32-source accounting.')
if __name__=='__main__':main()
