"""Behavior-only replay with default dictionary handling made explicit."""
import json,re,shlex
from history_worker import folder,invoke,INPUT
from kali_framed_artifacts_20261117 import emit
def score(i,g,row,dirs):
    if not row['ended']:return {'result':'truncated'}
    try:
        x=json.loads(row['visible'])
        if not row['closed'] or set(x)!={'command','explanation'} or not all(isinstance(v,str) and v.strip() for v in x.values()):raise ValueError()
        a=shlex.split(x['command'])
    except (ValueError,TypeError):return dict(result='format')
    allowed={
        '6115':{'-U','--no-unprintable','sales.mdb','customers'},
        '6118':{'-U','--no-unprintable','network.mdb','devices'},
        '6234':{'--ignore-case','--alphanum','adm'},
        '6539':{'-d','--divisor','--divisor=2048','2048','1024','system.iso'}}
    if not a:return dict(result='format')
    if a[0]=='/usr/bin/'+g[0]:a[0]=g[0]
    if a[0]!=g[0] or any(t not in allowed[i] and not (i=='6234' and re.fullmatch('-[df]+',t)) for t in a[1:]):
        return dict(result='unreviewed',argv=a)
    if i=='6234':
        flags=''.join(z[1:] for z in a if z.startswith('-') and not z.startswith('--'))
        if not (('f' in flags or '--ignore-case' in a) and ('d' in flags or '--alphanum' in a)):
            return dict(result='unverified-default-dictionary')
    hits=[]
    for d in dirs:
        gold=invoke(i,g,d);obs=invoke(i,a,d)
        assert gold['rc']==0
        ok=obs['rc']==0 and obs['out']==gold['out']
        if i in ('6115','6118') and obs['rc']==0:
            try:ok=json.loads(obs['out'])==json.loads(gold['out'])
            except ValueError:ok=False
        hits.append(ok)
    return dict(result='pass' if all(hits) else 'behavior-error',fixture_matches=hits)
if __name__=='__main__':
    rows=json.loads((INPUT/'draws.json').read_text());dirs=[folder(v) for v in range(2)]
    emit({i:{m:{s:score(i,r['gold'],call,dirs) for s,call in samples.items()} for m,samples in r['draws'].items()} for i,r in rows.items()},'RESULT')
