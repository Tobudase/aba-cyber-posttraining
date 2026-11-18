"""Recompute six-task TRAIN replay diagnostics from real CPU Job artifacts."""
import ast,contextlib,hashlib,io,json,tempfile
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,sha,save
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_framed_artifacts_20261117 import parse
from check_kali_curriculum_replay_fit_20261118 import analyze,protected_oracle_source,malformed_quotation
from kali_curriculum_acceptance_20261117 import command

STAGE=OUT/'paired-sft';DEST=STAGE/'replay-fit'

def function_ast(source,name):
    return ast.dump(next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)


def audit():
    combined=json.loads((DEST/'combined-analysis-private.json').read_text())
    assert combined['status']=='ALL_FIVE_ENDPOINT_PUBLISHER_TRAIN_REPLAY_FIT_VERIFIED'
    states={};pred_hashes={};positives=negatives=0
    paths={'E0':STAGE/'runs/pair/base-predictions.json','answer_only':STAGE/'runs/pair/answer_only-predictions.json',
        'reasoning':STAGE/'runs/pair/reasoning-predictions.json',**{c:STAGE/'runs'/c/'reasoning-predictions.json' for c in ['A1','A2']}}
    replay=[r for r in json.loads((OUT/'admission-private.json').read_text())['rows'] if r['role']=='publisher_train_replay']
    assert len(replay)==6
    for tag,job in [('known4','miw113-kali-cur-replay-known4-r2-1118'),('a2','miw113-kali-cur-replay-a2-1118')]:
        directory=DEST/tag;freeze=json.loads((directory/'freeze-private.json').read_text())
        host=json.loads((JOBS/job/'host.json').read_text());assert host['status']=='SUCCEEDED' and host['resources_cleaned'] and not host['gpu']
        assert not any(k.startswith('nvidia.com/') for k in host['resources'])
        objects=json.loads((JOBS/job/'objects.json').read_text());cm=next(o for o in objects if o['kind']=='ConfigMap')
        worker=cm['data']['worker.py'];base=(directory/'actual-old-oracle-private.py').read_text()
        assert hashlib.sha256(base.encode()).hexdigest()==freeze['actual_old_oracle_sha256']=='1574d2232c52d8000d1bdf992e970535cfb46c967e9b92fafbeb105be505a6d3'
        assert worker==protected_oracle_source(base)==(directory/'actually-submitted-worker-private.py').read_text()
        assert hashlib.sha256(worker.encode()).hexdigest()==freeze['transport_and_parse_safety_worker_sha256']
        assert hashlib.sha256(cm['data']['references.json'].encode()).hexdigest()==freeze['references_sha256']
        assert hashlib.sha256(cm['data']['commands.json'].encode()).hexdigest()==freeze['commands_sha256']
        references=json.loads(cm['data']['references.json'])
        assert {r['id'] for r in references}=={r['parent_id'] for r in replay}
        for row in replay:
            ref=next(r for r in references if r['id']==row['parent_id'])
            assert ref['split']=='train' and ref['training_eligible'] and not ref['official_test']
            assert ref['input_sha256']==row['source_sha256'] and ref['native_label']['query']==row['query']
        rebuilt={};expected_entries=[]
        for cid in freeze['states']:
            pred=json.loads(paths[cid].read_text());assert pred['status']=='COMPLETE'
            for row in replay:
                samples=[r for r in pred['predictions'] if r['id']==row['id']]
                assert len(samples)==6 and all(r['panel']=='trainfit' for r in samples)
                assert {(r['sampling_seed'],r['mode']) for r in samples}=={(seed,mode) for seed in [3407,4407,5407] for mode in ['thinking','nonthinking']}
                for r in samples:
                    role='model_'+cid+'__'+r['mode']+'__'+str(r['sampling_seed']);cmd=command(r)
                    expected_entries.append({'id':row['parent_id'],'state':cid,'mode':r['mode'],'seed':r['sampling_seed'],
                        'role':role,'expected_tool':row['tool'],'status':'READY' if cmd else 'NO_VALID_COMPLETED_OUTPUT',
                        'malformed_shell_quotation':bool(cmd and malformed_quotation(cmd))})
                    if cmd:rebuilt.setdefault(row['parent_id'],{})[role]=cmd
        assert expected_entries==freeze['entries'] and rebuilt==json.loads(cm['data']['commands.json'])
        for name,digest in json.loads((directory/'source-freeze-private.json').read_text()).items():
            assert sha(directory/'loaded-source-private'/name)==digest
        executed=(directory/'loaded-source-private/check_kali_curriculum_replay_fit_20261118.py').read_text()
        current=(ROOT/'scripts/check_kali_curriculum_replay_fit_20261118.py').read_text()
        for name in ['analyze','summarize_cases','protected_oracle_source','malformed_quotation']:
            assert function_ast(executed,name)==function_ast(current,name),'No post-hoc diagnostic redefinition'
        artifact=parse((JOBS/job/'worker.log').read_text(),'CURRICULUM_REPLAY_FIT_ARTIFACT')
        assert artifact is not None and artifact==json.loads((directory/'execution-private.json').read_text())
        with tempfile.TemporaryDirectory(prefix='kali-replay-audit-') as tmp,contextlib.redirect_stdout(io.StringIO()):
            analyze(Path(tmp),freeze,artifact)
            recomputed=json.loads((Path(tmp)/'analysis-private.json').read_text())
        saved=json.loads((directory/'analysis-private.json').read_text());assert recomputed==saved
        assert not set(states)&set(saved['summary']);states.update(saved['summary'])
        pred_hashes.update(saved['source_prediction_sha256']);positives+=saved['reference_positive_checks'];negatives+=saved['negative_controls']
        assert sha(directory/'analysis-private.json')==combined['batch_analysis_sha256'][tag]
    assert states==combined['summary'] and set(states)==set(paths)
    assert pred_hashes==combined['source_prediction_sha256']=={cid:sha(path) for cid,path in paths.items()}
    assert positives==combined['reference_positive_checks']==24 and negatives==combined['negative_controls']==32
    failed=json.loads((JOBS/'miw113-kali-cur-replay-known4-1118/host.json').read_text())
    assert failed['status']=='FAILED' and failed['resources_cleaned'] and not failed['gpu']
    retry=json.loads((DEST/'known4-oracle-retry-before-results-private.json').read_text())
    freeze=json.loads((DEST/'known4/freeze-private.json').read_text())
    assert failed['uid']==retry['failed_job_uid']
    assert freeze['references_sha256']==retry['original_references_sha256'] and freeze['commands_sha256']==retry['original_commands_sha256']
    assert combined['GPU']==combined['model_calls']==combined['protected_DEV_confirmation_TEST_commands']==0
    assert not combined['selection_changed'] and combined['false_passed_negative_controls']==0
    result={'status':'ACTUAL_CPU_JOBS_AND_ALL_FIVE_REPLAY_FIT_RESULTS_AUDITED',
        'summary':combined['summary'],'unique_seen_TRAIN_tasks':6,'samples_per_mode_per_state':18,
        'reference_positive_checks_across_two_batches':24,'negative_controls_across_two_batches':32,
        'false_passed_negative_controls':0,'old_task_postconditions_unchanged':True,
        'actual_cpu_jobs_succeeded':2,'actual_cpu_job_failed_retained':1,'GPU':0,'new_model_calls':0,
        'protected_DEV_confirmation_TEST_commands':0,'selection_changed':False,
        'same_exact_commands_retried_after_quotation_safety_fix':True,'semantic_unknown_not_counted_as_pass':True,
        'malformed_quotation_inputs_in_known4':retry['malformed_shell_quotation_inputs'],
        'audit_source_sha256':sha(__file__),'combined_source_sha256':sha(DEST/'combined-analysis-private.json'),
        'scope':'Already-seen TRAIN replay fit, not independent transfer, held-out evaluation or accuracy correction.'}
    save(DEST/'final-audit-private.json',result);return result

if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
