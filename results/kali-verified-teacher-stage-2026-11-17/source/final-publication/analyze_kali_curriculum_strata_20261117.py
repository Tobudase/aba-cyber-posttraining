"""Planned secondary tool/schema and native-vs-fixed analysis, no selection."""
import json
import random
from collections import defaultdict,Counter
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import OUT, label_group, save

STAGE=OUT/'paired-sft'


def compare(new, base, groups):
    a={(r['sampling_seed'],r['id']):r for r in new}
    b={(r['sampling_seed'],r['id']):r for r in base}
    assert set(a)==set(b) and len(a)==len(new)==len(base)
    by_id=defaultdict(list)
    for key in a:by_id[key[1]].append(int(a[key]['correct'])-int(b[key]['correct']))
    deltas={id:sum(v)/len(v) for id,v in by_id.items()}
    gg=defaultdict(list)
    for id,d in deltas.items():gg[groups[id]].append(d)
    keys=sorted(gg);sums={g:sum(v) for g,v in gg.items()};counts={g:len(v) for g,v in gg.items()}
    rng=random.Random(20261117);draws=[]
    for _ in range(5000):
        sampled=[rng.choice(keys) for _ in keys]
        draws.append(sum(sums[g] for g in sampled)/sum(counts[g] for g in sampled))
    draws.sort()
    return {'unique_tasks':len(deltas),'groups':len(keys),'inference_samples':len(a),
            'mean_correct_count_difference':sum(deltas.values()),
            'percentage_point_difference':100*sum(deltas.values())/len(deltas),
            'wins':sum(a[k]['correct'] and not b[k]['correct'] for k in a),
            'losses':sum(b[k]['correct'] and not a[k]['correct'] for k in a),
            'descriptive_group_bootstrap_interval_pp':[100*draws[125],100*draws[4874]],
            'limit':'Shared-source task-composition bootstrap; one training seed, not independent training replication.'}


def stratify(rows, tools, groups, main_tools, all_train_tools):
    task=defaultdict(list)
    for r in rows:task[r['id']].append(r)
    means={id:sum(r['correct'] for r in rr)/len(rr) for id,rr in task.items()}
    def macro(mapping):
        by_group=defaultdict(list)
        for id,value in means.items():by_group[mapping[id]].append(value)
        return 100*sum(sum(v)/len(v) for v in by_group.values())/len(by_group)
    seen={}
    categories={'main_training_tool':lambda t:t in main_tools,
                'replay_only_training_tool':lambda t:t in all_train_tools-main_tools,
                'tool_unseen_in_current_training':lambda t:t not in all_train_tools}
    for name,predicate in categories.items():
        ids=[id for id in means if predicate(tools[id])]
        seen[name]={'unique_tasks':len(ids),'mean_reference_correctness_pct':100*sum(means[id] for id in ids)/len(ids) if ids else None}
    return {'unique_tasks':len(means),'unique_tools':len({tools[id] for id in means}),
            'unique_schema_groups':len({groups[id] for id in means}),
            'strict_micro_pct':100*sum(means.values())/len(means),
            'strict_tool_macro_pct':macro(tools),'strict_schema_macro_pct':macro(groups),'tool_coverage_strata':seen}


def stable_retention(new,base):
    a={(r['sampling_seed'],r['id']):r for r in new};b={(r['sampling_seed'],r['id']):r for r in base}
    assert set(a)==set(b) and len(a)==len(new)==len(base)
    ids={id for seed,id in b}
    assert all(sum(key==id for seed,key in b)==3 for id in ids),'Stable2/3 requires exactly three paired inference seeds'
    stable_base={id for id in ids if sum(r['correct'] for (seed,key),r in b.items() if key==id)>=2}
    stable_new={id for id in ids if sum(r['correct'] for (seed,key),r in a.items() if key==id)>=2}
    losses=Counter()
    for key,r in a.items():
        if b[key]['correct'] and not r['correct']:
            category='UNRESOLVED_EQUIVALENCE_NOT_CERTIFIED_FAILURE' if r['equivalence_status'].startswith('UNKNOWN') else 'TRUNCATED' if r['truncated'] else 'INVALID_OUTPUT' if not r['valid'] else 'REFERENCE_DIFFERENCE_NOT_EXECUTION_VERIFIED'
            losses[category]+=1
    kept=len(stable_base&stable_new)
    return {'base_stable_reference_tasks':len(stable_base),'candidate_stable_reference_tasks':len(stable_new),
            'stable_base_tasks_retained':kept,'stable_reference_retention_rate':kept/len(stable_base) if stable_base else None,
            'stable_base_tasks_lost':len(stable_base-stable_new),'new_stable_reference_tasks':len(stable_new-stable_base),
            'lost_reference_responses_by_evidence_type':dict(losses),
            'does_not_override_frozen_per_seed_guard':True,
            'limit':'At least2/3 inference successes is a diagnostic stable-reference subset, not a semantic certificate or training replication.'}


def main():
    pair=json.loads((STAGE/'runs/pair/score-private.json').read_text())
    final=json.loads((STAGE/'final-audit-private.json').read_text())['aggregate']
    assert final['status']=='FULL_INTERNAL_STUDY_AUDITED'
    admission=json.loads((OUT/'admission-private.json').read_text())['rows']
    main_tools={r['tool'] for r in admission if r['role']=='independent_teacher_A'};all_tools={r['tool'] for r in admission}
    refs=json.loads((STAGE/'evaluation-references-private.json').read_text())
    tools={id:r['tool_name'] for id,r in refs.items()};groups={id:label_group(r) for id,r in refs.items()}
    details=dict(pair['details'])
    for cid in ['A1','A2']:details[cid]=json.loads((STAGE/'runs'/cid/'score-private.json').read_text())['details']
    strata={};diagnostic_contrasts={};stable={}
    for cid,state in details.items():
        strata[cid]={mode:{panel:stratify([r for r in state['details'] if r['mode']==mode and r['panel']==panel],tools,groups,main_tools,all_tools)
                           for panel in ['development24','old64']} for mode in ['thinking','nonthinking']}
        stable[cid]={mode:stable_retention([r for r in state['details'] if r['mode']==mode and r['panel']=='old64'],
                                          [r for r in details['E0']['details'] if r['mode']==mode and r['panel']=='old64'])
                     for mode in ['thinking','nonthinking']}
    for mode in ['thinking','nonthinking']:
        diagnostic_contrasts[mode]={panel:compare([r for r in details['reasoning']['details'] if r['mode']==mode and r['panel']==panel],
                                               [r for r in details['answer_only']['details'] if r['mode']==mode and r['panel']==panel],groups)
                                    for panel in ['development24','old64']}
    conf=json.loads((STAGE/'confirmation/analysis-private.json').read_text())
    conf_groups=json.loads((STAGE/'confirmation/groups-private.json').read_text())
    conf_refs=json.loads((STAGE/'confirmation/references-private.json').read_text());conf_tools={id:r['tool_name'] for id,r in conf_refs.items()}
    converted={key:[dict(r,sampling_seed=r['seed']) for r in rr] for key,rr in conf['details'].items()}
    fixed=max([cid for cid,r in pair['results'].items() if r['eligible']],key=lambda cid:pair['results'][cid]['score'])
    selection=json.loads((STAGE/'native-selection-private.json').read_text())
    def label(cid):return 'E0' if cid=='E0' else 'fixed_'+cid if cid in ['answer_only','reasoning'] else 'native_selected'
    def resolved(key):return conf['aliases'].get(key,key)
    retained=label(selection['candidate_id']);fixed_label=label(fixed)
    comparisons={name:{mode:compare([r for r in converted[resolved(new)] if r['mode']==mode],
                                     [r for r in converted[resolved(base)] if r['mode']==mode],conf_groups)
                       for mode in ['thinking','nonthinking']}
                 for name,new,base in [('native_selected_minus_fixed_winner','native_selected',fixed_label),
                                       ('retained_minus_fixed_winner',retained,fixed_label),
                                       ('retained_minus_E0',retained,'E0')]}
    conf_strata={key:{mode:stratify([r for r in rr if r['mode']==mode],conf_tools,conf_groups,main_tools,all_tools)
                     for mode in ['thinking','nonthinking']} for key,rr in converted.items()}
    result={'status':'SECONDARY_DESCRIPTIVE_ANALYSIS_NO_SELECTION_CHANGE','fixed_winner_before_confirmation':fixed,
            'retained_before_confirmation':selection['candidate_id'],'selection_changed':False,
            'internal_strata':strata,'stable_old_reference_retention':stable,'R_minus_A_exposed_diagnostics':diagnostic_contrasts,
            'confirmation_native_vs_fixed_and_retained':comparisons,'confirmation_strata':conf_strata,
            'primary_R_minus_A_confirmation_unchanged':True,'official_TEST_queries':0}
    save(STAGE/'secondary-analysis-private.json',result)
    print(json.dumps({'status':result['status'],'fixed_winner':fixed,'retained':selection['candidate_id']}))
    return result


if __name__=='__main__':main()
