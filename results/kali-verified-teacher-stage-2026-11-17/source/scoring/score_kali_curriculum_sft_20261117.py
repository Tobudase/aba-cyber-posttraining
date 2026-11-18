"""Host-only frozen metrics with per-seed retention gates."""
import hashlib,json,math
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save
from kali_reference_score_v3_20261117 import score as strict_score
from kali_reference_score_v2_20261117 import output_command
from benchkit import native_kali
STAGE=OUT/'paired-sft'
def summarize(rows):
    return {'n':len(rows),'correct':sum(r['correct'] for r in rows),'invalid':sum(not r['valid'] for r in rows),'truncated':sum(r['truncated'] for r in rows),'native_partial_mean':sum(r['native_partial'] for r in rows)/len(rows),'tokens':sum(r['tokens'] for r in rows),'unresolved_equivalence':sum(r['equivalence_status'].startswith('UNKNOWN') for r in rows)}
def score_predictions(path):
    freeze=json.loads((OUT/'method-freeze.json').read_text());assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==freeze['scripts_sha256'][Path(__file__).name],'Host grader changed after freeze'
    ep=json.loads((STAGE/'evaluation-protocol.json').read_text());assert hashlib.sha256((ROOT/'scripts/kali_reference_score_v3_20261117.py').read_bytes()).hexdigest()==ep['strict_scorer_sha256']
    refs=json.loads((STAGE/'evaluation-references-private.json').read_text());inputs=json.loads((STAGE/'evaluation-inputs-private.json').read_text());expected={(seed,mode,r['id']) for seed in ep['seeds'] for mode in ep['modes'] for r in inputs}
    data=json.loads(Path(path).read_text());assert data['status']=='COMPLETE' and {(r['sampling_seed'],r['mode'],r['id']) for r in data['predictions']}==expected and len(data['predictions'])==len(expected)
    sc=native_kali();details=[];summary={};per_seed={}
    for r in data['predictions']:
        if r['id'] not in refs:continue
        valid=output_command(r['content'],r['finish_reason']=='stop') is not None;strict=strict_score(refs[r['id']],r['content'],r['finish_reason']=='stop');native=sc.score_one(refs[r['id']],r['content']) if valid else {'total_score':0}
        details.append({'id':r['id'],'mode':r['mode'],'sampling_seed':r['sampling_seed'],'panel':r['panel'],'correct':strict['reference_equal'],'equivalence_status':strict['status'],'valid':valid,'truncated':r['finish_reason']=='length','tokens':r['generated_tokens'],'native_partial':native['total_score']})
    for seed in ep['seeds']:
        per_seed[str(seed)]={mode:{panel:summarize([r for r in details if r['sampling_seed']==seed and r['mode']==mode and r['panel']==panel]) for panel in ['development24','old64']} for mode in ep['modes']}
    for mode in ep['modes']:
        summary[mode]={}
        for panel in ['development24','old64']:
            rr=[r for r in details if r['mode']==mode and r['panel']==panel];s=summarize(rr);s['mean_correct_per_seed']=s['correct']/len(ep['seeds']);s['unique_examples']=s['n']//len(ep['seeds']);s['unique_at_least_two_success']=sum(sum(r['correct'] for r in rr if r['id']==id)>=2 for id in {r['id'] for r in rr});summary[mode][panel]=s
    return {'summary':summary,'per_seed':per_seed,'details':details,'adapter_sha256':data.get('adapter_sha256'),'reload_audit':data.get('reload_audit'),'seconds':data['seconds']}
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
def main():
    folder=STAGE/'runs/pair';base=score_predictions(folder/'base-predictions.json');results={'E0':dict(grade(base,base),score=0.,eligible=True)};details={'E0':base}
    for arm in ['answer_only','reasoning']:
        r=score_predictions(folder/(arm+'-predictions.json'));results[arm]=grade(r,base);details[arm]=r
    save(folder/'score-private.json',{'status':'PAIRED_SFT_HOST_SCORED','results':results,'details':details,'selection_frozen':False,'confirmation_queries':0,'official_TEST_queries':0})
    print(json.dumps({'status':'PAIRED_SFT_HOST_SCORED','results':{k:{'eligible':v['eligible'],'score':v['score'],'summary':v['summary']} for k,v in results.items()}},indent=2))
if __name__=='__main__':main()
