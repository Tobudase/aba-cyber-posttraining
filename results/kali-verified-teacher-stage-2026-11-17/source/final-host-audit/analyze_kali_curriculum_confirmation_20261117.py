"""Score the one frozen confirmation; never choose a model from these results."""
import hashlib,json,random
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save,sha
from kali_reference_score_v3_20261117 import score as strict_score
from kali_reference_score_v2_20261117 import output_command
from benchkit import native_kali
STAGE=OUT/'paired-sft';CONF=STAGE/'confirmation'
def main():
    freeze=json.loads((CONF/'selection-freeze-private.json').read_text());assert sha(STAGE/'native-selection-private.json')==freeze['selection_sha256']
    assert sha(CONF/'references-private.json')==freeze['reference_sha256'] and sha(CONF/'groups-private.json')==freeze['groups_sha256']
    refs=json.loads((CONF/'references-private.json').read_text());groups=json.loads((CONF/'groups-private.json').read_text());proto=json.loads((CONF/'evaluation-protocol.json').read_text());native=native_kali();summary={};details={}
    for state in freeze['states']:
        label=state['label'];p=CONF/'runs'/(label+'-predictions.json');data=json.loads(p.read_text());assert data['status']=='COMPLETE' and data.get('adapter_sha256')==state['pointer']['adapter_sha256']
        expected={(seed,mode,id) for seed in proto['seeds'] for mode in proto['modes'] for id in refs}
        assert len(data['predictions'])==len(expected) and {(r['sampling_seed'],r['mode'],r['id']) for r in data['predictions']}==expected
        scored=[]
        for r in data['predictions']:
            valid=output_command(r['content'],r['finish_reason']=='stop') is not None;s=strict_score(refs[r['id']],r['content'],r['finish_reason']=='stop')
            scored.append({'id':r['id'],'group':groups[r['id']],'seed':r['sampling_seed'],'mode':r['mode'],'correct':s['reference_equal'],'status':s['status'],'valid':valid,'truncated':r['finish_reason']=='length','tokens':r['generated_tokens'],'native_partial':native.score_one(refs[r['id']],r['content'])['total_score'] if valid else 0.})
        details[label]=scored;summary[label]={}
        for mode in proto['modes']:
            rr=[r for r in scored if r['mode']==mode]
            summary[label][mode]={'unique_tasks':24,'inference_samples':len(rr),'correct':sum(r['correct'] for r in rr),'mean_correct_per_seed':sum(r['correct'] for r in rr)/3,'unique_at_least_two_success':sum(sum(r['correct'] for r in rr if r['id']==id)>=2 for id in refs),'invalid':sum(not r['valid'] for r in rr),'truncated':sum(r['truncated'] for r in rr),'unresolved_equivalence':sum(r['status'].startswith('UNKNOWN') for r in rr),'native_partial_mean':sum(r['native_partial'] for r in rr)/len(rr),'tokens':sum(r['tokens'] for r in rr),'per_seed':{str(seed):{'correct':sum(r['correct'] for r in rr if r['seed']==seed),'n':24} for seed in proto['seeds']}}
    def resolve(label):return freeze['aliases'].get(label,label)
    paired={}
    for name,new,base in [('reasoning_minus_answer','fixed_reasoning','fixed_answer_only'),('reasoning_minus_E0','fixed_reasoning','E0'),('native_minus_E0','native_selected','E0')]:
        new,base=resolve(new),resolve(base);paired[name]={}
        for mode in proto['modes']:
            a={(r['seed'],r['id']):r for r in details[new] if r['mode']==mode};b={(r['seed'],r['id']):r for r in details[base] if r['mode']==mode}
            delta={id:sum(int(a[(seed,id)]['correct'])-int(b[(seed,id)]['correct']) for seed in proto['seeds'])/3 for id in refs};mean=sum(delta.values())/24
            rng=random.Random(20261117);unique=sorted(set(groups.values()));samples=[]
            for _ in range(5000):
                sampled=[rng.choice(unique) for _ in unique];values=[delta[id] for g in sampled for id in refs if groups[id]==g];samples.append(sum(values)/len(values))
            samples.sort();paired[name][mode]={'mean_correct_count_difference':mean*24,'percentage_point_difference':mean*100,'wins_across_inference_samples':sum(a[k]['correct'] and not b[k]['correct'] for k in a),'losses_across_inference_samples':sum(b[k]['correct'] and not a[k]['correct'] for k in a),'descriptive_group_bootstrap_interval_pp':[samples[125]*100,samples[4874]*100],'bootstrap_groups':len(unique),'interval_limit':'Panel composition only; one training seed, shared author/source, not independent real-world generalization guarantee'}
    result={'status':'POST_SELECTION_CONFIRMATION_SCORED_NO_RESELECTION','summary':summary,'aliases':freeze['aliases'],'paired':paired,'retained_model_before_confirmation':json.loads((STAGE/'native-selection-private.json').read_text())['candidate_id'],'retention_decision_changed_by_confirmation':False,'confirmation_unique_tasks':24,'official_TEST_queries':0,'details':details}
    save(CONF/'analysis-private.json',result);print(json.dumps({'status':result['status'],'summary':summary,'paired':paired},indent=2))
if __name__=='__main__':main()
