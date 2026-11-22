"""Offline recount for every native database result, prompt pair, and control."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
result = json.loads((here / 'results.json').read_text())
protocol = json.loads((here / 'protocol.json').read_text())
assert len(protocol['probes']) == 6 and len(protocol['seeds']) == 2
assert len(set(result['adapter_parameter_sha256'].values())) == 2
assert all(len(values) == 16 for values in result['losses'].values())
for arm, rows in result['draws'].items():
    pairs = {}
    for row in rows:
        key = row['seed'], row['file']
        pair = pairs.setdefault(key, {})
        assert row['retain'] not in pair
        files = row['fixtures']
        assert len(files) == (3 if row['executed'] else 0)
        assert row['semantic'] == (bool(files) and all(f['rc'] == 0 and f['match'] for f in files))
        assert row['strict'] == (row['semantic'] and row['format_ok'])
        pair[row['retain']] = row['strict']
    assert len(pairs) == 6 and all(set(pair) == {True, False} for pair in pairs.values())
    totals = dict(
        both=sum(all(pair.values()) for pair in pairs.values()),
        omit=sum(pair[False] for pair in pairs.values()),
        retain=sum(pair[True] for pair in pairs.values()),
        format=sum(row['format_ok'] for row in rows),
        semantic=sum(row['semantic'] for row in rows),
        strict=sum(row['strict'] for row in rows),
    )
    assert totals == result['counts'][arm]
    print(arm, totals)
for name, check in result['controls'].items():
    assert len(check['fixtures']) == 3 and all(f['rc'] == 0 for f in check['fixtures'])
    assert all(f['match'] for f in check['fixtures']) == name.endswith('_gold')
print('Native references and both intentionally wrong alternatives verified for each direction.')
for file,prefix,short_arm in [('sensitivity.json','base4096','base'),('aux-sensitivity.json','explain4096','paired-explain16')]:
    record=json.loads((here/file).read_text())
    rows={k:v for k,v in record.items() if k.startswith(prefix+'_')}
    assert len(rows)==12
    completed=[]
    for key,row in rows.items():
        _,seed,index=key.split('_')
        old=[v for v in result['draws'][short_arm] if v['seed']==int(seed)][int(index)]
        assert old['ended']==row['short_ended']
        if old['ended']:
            assert old['tokens']==row['tokens'] and old['command']==row['command']
        else:
            assert row['tokens']>=1024
        assert row['semantic']==(len(row['fixtures'])==3 and all(f['rc']==0 and f['match'] for f in row['fixtures']))
        completed.append(row['semantic'] and row['format_ok'])
    print(prefix, 'extended-budget strict',sum(completed),'of 12')
if (here/'direct.json').exists():
    direct=json.loads((here/'direct.json').read_text())
    assert len(direct)==12
    for key,r in direct.items():
        assert r['semantic']==(len(r['fixtures'])==3 and all(f['rc']==0 and f['match'] for f in r['fixtures']))
        assert r['tokens']<=1024
    print('No-thinking, strict',sum(r['format_ok'] and r['semantic'] for r in direct.values()),'of 12')
last=json.loads((here/'remaining-error.json').read_text())
for key,obs in last['observed'].items():
    assert len(obs)==len(last['gold'])==3
    assert (obs==last['gold'])==('--no-not-null' in key.split())
print('Final long-budget error reproduced from native SQL hashes')
if (here/'matched-thinking.json').exists():
    matched=json.loads((here/'matched-thinking.json').read_text())
    assert len(matched)==12
    for row in matched.values():
        assert row['tokens']<=1024 and row['semantic']==(len(row['fixtures'])==3 and all(f['match'] and f['rc']==0 for f in row['fixtures']))
    print('Matched thinking-mode control, strict',sum(r['format_ok'] and r['semantic'] for r in matched.values()),'of 12')
