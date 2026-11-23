"""Offline recount of original sources, free model draws, contrast fixtures and matched SFT targets."""
import json
import hashlib
from pathlib import Path

def load(root, name):
    return json.loads((root/name).read_text())

def recount(root):
    evidence=load(root,'evidence.json')
    new=evidence['new_sources']
    assert len(new)==len(set(new))==18
    screened={i:r for i,r in new.items() if 'draws' in r}
    passes={m:0 for m in ('student','qwen','deepseek')}
    calls={m:0 for m in passes}
    accepted=[]
    for i,source in screened.items():
        for m in passes:
            draws=source['draws'][m]
            assert set(draws)=={'22103','22109','22111'}
            for row in draws.values():
                if row['result']=='pass':
                    assert row['fixture_matches']==[True,True]
                    passes[m]+=1
                calls[m]+=1
        student=source['draws']['student']
        if source.get('admitted'):
            assert source['attributed_student_error'] and source.get('reviewed_raw_traces')
            assert sum(r['result']!='pass' for r in student.values())>=2
            accepted.append(i)
        else:
            assert sum(r['result']=='pass' for r in student.values())>=2 or source.get('exclusion_basis')
    pairs=load(root,'pairs.json')
    assert set(pairs)=={'6137','7293','6118'}
    for source,variants in pairs.items():
        assert set(variants)=={'original','same','opposite','distractor'}
        for rows in variants.values():
            assert len(rows)==(2 if source=='6118' else 3) and any(r['distinguishes'] for r in rows)
            assert all(r['distinguishes']==(r['expected_sha256']!=r['reversed_sha256']) for r in rows)
        # Same filename and inputs: the opposite and distractor require identical outputs.
        assert variants['opposite']==variants['distractor']
        assert all(a['expected_sha256']==b['reversed_sha256'] and a['reversed_sha256']==b['expected_sha256']
                   for a,b in zip(variants['same'],variants['opposite']))
    labels=load(root,'matched-labels.json')
    for i,source in labels.items():
        arms=source['labels']
        assert arms['D']==arms['E'] and arms['A']['trace']==0
        assert all(len({v[k] for v in arms.values()})==1 for k in ('answer','format','visible','prompt'))
        assert all(arms[a]['trace']>0 for a in 'BCDE')
    previous=evidence['previous']
    assert set(previous['accepted'])|{'sample_'+i for i in accepted}==set(labels) and previous['screened']==19
    assert set(previous['accepted']).isdisjoint('sample_'+i for i in new)
    assert len(accepted)+len(previous['accepted'])==evidence['qualified_total']
    fmt=new['6118']['escape_repair']
    assert sorted(v['explanation_escape_insertions'] for v in fmt.values())==[0,1,1]
    assert len({v['unchanged_command_sha256'] for v in fmt.values()})==1
    assert all(v['behavior_matches']==[True,True] for v in fmt.values())
    assert not new['6118']['semantic_gap']
    raw=load(root,'format-replay.json')['student_visible']
    for seed,v in raw.items():
        row=fmt[seed]
        assert hashlib.sha256(v.encode()).hexdigest()==row['original_visible_sha256']
        if row['strict']:
            obj=json.loads(v)
        else:
            try:json.loads(v)
            except json.JSONDecodeError as err:
                assert err.msg==row['parser_error']
                where=v.index(chr(92)+'u00XX')
                assert abs(err.pos-where)<=1 and where>v.index('"explanation"')
                obj=json.loads(v[:where]+chr(92)+v[where:])
            else:raise ValueError('Expected JSON error')
        assert hashlib.sha256(obj['command'].encode()).hexdigest()==row['unchanged_command_sha256']
    total=previous['screened']+len(screened)
    assert total==evidence['screened_total']
    assert evidence['new_test_calls']==0 and evidence['new_confirmation_calls']==0 and evidence['new_training_runs']==0
    assert evidence['qualified_total']<evidence['min_train_sources']
    grads=load(root,'loss-check.json')['weights']
    for arm,sources in grads.items():
        for weights in sources.values():
            assert weights==dict(answer=1.0,format=.1,prompt=0.,visible=0.,trace=0. if arm=='A' else .5)
    adapter=load(root,'adapter-grades.json')
    assert set(adapter)=={'base','A16','A64','B64','C64'}
    print('retained adapter checks on one source, two decoding seeds')
    for arm,draws in adapter.items():
        assert set(draws)=={'11341','11351'}
        for seed,variants in draws.items():
            assert set(variants)=={'same','opposite','distractor'}
            for row in variants.values():
                assert row['strict']==(row['format'] and row['behavior'])
                if 'fixture_matches' in row:assert row['behavior']==all(row['fixture_matches'])
        p={k:sum(all(d[x][k] for x in ('same','opposite')) for d in draws.values()) for k in ('behavior','strict')}
        assert p==evidence['paired_checkpoints'][arm]
        print(arm,p)
    edits=load(root,'one-edit-grades.json');witness=load(root,'one-edit-witness.json')
    for seed,g in edits['original'].items():
        for variant,initial in g.items():
            fixed=edits['one_edit'][seed][variant]
            w=witness[seed+'-'+variant]
            x,y=w['original_command'],w['repaired_command']
            assert len(x)==len(y) and sum(a!=b for a,b in zip(x,y))==1
            assert x.replace('--no-not-empty','--no-not_empty')==y
            assert initial==adapter['base'][seed][variant]
            assert initial['issue']=='native-error' and fixed['fixture_matches']==[True]*3 and fixed['strict']
    additional=load(root,'adapter-edits.json');notes=load(root,'adapter-edit-witness.json')
    assert set(additional)==set(notes)
    for key,edits_for_seed in additional.items():
        old=notes[key]['original_command'].split();new=notes[key]['modified_command'].split()
        assert new==old[:-1]+notes[key]['modified_argv']+old[-1:]
        arm,seed,variant,label=key.split('-')
        after=edits_for_seed[seed][variant]
        assert not adapter[arm][seed][variant]['behavior'] and after['format']==adapter[arm][seed][variant]['format']
    print('unique sources screened:',total,'of which newly screened:',len(screened))
    print('new valid-JSON and behavior passes / calls:',{m:(passes[m],calls[m]) for m in passes})
    print('common training sources:',evidence['qualified_total'],'of',evidence['min_train_sources'],'required')
    print('contrast probes:',sum(map(len,pairs.values())),'fixture-direction checks:',sum(len(v) for p in pairs.values() for v in p.values()))
    print('matched auxiliary token lengths:',{i:s['labels']['D']['trace'] for i,s in labels.items()})
    return passes,calls
if __name__=='__main__':recount(Path(__file__).resolve().parent)
