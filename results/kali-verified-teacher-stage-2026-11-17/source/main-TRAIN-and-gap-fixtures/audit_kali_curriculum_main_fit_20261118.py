"""Audit actual main TRAIN/gap CPU execution and prediction-command mapping."""
import ast,contextlib,hashlib,io,json,tempfile
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,sha,save
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_framed_artifacts_20261117 import parse
from kali_curriculum_acceptance_20261117 import command
from check_kali_curriculum_posttrain_fit_20261117 import analyze

STAGE=OUT/'paired-sft';DEST=STAGE/'trainfit/all'
def read(path):return json.loads(path.read_text())
def function_ast(source,name):
    return ast.dump(next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)

def audit():
    freeze=read(DEST/'freeze-private.json');job='miw113-kali-cur-fit-all-1117'
    host=read(JOBS/job/'host.json');assert host['status']=='SUCCEEDED' and host['resources_cleaned'] and not host['gpu']
    assert not any(k.startswith('nvidia.com/') for k in host['resources'])
    objects=read(JOBS/job/'objects.json');cm=next(o for o in objects if o['kind']=='ConfigMap')
    oracle=(DEST/'original-oracle-private.py').read_text();worker=cm['data']['worker.py']
    assert sha(DEST/'original-oracle-private.py')==freeze['original_oracle_worker_sha256']
    old="print('VERIFIED_CURRICULUM_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps(artifact).encode())).decode(),flush=True)"
    new="import sys;sys.path.insert(0,'/input');from kali_framed_artifacts_20261117 import emit;emit(artifact,'CURRICULUM_FIT_ARTIFACT')"
    assert oracle.count(old)==1 and worker==oracle.replace(old,new)==(DEST/'actually-submitted-worker-private.py').read_text()
    assert hashlib.sha256(worker.encode()).hexdigest()==freeze['transport_only_worker_sha256']
    for name,digest in read(DEST/'source-freeze-private.json').items():assert sha(DEST/'loaded-source-private'/name)==digest
    assert sha(ROOT/'scripts/kali_curriculum_acceptance_20261117.py')==sha(DEST/'loaded-source-private/kali_curriculum_acceptance_20261117.py')
    assert cm['data']['kali_framed_artifacts_20261117.py']==(DEST/'loaded-source-private/kali_framed_artifacts_20261117.py').read_text()
    executed=(DEST/'loaded-source-private/check_kali_curriculum_posttrain_fit_20261117.py').read_text()
    current=(ROOT/'scripts/check_kali_curriculum_posttrain_fit_20261117.py').read_text()
    assert function_ast(executed,'analyze')==function_ast(current,'analyze'),'No post-hoc result redefinition'
    assert hashlib.sha256(cm['data']['candidates.json'].encode()).hexdigest()==freeze['candidate_sha256']
    assert hashlib.sha256(cm['data']['commands.json'].encode()).hexdigest()==freeze['commands_sha256']
    assert hashlib.sha256(cm['data']['galleta.c'].encode()).hexdigest()==cm['data']['galleta.sha256']==sha(ROOT/'data/benchkit/kali-independent-teacher-2026-11-17/source-evidence/galleta.c')
    candidates=json.loads(cm['data']['candidates.json']);supported={r['id'] for r in candidates}
    admission={r['id']:r for r in read(OUT/'admission-private.json')['rows']}
    inputs=read(STAGE/'evaluation-inputs-private.json');fit_ids={r['id'] for r in inputs if r['panel']=='trainfit'}
    gap_ids={r['id'] for r in admission.values() if r.get('strong_gap')}
    assert len(fit_ids)==16 and len(gap_ids)==3 and freeze['known_train_gap_unique_tasks']==3
    expected_candidates=[r for r in read(OUT/'candidates-r2-private.json') if r['id'] in fit_ids|gap_ids]
    assert candidates==expected_candidates and supported<=(fit_ids|gap_ids)
    assert all(admission[id]['role']=='independent_teacher_A' for id in supported)
    paths={'E0':STAGE/'runs/pair/base-predictions.json','answer_only':STAGE/'runs/pair/answer_only-predictions.json',
        'reasoning':STAGE/'runs/pair/reasoning-predictions.json',**{c:STAGE/'runs'/c/'reasoning-predictions.json' for c in ['A1','A2']}}
    endpoint_freeze=read(STAGE/'confirmation/selection-freeze-private.json')
    paths.update({'known_gap_'+r['label']:STAGE/'confirmation/runs'/(r['label']+'-gap-predictions.json') for r in endpoint_freeze['states']})
    assert set(paths)==set(freeze['states'])==set(freeze['source_predictions_sha256'])
    predictions={};expected_keys=set()
    for state,path in paths.items():
        assert sha(path)==freeze['source_predictions_sha256'][state]
        pred=read(path);assert pred['status']=='COMPLETE'
        panel='known_training_gap3' if state.startswith('known_gap_') else 'trainfit'
        ids=gap_ids if state.startswith('known_gap_') else fit_ids
        selected=[r for r in pred['predictions'] if r['panel']==panel]
        expected={(seed,mode,id) for seed in [3407,4407,5407] for mode in ['thinking','nonthinking'] for id in ids}
        assert {(r['sampling_seed'],r['mode'],r['id']) for r in selected}==expected and len(selected)==len(expected)
        for row in selected:
            key=(state,row['mode'],row['sampling_seed'],row['id']);assert key not in predictions
            predictions[key]=row;expected_keys.add(key)
    entries=freeze['entries'];keys=[(r['state'],r['mode'],r['seed'],r['id']) for r in entries]
    assert len(keys)==len(set(keys)) and set(keys)==expected_keys
    commands={}
    for entry,key in zip(entries,keys):
        state,mode,seed,id=key;row=predictions[key];role=state+'__'+mode+'__'+str(seed)
        assert entry['role']==role
        if id not in supported:assert entry['status']=='UNSUPPORTED_PUBLISHER_REPLAY_NOT_EXECUTED';continue
        cmd=command(row);assert entry['status']==('READY' if cmd else 'NO_VALID_COMPLETED_OUTPUT')
        if cmd:commands.setdefault(id,{})[role]=cmd
    assert commands==json.loads(cm['data']['commands.json']),'Execute actual unchanged model outputs, never idealized reference answers'
    artifact=parse((JOBS/job/'worker.log').read_text(),'CURRICULUM_FIT_ARTIFACT');assert artifact is not None
    assert artifact==read(DEST/'execution-private.json')
    with tempfile.TemporaryDirectory(prefix='kali-main-fit-audit-') as tmp,contextlib.redirect_stdout(io.StringIO()):
        analyze(Path(tmp),freeze,artifact);recomputed=read(Path(tmp)/'analysis-private.json')
    saved=read(DEST/'analysis-private.json');assert saved==recomputed
    assert saved['GPU']==saved['DEV_or_confirmation_or_TEST_commands']==0 and saved['false_passed_negative_controls']==0
    assert saved['paired_fixture_controls_verified'] and saved['unique_fixture_tasks']==len(supported)
    result={'status':'ACTUAL_MAIN_TRAIN_AND_GAP_CPU_EXECUTION_AND_PREDICTION_MAPPING_AUDITED',
        'actual_CPU_jobs_succeeded':1,'unique_fixture_tasks':len(supported),
        'unique_main_TRAIN_fit_tasks':len(supported&fit_ids),'known_TRAIN_gap_tasks':len(supported&gap_ids),
        'overlap_main_fit_and_gap_tasks':len(supported&fit_ids&gap_ids),
        'reference_positive_checks':saved['reference_positive_checks'],'negative_controls':saved['negative_controls'],
        'false_passed_negative_controls':0,'GPU':0,'new_model_calls':0,'protected_DEV_confirmation_TEST_commands':0,
        'selection_changed':False,'task_postconditions_unchanged':True,'raw_commands_traceable_to_exact_frozen_predictions':True,
        'complete_analysis_recomputed_identically':True,'audit_source_sha256':sha(__file__),
        'all_negative_controls_explicit_FAIL':True,
        'actual_analysis_source_sha256':sha(DEST/'loaded-source-private/check_kali_curriculum_posttrain_fit_20261117.py'),
        'original_oracle_sha256':freeze['original_oracle_worker_sha256'],'submitted_oracle_sha256':freeze['transport_only_worker_sha256'],
        'scope':'Already-seen TRAIN10 and known TRAIN-gap3 only; no held-out or official benchmark accuracy correction.'}
    save(DEST/'final-audit-private.json',result);return result

if __name__=='__main__':print(json.dumps(audit(),indent=2))
