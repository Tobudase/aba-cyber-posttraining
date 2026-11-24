"""Reproduce source-level paired effects, strata and leave-one-source-out sensitivity."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAGS = ('base','A64','B64','C64')
SEEDS = ('22103','22109','22111')

def load(p):
    return json.loads(p.read_text())

def combine():
    old = load(HERE.parent/'teacher-recall-2026-11-22/transfer.json')
    extra = load(HERE.parent/'schema-factor-2026-11-23/prospective-results.json')
    here = load(HERE/'transfer.json')
    assert old['training_source'] == extra['training_source'] == 'sample_6137'
    hashes = {k: o['weights'] if o else None for k,o in extra['adapters'].items()}
    assert hashes == old['checkpoints'] == here['checkpoint_sha256']
    rows = {}
    for uid, arms in old['sources'].items():
        rows[uid] = ('known_gap',{t:{s:arms[t][s]['strict_pass'] for s in SEEDS} for t in TAGS})
    for uid, case in extra['sources'].items():
        arms = case['models']
        assert uid not in rows
        rows[uid] = ('previous_prospective',{t:{s:arms['student' if t=='base' else t][s]['strict'] for s in SEEDS} for t in TAGS})
    for uid, case in here['sources'].items():
        assert 'sample_'+uid not in rows
        rows['sample_'+uid] = ('new_prospective',{t:{s:case[t+'-'+s]['final']=='pass' for s in SEEDS} for t in TAGS})
    return rows

def paired(rows,left,right):
    counts = Counter((v[left][s],v[right][s]) for _,v in rows.values() for s in SEEDS)
    return dict(wins=counts[True,False],losses=counts[False,True],both_pass=counts[True,True],both_miss=counts[False,False])

def summarize(rows):
    return {t:sum(sum(v[t].values()) for _,v in rows.values()) for t in TAGS}

def main():
    data=combine()
    for group in ('known_gap','previous_prospective','new_prospective','all_prospective','all'):
        selected={k:v for k,v in data.items() if group=='all' or v[0]==group or (group=='all_prospective' and v[0]!='known_gap')}
        print(group,len(selected),summarize(selected))
        for tag in ('B64','C64'):
            print(tag,'vs A64',paired(selected,tag,'A64'))
    primary=load(HERE/'transfer.json')['sources']
    replay=load(HERE/'semantic-replays.json')['relaxed_behavior']
    totals={t:0 for t in TAGS}
    for k,vs in primary.items():
        for key,r in vs.items():
            t,seed=key.split('-')
            totals[t]+=int(replay.get(k,{}).get(key,r['final']=='pass'))
    assert totals=={'base':15,'A64':12,'B64':15,'C64':12}
    print('New sources under post-hoc recoverable-behavior scoring',totals)
    assert all(x['same_visible'] and x['first_score']==x['second_score']=='pass' for vs in load(HERE/'base-repeat.json').values() for x in vs.values())
    spells=load(HERE/'spelling-replay.json')
    assert len(spells)==36 and all(p==k.endswith(('-spelling','-both')) for k,p in spells.items())
    hints=load(HERE/'hint-exposure.json')
    assert all(hints['b-'+k]['extra_tokens']==hints['c-'+k]['extra_tokens'] for k in ('6118','6137','7293'))
    scope=load(HERE/'source-accounting.json')
    assert scope['cumulative_count']==scope['prior_count']+len(scope['new_screened'])==56
    history=load(HERE/'prompt-results.json')
    for arm in 'abcd':
        print('prompt',arm,{k:sum(r['native'] for s,r in rows[arm].items()) for k,rows in history.items()})
    src=load(HERE/'controls.json')
    assert all(len(r['checks'])==2 and all(c['gold']['pass'] and not c['wrong']['pass'] for c in r['checks']) for coll in ('elf','pe_and_rules') for r in src[coll].values() if r.get('ok',r.get('valid')))
    assert all(v['header_verified_section'] for v in src['pe_header_evidence'])
    assert len(load(HERE/'explanation-repairs.json')['rows'])==10
    assert not load(HERE/'source-accounting.json')['official_test_accessed']
    assert all(x['cleaned'] for x in load(HERE/'resources.json').values())
    prospect={k:v for k,v in data.items() if v[0]!='known_gap'}
    tools={'sample_6402':'blkid','sample_7538':'sanstats','sample_7395':'llvm-mca','sample_7411':'llvm-objcopy','sample_7413':'llvm-objcopy','sample_7500':'llvm-strip','sample_1605':'pepack','sample_2617':'pepack'}
    assert set(tools)==set(prospect)
    for tag in TAGS:
        tool_means=[]
        for tool in sorted(set(tools.values())):
            chosen={k:v for k,v in prospect.items() if tools[k]==tool}
            tool_means.append(summarize(chosen)[tag]/(3*len(chosen)))
        print(tag,'mean native success with each prospective tool weighted equally',round(sum(tool_means)/len(tool_means),3))
    for tag in ('B64','C64'):
        deltas=[]
        for drop in prospect:
            sub={k:v for k,v in prospect.items() if k!=drop}
            scores=summarize(sub)
            deltas.append(scores[tag]-scores['A64'])
        print(tag,'minus A64 net correct after omitting one prospective source:',min(deltas),max(deltas),'out of',3*(len(prospect)-1))

if __name__=='__main__':
    main()
