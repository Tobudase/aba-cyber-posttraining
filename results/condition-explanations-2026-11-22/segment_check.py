"""Numerical regression check on the real per-token masks, with synthetic logits and no model weights."""
import json
import itertools
from pathlib import Path
import torch
import torch.nn.functional as F
W=Path(__file__).resolve().parent
WEIGHTS={'answer':1.0,'format':0.1,'trace':0.5}
def loss(logits,labels,segments):
    shifted=F.cross_entropy(logits[:-1],labels[1:],reduction='none')
    loss=shifted.new_zeros(())
    for part,weight in WEIGHTS.items():
        mask=torch.tensor([t==part for t in segments[1:]],device=shifted.device)
        if mask.any():loss=loss+weight*shifted[mask].mean()
    return loss
def main():
    private=W/'private/encoded.json'
    layout=W/'label-layout.json'
    if private.exists():
        records=json.loads(private.read_text())
        compact={i:{a:[[name,len(list(tokens))] for name,tokens in itertools.groupby(row['segments'])] for a,row in arms.items()} for i,arms in records.items()}
        layout.write_text(json.dumps(compact,indent=2)+'\n')
    else:
        compact=json.loads(layout.read_text())
        records={}
        for i,arms in compact.items():
            records[i]={}
            for a,spans in arms.items():
                segments=[name for name,count in spans for _ in range(count)]
                records[i][a]={'segments':segments,'input_ids':list(range(len(segments)))}
    results={}
    torch.set_num_threads(1)
    for arm in 'ABCDE':
        rows=[];info=[]
        for i,arms in records.items():
            row=arms[arm];ids=torch.tensor(row['input_ids'])%7
            logits=torch.zeros(len(ids),7,dtype=torch.double,requires_grad=True)
            rows.append(loss(logits,ids,row['segments']));info.append((i,row,ids,logits))
        batch=torch.stack(rows).mean()
        batch.backward()
        result={}
        for i,row,ids,z in info:
            n=len(ids)
            grad=z.grad[torch.arange(n-1),ids[1:]]
            empirical={}
            for part in ('prompt','visible','format','trace','answer'):
                mask=torch.tensor([t==part for t in row['segments'][1:]])
                # At uniform logits the absolute gradient on each correct next-token logit is 6/7.
                # Undo that factor and the two-item batch mean to recover the total segment weight.
                mass=float(-grad[mask].sum()*7/6*len(rows))
                target=WEIGHTS.get(part,0.0) if mask.any() else 0.
                assert abs(mass-target)<1e-9
                empirical[part]=round(mass,6)
            assert torch.count_nonzero(z.grad[-1])==0
            result[i]=empirical
        results[arm]=result
    (W/'loss-check.json').write_text(json.dumps(dict(method='Next-token cross-entropy, uniform synthetic seven-class logits, real tokenizer masks; mean over examples after segment normalization.',weights=results),indent=2)+'\n')
    print('Gradient weights verified on',len(records)*5,'encoded source/arm pairs.')
if __name__=='__main__':main()
