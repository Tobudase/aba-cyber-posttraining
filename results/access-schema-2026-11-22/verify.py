"""Recount saved fixture outcomes and metamorphic controls without model access."""
import json
from pathlib import Path
s=json.loads(Path(__file__).with_name('screen.json').read_text())
counts={}
for arm in ('student','qwen','deepseek'):
    rows=[x for x in s['draws'] if x['arm']==arm]
    assert [x['seed'] for x in rows]==s['seeds']
    for row in rows:
        assert row['passed']==all(x['match'] and x['rc']==0 for x in row['fixtures'])
        assert len(row['fixtures'])==3
    counts[arm]=sum(r['passed'] and r['explanation_correct'] for r in rows)
assert counts=={'student':0,'qwen':3,'deepseek':2}
assert len(s['prior_counterfactuals'])==3 and all(c=={'before':1,'after':0,'match_gold':True} for draw in s['prior_counterfactuals'].values() for c in draw['checks'])
assert s['reverse_control']==[1,1,1] and s['default_37_observed']
assert sum(all(row) for row in s['extension_controls'].values())==4
assert s['labels']['A']['answer']==s['labels']['B']['answer']==39
print(counts)
m=json.loads(Path(__file__).with_name('sft.json').read_text())
assert m['init_equal'] and set(m['adapters'])=={'A','B'}
assert len({v['weights'] for arm in m['adapters'].values() for v in arm.values()})==6
expectations={'base':(0,0,0),'A-16':(1,1,1),'A-32':(1,1,0),'A-64':(1,1,0),'B-16':(0,0,0),'B-32':(0,1,1),'B-64':(1,1,0)}
for arm,expected in expectations.items():
    observed=[]
    for kind in ('train','fresh','contrast'):
        v=m['probes'][arm][kind]
        fixtures=v['fixture_checks']
        assert (len(fixtures)==3 and all(f['rc']==0 and f['match'] for f in fixtures))==v['passed']
        assert v['ended'] and v['generated_tokens']<m['training']['eval_token_cap']
        observed.append(int(v['passed']))
    assert tuple(observed)==expected
print('21 sampled completions and 6 checkpoint hashes verified')
fmt=json.loads(Path(__file__).with_name('format-replay.json').read_text())
assert len(fmt['counters'])==6 and all(r['strict_final_reproduced'] and r['ended'] for r in fmt['counters'].values())
assert all(fmt['counters'][k]['closing_think_tags']==0 and fmt['counters'][k]['opening_output_tags']==fmt['counters'][k]['closing_output_tags']==1 for k in fmt['recovered'])
assert all(r['match'] for r in fmt['checks']['32-train']['fixtures'])
assert all(r['rc']==1 and 'Unknown option --no-no-empty' in r['err'] for r in fmt['checks']['64-contrast']['fixtures'])
print('Replayed missing-delimiter cases verified')
extra=json.loads(Path(__file__).with_name('extra-screen.json').read_text())
assert len(extra['draws'])==4
assert all(len(draws)==3 and all(d['fixture_pass']==[True,True] and d['rc']==[0,0] for d in draws.values()) for draws in extra['draws'].values())
print('12/12 extra draws passed on two fixtures each')
