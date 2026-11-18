import collections, json, re, sqlite3
from pathlib import Path
from fixture import DATA, digest, save, FIELDS
from teacher import answer
from reason import checked

def read(path):return json.loads(path.read_text())

def verify():
    freeze=read(DATA/'freeze.json')
    for split,h in freeze['hashes'].items():assert digest((DATA/(split+'.json')).read_bytes())==h
    for split in freeze['hashes']:
        for row in read(DATA/(split+'.json')):
            p=DATA/(row['id']+'.db');raw=p.read_bytes()
            assert digest(raw)==freeze['files'][row['id']]==row['file_sha']
            o,w,q=FIELDS[row['field']]
            with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as db:value=db.execute('pragma '+q).fetchone()[0]
            assert row['answer']==dict(offset=o,width=w,value=value)
            assert row['evidence']==f'{o},{w},{raw[o:o+w].hex()}'
            for field in row['answer']:
                negative=dict(row['answer']);negative[field]+=1
                assert answer('<answer>'+json.dumps(negative)+'</answer>')!=row['answer']
def classify(raw,row):
    a=answer(raw['content']) if raw['stop'] else None
    return 'unknown' if a is None else 'pass' if a==row['answer'] else 'fail'
def prep():
    verify()
    train=read(DATA/'train.json');screen=read(DATA/'screen-result.json')
    rr=screen['responses'];keys=[(r['id'],r['thinking'],r['seed']) for r in rr]
    assert len(keys)==len(set(keys))==len(train)*6
    assert set(keys)=={(r['id'],m,s) for r in train for m in [False,True] for s in [3407,4407,5407]}
    diag=[];verified=[];gap=[]
    def target(r):return dict(id=r['id'],prompt=r['prompt'],target='<answer>'+json.dumps(r['answer'],separators=(',',':'))+'</answer>')
    identities=set()
    for i,r in enumerate(train):
        passed=[]
        for j in range(3):
            d=read(DATA/'teacher'/f'{i}-{j}.json');identities.add(d['model'])
            assert d['id']==r['id'] and d['seed']==8407+i+1000*j
            ev=re.findall(r'<evidence>(.*?)</evidence>',d['content'],re.S)
            cert=d['stop']=='stop' and answer(d['content'])==r['answer'] and len(ev)==1 and ev[0].strip().lower()==r['evidence']
            assert cert==d['cert']
            if cert:passed.append('<evidence>'+ev[0]+'</evidence>')
        counts={str(m):dict(collections.Counter(classify(z,r) for z in rr if z['id']==r['id'] and z['thinking']==m)) for m in [False,True]}
        is_gap=len(passed)>=2 and all(v.get('fail',0)>=2 for v in counts.values())
        diag.append(dict(id=r['id'],family=r['field'],teacher=len(passed),counts=counts,gap=is_gap))
        expl=read(DATA/'explanations'/f'{i}.json')
        if len(passed)>=2 and expl['admitted']:
            assert checked(expl['reason'],r) and any(expl['reason'] in a['text'] for a in expl['attempts'])
            v=dict(**target(r),evidence_target=expl['reason'])
            verified.append(v)
            if is_gap:gap.append(v)
    assert len(identities)==1
    save(DATA/'diagnosis.json',dict(rows=diag,teacher=list(identities)))
    assert verified,'No repeatedly verified teacher examples with verified derivations'
    rows=gap if len(gap)>=8 else verified
    replay=[target(r) for r in read(DATA/'replay.json')]
    ev=[{k:r[k] for k in ['id','prompt']} for s in ['holdout','retention'] for r in read(DATA/(s+'.json'))]
    save(DATA/'pair-input.json',dict(rows=rows,replay=replay,eval_inputs=ev))
    print(len(gap),'certified gaps;',len(rows),'training rows')
def score():
    verify();out=read(DATA/'pair-result.json');pair=read(DATA/'pair-input.json')
    assert out['model_revision']==read(DATA/'screen-result.json')['model_revision']
    a,b=out['answer'],out['reason'];assert a['init']==b['init'] and a['final']!=b['final']
    def objective(arm):return [{k:v for k,v in s.items() if k!='norm'} for s in arm['trace']]
    assert objective(a)==objective(b) and len(a['trace'])==4*len(pair['rows'])
    assert all(t['answer_weight']==1 and t['replay_weight']==.25 for t in a['trace']+b['trace'])
    ds=read(DATA/'diagnosis.json');diag=ds['rows']
    res=dict(student_revision=out['model_revision'],teacher=ds['teacher'],screened=len(diag),
             teacher_pass_two=sum(r['teacher']>=2 for r in diag),dual_mode_confirmed_gaps=sum(r['gap'] for r in diag),
             by_family={k:sum(r['gap'] for r in diag if r['family']==k) for k in sorted({r['family'] for r in diag})},
             trained=len(pair['rows']),steps_per_arm=len(a['trace']),coefficients={'answer':1,'replay':.25,'evidence_reasoning_only':.5},
             answer_replay_tokens_and_order_match=True,base_init_sha=a['init'],final_sha={k:out[k]['final'] for k in ['answer','reason']},
             freeze_sha=digest((DATA/'freeze.json').read_bytes()),panels={})
    for split in ['holdout','retention']:
        truth=read(DATA/(split+'.json'));preds={};stats={}
        for arm,raw in [('base',out['base']),('answer',a['responses']),('reason',b['responses'])]:
            assert len(raw)==len({r['id'] for r in raw})==len(pair['eval_inputs'])
            idx={r['id']:r for r in raw}
            preds[arm]=[classify(idx[r['id']],r) for r in truth]
            stats[arm]=dict(collections.Counter(preds[arm]))
        swap={}
        for new,old in [('answer','base'),('reason','base'),('reason','answer')]:
            p=list(zip(preds[new],preds[old]))
            swap[new+'-'+old]=dict(wins=sum(x=='pass' and y!='pass' for x,y in p),losses=sum(x!='pass' and y=='pass' for x,y in p))
        res['panels'][split]=dict(files=len(truth),outcomes=stats,paired=swap)
    save(DATA/'summary.json',res);print(json.dumps(res,indent=2))
if __name__=='__main__':
    import sys
    (prep if sys.argv[1]=='prep' else score)()
