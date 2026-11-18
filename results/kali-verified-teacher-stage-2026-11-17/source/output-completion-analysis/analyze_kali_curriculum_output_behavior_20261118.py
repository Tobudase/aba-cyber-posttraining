"""Descriptive output-completion audit; no labels, accuracy or model selection."""
import argparse,json,statistics
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save,sha
from kali_reference_score_v2_20261117 import output_command

STAGE=OUT/'paired-sft'


def summarize(rows):
    truncated=[r for r in rows if r['finish_reason']=='length']
    one_tag=lambda r:output_command(r['content'],True) is not None
    return {'responses':len(rows),'generated_tokens':sum(r['generated_tokens'] for r in rows),
        'mean_generated_tokens':statistics.mean(r['generated_tokens'] for r in rows),
        'median_generated_tokens':statistics.median(r['generated_tokens'] for r in rows),
        'truncated':len(truncated),
        'truncated_without_think_closure':sum(r['mode']=='thinking' and '</think>' not in r['response'] for r in truncated),
        'truncated_with_one_nonempty_closed_output_tag':sum(one_tag(r) for r in truncated),
        'truncated_without_one_nonempty_closed_output_tag':sum(not one_tag(r) for r in truncated),
        'stopped_without_one_nonempty_closed_output_tag':sum(r['finish_reason']=='stop' and not one_tag(r) for r in rows),
        'one_closed_output_tag_is_not_a_syntax_or_correctness_certificate':True}


def main(require_complete=True):
    files={'E0':STAGE/'runs/pair/base-predictions.json',
        'answer_only':STAGE/'runs/pair/answer_only-predictions.json',
        'reasoning':STAGE/'runs/pair/reasoning-predictions.json',
        'A1':STAGE/'runs/A1/reasoning-predictions.json','A2':STAGE/'runs/A2/reasoning-predictions.json'}
    states={};hashes={}
    for cid,path in files.items():
        if not path.exists():
            assert not require_complete,'Missing completed endpoint '+cid
            continue
        data=json.loads(path.read_text());assert data['status']=='COMPLETE'
        rows=data['predictions'];assert len(rows)==len({(r['id'],r['sampling_seed'],r['mode']) for r in rows})==624
        hashes[cid]=sha(path)
        states[cid]={'all':summarize(rows),'modes':{mode:{
            'all':summarize([r for r in rows if r['mode']==mode]),
            'panels':{panel:summarize([r for r in rows if r['mode']==mode and r['panel']==panel])
                for panel in ['development24','old64','trainfit']}}
            for mode in ['thinking','nonthinking']}}
    result={'status':'ALL_FIVE_ENDPOINT_OUTPUT_BEHAVIOR_DESCRIBED' if len(states)==5 else 'PRELIMINARY_COMPLETED_ENDPOINTS_ONLY',
        'states':states,'prediction_source_sha256':hashes,'analysis_source_sha256':sha(__file__),
        'output_parser_source_sha256':sha(ROOT/'scripts/kali_reference_score_v2_20261117.py'),
        'references_or_correctness_labels_loaded':False,'new_model_calls':0,'selection_changed':False,
        'limit':'Descriptive completion/format behavior only. A closed output tag does not establish command syntax or task correctness; frozen length rejection and scores are unchanged.',
        'official_TEST_queries':0,'confirmation_queries_added':0}
    save(STAGE/('output-behavior-private.json' if len(states)==5 else 'output-behavior-preliminary-private.json'),result)
    print(json.dumps({'status':result['status'],'states':{cid:record['all'] for cid,record in states.items()}},indent=2))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--completed-only',action='store_true');args=parser.parse_args()
    main(require_complete=not args.completed_only)
