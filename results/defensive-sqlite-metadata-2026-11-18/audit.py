"""Recompute paired results from the collected jobs and the frozen SQLite files."""
import json
import math
from collections import Counter
from itertools import combinations
from fixture import DATA, ROOT, digest
from evaluate import read, verify, classify
from match import outcome
from reason import checked

def audit():
    verify()
    frozen = read(DATA / 'training-freeze.json')
    for name, key in [('pair-input', 'inputs'), ('matched-screen', 'matched_screen'), ('diagnosis', 'teacher_screen')]:
        assert digest((DATA / (name + '.json')).read_bytes()) == frozen[key]
    pair = read(DATA / 'pair-input.json')
    output = read(DATA / 'pair-result.json')
    train = read(DATA / 'train.json')
    screen = read(DATA / 'screen-result.json')['responses']
    long_finished=(DATA/'long-result.json').exists()
    long=read(DATA/'long-result.json')['responses'] if long_finished else []
    pool = read(DATA / 'long-input.json')
    train_lookup = {r['id']: r for r in train}
    selected = {r['id'] for r in pair['rows']}
    required = set()
    teacher_counts = []
    for i, r in enumerate(train):
        teacher = [read(DATA/'teacher'/f'{i}-{j}.json') for j in range(3)]
        assert len({t['seed'] for t in teacher}) == 3
        passed = sum(t['cert'] for t in teacher)
        teacher_counts.append(passed)
        student_fails = sum(outcome(z, r) == 'fail' for z in screen if z['id'] == r['id'] and not z['thinking'])
        explanation = read(DATA/'explanations'/f'{i}.json')
        if passed >= 2 and student_fails >= 2 and explanation['admitted']:
            assert checked(explanation['reason'], r)
            required.add(r['id'])
    assert selected == required == {p['id'] for p in pool}
    roles = {s: {r['id'] for r in read(DATA/(s+'.json'))} for s in ('train', 'holdout', 'replay','retention')}
    assert all(roles[a].isdisjoint(roles[b]) for a,b in combinations(roles,2))
    assert {r['id'] for r in pair['eval_inputs']} == roles['holdout'] | roles['retention']
    assert all(set(row) == {'id', 'prompt'} for row in pair['eval_inputs'])
    assert {r['id'] for r in pair['replay']} == roles['replay']
    def aggregate(responses, ids):
        return dict(Counter(outcome(z, train_lookup[z['id']]) for z in responses if z['id'] in ids))
    jobs = {}
    for phase in (['screen','long','pair'] if long_finished else ['screen','pair']):
        folder = ROOT.parent/'data/benchkit/kali-execution-2026-11-14'/('miw113-metadata-'+phase+'-1118'+read(DATA/'job-suffixes.json')[phase])
        host = read(folder/'host.json')
        assert host['status']=='SUCCEEDED'
        objects = read(folder/'objects.json')
        contents = objects[0]['data']
        task = json.loads(contents['task.json'])
        if phase == 'pair':
            assert all(task[key]==value for key,value in pair.items())
            assert digest(contents['model_run.py'].encode()) == frozen['worker']
            assert digest((ROOT/'model_run.py').read_bytes()) == frozen['worker']
        result = read(DATA/(phase+'-result.json'))
        jobs[phase] = dict(uid=host['uid'], submitted=host['submitted_at_utc'],
                           finished=host['job_status']['completionTime'],
                           gpu=result.get('gpu'), task_sha256=digest(contents['task.json'].encode()),
                           result_sha256=digest((DATA/(phase+'-result.json')).read_bytes()))
    long_by_file = {t['id']:aggregate(long, {t['id']}) for t in pool}
    both = sum(vals.get('fail',0)>=2 for vals in long_by_file.values())
    matched = read(DATA/'matched-screen.json')
    assert matched['used']==len(selected)
    if long_finished:
        assert len(long)==3*len(pool)
        assert {(r['id'],r['seed']) for r in long} == {(r['id'],s) for r in pool for s in (7407,8407,9407)}
    for arm in ('answer','reason'):
        trace=output[arm]['trace']
        assert len(trace)==4*len(selected)
        assert all(math.isfinite(t['norm']) and t['norm']>0 for t in trace)
        assert {name:sum(t['id']==name for t in trace) for name in selected}==dict.fromkeys(selected,4)
        assert {t['replay'] for t in trace}==roles['replay']
    # Independent scoring with zip-by-id; cover every held-out output, including nonanswers.
    summary=read(DATA/'summary.json')
    semantic_panels={}
    for split in ('holdout','retention'):
        gold=read(DATA/(split+'.json'))
        semantic_panels[split]={}
        strict=summary['panels'][split]
        scores={}
        for arm in ('base','answer','reason'):
            pred=output[arm] if arm=='base' else output[arm]['responses']
            by_id={r['id']:r for r in pred}
            assert set(by_id)==roles['holdout']|roles['retention']
            assert all(not r['thinking'] and r['seed']==3407 for r in pred)
            triples=[classify(by_id[r['id']],r) for r in gold]
            assert dict(Counter(triples))==strict['outcomes'][arm]
            scores[arm]=[outcome(by_id[r['id']],r) for r in gold]
            semantic_panels[split][arm]=dict(Counter(scores[arm]))
        switches={}
        for new,old in [('answer','base'),('reason','base'),('reason','answer')]:
            paired=list(zip(scores[new],scores[old]))
            switches[new+'-'+old]=dict(wins=sum(a=='pass' and b!='pass' for a,b in paired),
                                        losses=sum(a!='pass' and b=='pass' for a,b in paired))
        semantic_panels[split]['paired']=switches
    failed = read(ROOT.parent/'data/benchkit/kali-execution-2026-11-14/miw113-metadata-long-1118g/host.json')
    assert failed['status']=='FAILED' and failed['resources_cleaned']
    excluded = dict(failed_long_gpu_kernel_launch=dict(uid=failed['uid'], predictions_scored=0),
                    unassigned_generic_training_route=read(DATA/'pair-route-change.json'))
    return dict(jobs=jobs,operational_attempts_excluded=excluded,teacher_verified_counts_histogram=dict(Counter(teacher_counts)),
                deployment_gap_files=len(pool), trained_files=len(selected), long_screen_complete=long_finished,also_confirmed_with_long_thinking=both if long_finished else None,
                long_student_responses=aggregate(long,selected) if long_finished else None, nonthinking_on_matched_files=aggregate([r for r in screen if not r['thinking']],selected),
                short_thinking_cutoffs=sum(not r['stop'] for r in screen if r['thinking']),
                long_thinking_cutoffs=sum(not r['stop'] for r in long) if long_finished else None, semantic_panels=semantic_panels,
                protocol_amendment=read(DATA/'extended-screen-protocol.json'))
