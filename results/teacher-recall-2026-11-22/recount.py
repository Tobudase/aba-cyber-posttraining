"""Recompute results using public hashes, per-draw grades, and the prior checkpoint report."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def recount_recall():
    d = read(HERE/'recall.json')
    prior = read(HERE.parent/'readonly-teacher-match-2026-11-22/single-aligned-results.json')
    exposures = read(HERE.parent/'readonly-teacher-match-2026-11-22/trace-exposures.json')
    assert d['training_seed'] == prior['seed'] and d['decoding_seed'] == prior['decode_seed']
    assert d['rows']['base'] == d['rows']['base_recheck']
    hits = []
    for tag, probes in d['rows'].items():
        assert set(probes) == {'train', 'fresh', 'contrast'}
        for name, row in probes.items():
            old = prior['details'][tag+'-'+name]
            assert (row['native_behavior'], row['strict']) == (old['behavior'], old['strict'])
            for arm, target in d['teachers'].items():
                assert target['raw_sha256'] == exposures[arm]['raw_sha256']
                same = row['trace_sha256'] == target['normalized_sha256']
                assert same == row['comparison'][arm]['exact']
                if same:
                    assert row['closed'] and row['ended'] and row['strict']
                    assert row['trace_tokens'] == target['tokens'] == row['comparison'][arm]['common_prefix_tokens']
                    hits.append((tag, name, arm, target['tokens']))
    assert sorted(hits) == [('B64','train','B',1027), ('C64','train','C',430)]
    for i, case in enumerate(('train','fresh','contrast')):
        mentions = d['rows']['base'][case]['spelling_mentions']
        assert mentions == {'--no-not_empty':0,'--no-not-empty':(4,5,3)[i]}
    print('Original training prompt: exact trajectory matches', hits)


def recount_transfer():
    data = read(HERE/'transfer.json')
    assert data['training_source'] == 'sample_6137'
    assert data['seeds'] == [22103,22109,22111]
    assert set(data['sources']) == {'sample_6118', 'sample_7293'}
    totals = Counter()
    for source, arms in data['sources'].items():
        assert set(arms) == {'base','A64','B64','C64'}
        for arm, seeds in arms.items():
            assert set(seeds) == {str(s) for s in data['seeds']}
            passed = 0
            for row in seeds.values():
                if row['strict_pass']:
                    assert row['ended'] and row['closed'] and row['native_fixture_matches'] == [True, True]
                    assert row['result'] == 'pass'
                    passed += 1
            print(source, arm, f'{passed}/3')
            totals[arm] += passed
    assert dict(totals) == {'base':2,'A64':0,'B64':1,'C64':5}
    llvm=data['sources']['sample_7293']
    for arm in ('base','A64','B64'):
        assert all(r['result']=='missing-executable' and r['after_adding_executable']==[True,True]
                   for r in llvm[arm].values())
    assert all(r['strict_pass'] for r in llvm['C64'].values())
    db=data['sources']['sample_6118']
    repairs=[(a,r['one_escape_replay']) for a,ss in db.items() for r in ss.values()
             if 'one_escape_replay' in r]
    assert len(repairs)==4
    assert all(r['insertions']==1 for a,r in repairs)
    assert sum(r['fixture_matches']==[True,True] for a,r in repairs)==3
    assert [(a,r['exit_codes']) for a,r in repairs if not all(r['fixture_matches'])]==[('C64',[1,1])]
    assert all(r['result']=='behavior-error' and r['native_fixture_matches']==[False,False]
               for r in db['A64'].values())
    assert len(data['jobs'])==4 and all(r['released'] for r in data['jobs'].values())
    return dict(totals)


if __name__ == '__main__':
    recount_recall()
    print('Totals across two diagnostic sources:', recount_transfer())
