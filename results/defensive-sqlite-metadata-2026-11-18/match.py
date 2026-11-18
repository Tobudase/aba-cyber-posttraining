"""Additional TRAIN-only confirmation for the same deployment-mode error."""
import json
from fixture import DATA,save
from semantic import semantic

def read(p):return json.loads(p.read_text())
def outcome(z,r):
    v=semantic(z['content']) if z['stop'] else None
    return 'unknown' if v is None else 'pass' if v==r['answer'] else 'fail'

def select():
    train=read(DATA/'train.json');raw=read(DATA/'screen-result.json')['responses'];rows=[]
    for i,r in enumerate(train):
        passed=sum(read(DATA/'teacher'/f'{i}-{j}.json')['cert'] for j in range(3))
        wrong=sum(outcome(z,r)=='fail' for z in raw if z['id']==r['id'] and not z['thinking'])
        if passed>=2 and wrong>=2:rows.append({k:r[k] for k in ('id','prompt')})
    save(DATA/'long-input.json',rows);return rows
