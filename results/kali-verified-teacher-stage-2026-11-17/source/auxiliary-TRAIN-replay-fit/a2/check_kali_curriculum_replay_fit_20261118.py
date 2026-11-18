"""Auxiliary execution of six already-seen publisher TRAIN replay tasks.

Reuses the ACTUAL earlier submitted reference oracle, including its LLVM-dev
fix. Changes framing and malformed-quotation handling only; task checks unchanged.
"""
import argparse,datetime,hashlib,json,shlex,time
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save,sha
from kali_execution_jobs_20261114 import OUT as JOBS,submit,poll,cleanup
from kali_curriculum_acceptance_20261117 import command
from kali_framed_artifacts_20261117 import parse
from kali_cpu_node_pool_20261118 import ordinary_cpu_nodes

STAGE=OUT/'paired-sft';DEST=STAGE/'replay-fit'


def protected_oracle_source(oracle):
    old="print('INDEPENDENT_ACCEPTANCE_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps(report).encode())).decode(),flush=True)"
    assert oracle.count(old)==1 and oracle.count(';argv=shlex.split(command)')==1
    worker=oracle.replace(';argv=shlex.split(command)',
        '\n        try:argv=shlex.split(command)\n        except ValueError:return None')
    return worker.replace(old,"import sys;sys.path.insert(0,'/input');from kali_framed_artifacts_20261117 import emit;emit(report,'CURRICULUM_REPLAY_FIT_ARTIFACT')")


def malformed_quotation(command_text):
    try:shlex.split(command_text.replace("$'\\n'",shlex.quote('\n')))
    except ValueError:return True
    return False


def summarize_cases(cases,states):
    summary={}
    for state in states:
        summary[state]={}
        for mode in ['thinking','nonthinking']:
            rr=[r for r in cases if r['state']==state and r['mode']==mode]
            assert len(rr)==18 and len({r['id'] for r in rr})==6
            summary[state][mode]={'unique_training_tasks':6,'inference_samples':18,
                'functional_pass':sum(r['status']=='PASS_BOTH_FIXTURES' for r in rr),
                'functional_fail':sum(r['status']=='FAIL_SCOPED_FIXTURE' for r in rr),
                'unknown':sum(r['status']=='UNKNOWN_SCOPED_SYNTAX_OR_TOOL' for r in rr),
                'invalid_output':sum(r['status']=='NO_VALID_COMPLETED_OUTPUT' for r in rr),
                'unbalanced_shell_quotation':sum(r.get('malformed_shell_quotation',False) for r in rr),
                'per_seed':{str(seed):{'n':6,'functional_pass':sum(r['status']=='PASS_BOTH_FIXTURES' for r in rr if r['seed']==seed)} for seed in [3407,4407,5407]}}
            assert sum(summary[state][mode][key] for key in ['functional_pass','functional_fail','unknown','invalid_output'])==18
    return summary


def main(states,tag,attempt=1):
    paths={'E0':STAGE/'runs/pair/base-predictions.json','answer_only':STAGE/'runs/pair/answer_only-predictions.json',
        'reasoning':STAGE/'runs/pair/reasoning-predictions.json',**{cid:STAGE/'runs'/cid/'reasoning-predictions.json' for cid in ['A1','A2']}}
    assert states and len(set(states))==len(states) and set(states)<=set(paths)
    dest=DEST/tag;assert not dest.exists();dest.mkdir(parents=True,mode=0o700)
    admitted=json.loads((OUT/'admission-private.json').read_text())['rows']
    replay=[r for r in admitted if r['role']=='publisher_train_replay'];assert len(replay)==6
    refs_source=ROOT/'data/benchkit/kali-independent-teacher-2026-11-17/screen-references-private.json'
    allrefs={r['id']:r for r in json.loads(refs_source.read_text())};refs=[allrefs[r['parent_id']] for r in replay]
    for row,ref in zip(replay,refs):
        assert ref['split']=='train' and ref['training_eligible'] and not ref['official_test']
        assert ref['input_sha256']==row['source_sha256'] and ref['native_label']['query']==row['query']
    current=json.loads((STAGE/'evaluation-inputs-private.json').read_text())
    assert {r['id'] for r in replay}=={r['id'] for r in current if r['panel']=='trainfit' and r['id'].startswith('publisher-replay-')}
    original_objects=JOBS/'miw113-kali-independent-acceptance-r3-1117/objects.json'
    cm=next(o for o in json.loads(original_objects.read_text()) if o['kind']=='ConfigMap')
    oracle=cm['data']['worker.py'];assert hashlib.sha256(oracle.encode()).hexdigest()=='1574d2232c52d8000d1bdf992e970535cfb46c967e9b92fafbeb105be505a6d3'
    assert "'llvm-14-dev'" in oracle
    old="print('INDEPENDENT_ACCEPTANCE_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps(report).encode())).decode(),flush=True)"
    assert oracle.count(old)==1
    worker=protected_oracle_source(oracle)
    commands={};entries=[];pred_hashes={}
    for state in states:
        pred=json.loads(paths[state].read_text());assert pred['status']=='COMPLETE' and len(pred['predictions'])==624
        pred_hashes[state]=sha(paths[state])
        for row in replay:
            samples=[r for r in pred['predictions'] if r['id']==row['id']]
            assert len(samples)==6 and all(r['panel']=='trainfit' for r in samples)
            assert {(r['sampling_seed'],r['mode']) for r in samples}=={(seed,mode) for seed in [3407,4407,5407] for mode in ['thinking','nonthinking']}
            for r in samples:
                role='model_'+state+'__'+r['mode']+'__'+str(r['sampling_seed']);cmd=command(r)
                entries.append({'id':row['parent_id'],'state':state,'mode':r['mode'],'seed':r['sampling_seed'],'role':role,
                    'expected_tool':row['tool'],'status':'READY' if cmd else 'NO_VALID_COMPLETED_OUTPUT','malformed_shell_quotation':bool(cmd and malformed_quotation(cmd))})
                if cmd:commands.setdefault(row['parent_id'],{})[role]=cmd
    ref_text=json.dumps(refs,indent=2)+'\n';command_text=json.dumps(commands,indent=2)+'\n'
    files={'worker.py':worker,'references.json':ref_text,'commands.json':command_text,
        'galleta.c':cm['data']['galleta.c'],'galleta.sha256':cm['data']['galleta.sha256'],
        'kali_framed_artifacts_20261117.py':(ROOT/'scripts/kali_framed_artifacts_20261117.py').read_text()}
    assert hashlib.sha256(files['galleta.c'].encode()).hexdigest()==files['galleta.sha256'].strip()
    freeze={'status':'AUXILIARY_ALREADY_SEEN_TRAIN_REPLAY_FIT_ONLY','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'states':states,'entries':entries,'source_prediction_sha256':pred_hashes,'unique_training_tasks':6,
        'references_sha256':hashlib.sha256(ref_text.encode()).hexdigest(),'commands_sha256':hashlib.sha256(command_text.encode()).hexdigest(),
        'actual_old_oracle_sha256':hashlib.sha256(oracle.encode()).hexdigest(),'transport_and_parse_safety_worker_sha256':hashlib.sha256(worker.encode()).hexdigest(),'task_postconditions_unchanged':True,'attempt':attempt,
        'old_submitted_objects_sha256':sha(original_objects),'GPU':0,'model_calls':0,'selection_changed':False,
        'protected_DEV_confirmation_TEST_commands':0}
    if attempt==2:
        assert tag=='known4'
        proof=json.loads((DEST/'known4-oracle-retry-before-results-private.json').read_text())
        assert freeze['references_sha256']==proof['original_references_sha256'] and freeze['commands_sha256']==proof['original_commands_sha256']
        prior=json.loads((JOBS/proof['failed_job']/'host.json').read_text())
        assert prior['status']=='FAILED' and prior['resources_cleaned'] and prior['uid']==proof['failed_job_uid']
        freeze['prior_failed_CPU_attempt_kept']=True
    else:assert attempt==1
    save(dest/'freeze-private.json',freeze);(dest/'actual-old-oracle-private.py').write_text(oracle)
    (dest/'actually-submitted-worker-private.py').write_text(worker)
    loaded=dest/'loaded-source-private';loaded.mkdir()
    names=['check_kali_curriculum_replay_fit_20261118.py','kali_cpu_node_pool_20261118.py','kali_framed_artifacts_20261117.py']
    for name in names:(loaded/name).write_bytes((ROOT/'scripts'/name).read_bytes())
    save(dest/'source-freeze-private.json',{name:sha(loaded/name) for name in names})
    job='miw113-kali-cur-replay-'+tag+('-r2' if attempt==2 else '')+'-1118'
    print(json.dumps(submit(job,files,{'cpu':'2','memory':'4Gi','ephemeral-storage':'8Gi'},runtime=2700,node_names=ordinary_cpu_nodes())),flush=True)
    until=time.monotonic()+4900;collected=None;previous=None
    while time.monotonic()<until:
        try:state=poll(job)
        except Exception as exc:print('TRANSIENT_REPLAY_FIT_POLL '+type(exc).__name__,flush=True);time.sleep(30);continue
        log=JOBS/job/'worker.log'
        if log.exists():
            artifact=parse(log.read_text(),'CURRICULUM_REPLAY_FIT_ARTIFACT')
            if artifact is not None:collected=artifact;save(dest/'execution-private.json',artifact)
        state.pop('log_tail',None);save(dest/'monitor-private.json',state)
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        if state['status'] in ['FAILED','SUCCEEDED']:
            if state['status']=='SUCCEEDED':assert collected is not None
            cleanup(job);assert state['status']=='SUCCEEDED','Preserve actual failed CPU attempt; never relabel success'
            analyze(dest,freeze,collected);combine_if_ready();return
        time.sleep(30)
    raise TimeoutError('Finite auxiliary TRAIN CPU execution exhausted; no auto-resubmission')


def analyze(dest,freeze,artifact):
    assert artifact['status']=='COMPLETE_PENDING_HOST_AUDIT'
    assert artifact['input_sha256']==freeze['references_sha256'] and artifact['commands_sha256']==freeze['commands_sha256']
    assert artifact['GPU']==artifact['model_calls']==artifact['target_binaries_executed']==0
    rows=artifact['results'];keys=[(r['id'],r['role'],r['variant']) for r in rows];assert len(keys)==len(set(keys))
    ids={r['id'] for r in freeze['entries']};assert len(ids)==6
    refs=[r for r in rows if r['role']=='reference'];assert {(r['id'],r['variant']) for r in refs}=={(id,v) for id in ids for v in [0,1]}
    assert all(r['task_pass'] is True for r in refs)
    negatives=artifact['negative_controls'];assert {(r['id'],r['variant']) for r in negatives}=={(id,v) for id in ids for v in [0,1]}
    assert len(negatives)>=12 and all(r['task_pass'] is False for r in negatives),'Negative controls must actually fail, not be UNKNOWN'
    indexed={}
    for r in rows:indexed.setdefault((r['id'],r['role']),[]).append(r)
    cases=[]
    for entry in freeze['entries']:
        case=dict(entry)
        if entry['status']=='READY':
            rr=indexed[(entry['id'],entry['role'])];assert len(rr)==2 and {r['variant'] for r in rr}=={0,1}
            wrong_tool=any(r.get('argv',[entry['expected_tool']])[0]!=entry['expected_tool'] for r in rr)
            case['status']='UNKNOWN_SCOPED_SYNTAX_OR_TOOL' if wrong_tool or any(r['status'].startswith('UNKNOWN') for r in rr) else 'PASS_BOTH_FIXTURES' if all(r['task_pass'] for r in rr) else 'FAIL_SCOPED_FIXTURE'
        cases.append(case)
    result={'status':'AUXILIARY_TRAIN_REPLAY_FIT_VERIFIED_NOT_SELECTION','summary':summarize_cases(cases,freeze['states']),
        'source_prediction_sha256':freeze['source_prediction_sha256'],'reference_positive_checks':len(refs),
        'negative_controls':len(negatives),'false_passed_negative_controls':0,'paired_fixture_controls_verified':True,
        'GPU':0,'model_calls':0,'protected_DEV_confirmation_TEST_commands':0,'selection_changed':False,
        'scope':'Six already-seen publisher TRAIN replay tasks, two benign fixtures. No transfer or benchmark accuracy claim.',
        'actual_old_oracle_sha256':freeze['actual_old_oracle_sha256'],'malformed_quote_handling_only_safety_fix':True,'task_postconditions_unchanged':True,'attempt':freeze['attempt'],'cases':cases}
    save(dest/'analysis-private.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','source_prediction_sha256']}),flush=True)


def combine_if_ready():
    paths=[DEST/tag/'analysis-private.json' for tag in ['known4','a2']]
    if not all(p.exists() for p in paths):return
    batches_=[json.loads(p.read_text()) for p in paths];states={};hashes={}
    for batch in batches_:
        assert batch['status']=='AUXILIARY_TRAIN_REPLAY_FIT_VERIFIED_NOT_SELECTION' and not batch['selection_changed']
        assert not set(states)&set(batch['summary']);states.update(batch['summary']);hashes.update(batch['source_prediction_sha256'])
    assert set(states)=={'E0','answer_only','reasoning','A1','A2'}
    save(DEST/'combined-analysis-private.json',{'status':'ALL_FIVE_ENDPOINT_PUBLISHER_TRAIN_REPLAY_FIT_VERIFIED',
        'summary':states,'source_prediction_sha256':hashes,'batch_analysis_sha256':{p.parent.name:sha(p) for p in paths},
        'unique_training_tasks':6,'inference_samples_per_state_and_mode':18,
        'reference_positive_checks':sum(b['reference_positive_checks'] for b in batches_),
        'negative_controls':sum(b['negative_controls'] for b in batches_),'false_passed_negative_controls':0,
        'GPU':0,'model_calls':0,'protected_DEV_confirmation_TEST_commands':0,'selection_changed':False,
        'actual_old_oracle_sha256':batches_[0]['actual_old_oracle_sha256'],
        'task_postconditions_unchanged':True,'malformed_quote_handling_only_safety_fix':True,
        'prior_failed_CPU_oracle_attempts':1,'retry_preserved_exact_original_commands':True,
        'scope':'Supplemental already-seen TRAIN replay fit; not a correction to frozen scores or a generalization test.'})
    print('ALL_FIVE_ENDPOINT_PUBLISHER_TRAIN_REPLAY_FIT_VERIFIED',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',choices=['known4','a2'],required=True)
    p.add_argument('--states',nargs='+',choices=['E0','answer_only','reasoning','A1','A2'],required=True)
    p.add_argument('--attempt',type=int,choices=[1,2],default=1)
    a=p.parse_args();assert (a.tag=='known4' and a.states==['E0','answer_only','reasoning','A1']) or (a.tag=='a2' and a.states==['A2'])
    main(a.states,a.tag,a.attempt)
