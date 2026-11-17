"""Score a completed fixed comparison; no model calls or checkpoint selection."""
import argparse,hashlib,importlib.util,json,math,re
from pathlib import Path
from benchkit import strict_option_values

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--runs',type=Path,required=True);p.add_argument('--scorer',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    ep=json.loads((a.stage/'evaluation-protocol.json').read_text());assert hashlib.sha256(a.scorer.read_bytes()).hexdigest()==ep['scorer_sha256']
    spec=importlib.util.spec_from_file_location('frozen_score',a.scorer);sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
    refs=json.loads((a.stage/'evaluation-references-private.json').read_text());inputs=json.loads((a.stage/'evaluation-inputs-private.json').read_text());assert hashlib.sha256((a.stage/'evaluation-inputs-private.json').read_bytes()).hexdigest()==ep['input_sha256']
    details={};summary={}
    for arm in ['base','answer_only','reasoning']:
        d=json.loads((a.runs/(arm+'-predictions.json')).read_text());assert d['status']=='COMPLETE'
        assert [r['id'] for r in d['predictions']]==[r['id'] for r in inputs]
        scored=[]
        for r in d['predictions']:
            text=r['content'];matches=re.findall(r'<output>\s*([\s\S]*?)\s*</output>',text)
            valid=r['finish_reason']=='stop' and len(matches)==1 and text.count('<output>')==text.count('</output>')==1 and bool(matches[0].strip())
            final='<output>'+matches[0].strip()+'</output>' if valid else ''
            n=sc.score_one(refs[r['id']],final)
            scored.append({'id':r['id'],'panel':r['panel'],'strict':bool(valid and strict_option_values(refs[r['id']],final,sc)),'partial':n['total_score'] if valid else 0.,'invalid':not valid,'truncated':r['finish_reason']=='length','tokens':r['generated_tokens']})
        details[arm]=scored
        summary[arm]={panel:{'n':len(rr),'strict':sum(x['strict'] for x in rr),'native_partial':sum(x['partial'] for x in rr)/len(rr),'invalid':sum(x['invalid'] for x in rr),'truncated':sum(x['truncated'] for x in rr),'tokens':sum(x['tokens'] for x in rr)} for panel in ['development24','old64'] if (rr:=[x for x in scored if x['panel']==panel])}
    baseold={r['id'] for r in details['base'] if r['panel']=='old64' and r['strict']};retention={}
    for arm in ['answer_only','reasoning']:
        kept=sum(r['id'] in baseold and r['strict'] for r in details[arm]);denom=len(baseold)
        retention[arm]={'kept':kept,'base_correct':denom,'rate':kept/denom if denom else None,'guard_pass':bool(denom and kept>=math.ceil(.95*denom) and summary[arm]['old64']['invalid']<=summary['base']['old64']['invalid'] and summary[arm]['old64']['truncated']<=summary['base']['old64']['truncated'])}
    result={'status':'FIXED_PAIR_SCORED','summary':summary,'retention':retention,'DEV_strict_reasoning_minus_answer_only':summary['reasoning']['development24']['strict']-summary['answer_only']['development24']['strict'],'details':details,'promotion':False,'confirmation_queries':0,'official_TEST_queries':0,'scope':'One-seed fixed pilot, reference metrics only; no independent generalization claim'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'summary':summary,'retention':retention},indent=2))
if __name__=='__main__':main()
