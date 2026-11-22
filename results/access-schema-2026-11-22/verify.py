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
