"""Exact host grading function, with private file I/O removed."""
import math

def grade(result,base):
    retention={};eligible=True
    for seed in base['per_seed']:
        retention[seed]={}
        for mode in ['thinking','nonthinking']:
            ids={r['id'] for r in base['details'] if str(r['sampling_seed'])==seed and r['mode']==mode and r['panel']=='old64' and r['correct']}
            kept=sum(r['id'] in ids and r['correct'] for r in result['details'] if str(r['sampling_seed'])==seed and r['mode']==mode and r['panel']=='old64');b=base['per_seed'][seed][mode];s=result['per_seed'][seed][mode]
            guard=bool(ids) and kept>=math.ceil(.95*len(ids)) and s['old64']['correct']>=b['old64']['correct'] and all(s[p]['invalid']<=b[p]['invalid'] and s[p]['truncated']<=b[p]['truncated'] for p in ['development24','old64'])
            retention[seed][mode]={'kept':kept,'base_correct':len(ids),'rate':kept/len(ids) if ids else None,'guard_pass':guard};eligible &= guard
    s=result['summary']['thinking'];b=base['summary']['thinking'];score=(s['development24']['mean_correct_per_seed']-b['development24']['mean_correct_per_seed'])+.001*(s['old64']['mean_correct_per_seed']-b['old64']['mean_correct_per_seed'])
    lost=sum(v['base_correct']-v['kept'] for seed in retention.values() for v in seed.values())
    return {'eligible':eligible,'score':score if eligible else -100-lost,'unpenalized_score':score,'retention':retention,'summary':result['summary'],'per_seed':result['per_seed'],'no_official_TEST':True,'confirmation_queries':0,'scope':'Three paired inference seeds, one training seed. Exposed internal reference diagnostics, not independent official accuracy or three independent training replications.'}
