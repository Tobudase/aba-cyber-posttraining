"""One conditional infrastructure-only tail of the SAME frozen cohort.

Only after the original Job actually fails its unmodified deadline and is
cleaned. No new training, data, seeds, selection or confirmation score queries.
"""
import base64,datetime,gzip,hashlib,json,time
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save,sha
from kali_execution_jobs_20261114 import OUT as JOBS,k,submit,poll,cleanup,gpu_cache_conflicts
from kali_framed_artifacts_20261117 import parse
from kali_curriculum_prefix_resume_20261118 import validate_prefix

STAGE=OUT/'paired-sft';CONF=STAGE/'confirmation';OLD='miw113-kali-curriculum-confirm-1117'
NAME='miw113-kali-curriculum-confirm-tail-1117';TAIL=CONF/'tail';ACT=CONF/'deadline-tail-activation-private.json'
def read(path):return json.loads(path.read_text())

def prediction_manifest(directory):
    frozen=read(CONF/'selection-freeze-private.json');result={}
    for state in frozen['states']:
        for gap in [False,True]:
            filename=state['label']+('-gap-predictions.json' if gap else '-predictions.json');p=directory/filename
            if not p.exists():continue
            stage=STAGE/'gap-diagnostic' if gap else CONF;protocol=read(stage/'evaluation-protocol.json');rows=read(stage/'evaluation-inputs-private.json')
            data=read(p);n=validate_prefix(data,rows,protocol,state['pointer']['adapter_sha256'],minimum=1)
            assert n<=(18 if gap else 144)
            if data['status']=='COMPLETE':
                assert n==(18 if gap else 144) and data['inputs_sha256']==protocol['input_sha256'] and data['no_evaluation_gold_loaded']
            else:assert data['status']=='RUNNING' and n<(18 if gap else 144)
            result[filename]={'sha256':sha(p),'responses':n,'status':data['status']}
    assert result,'No preserved actual completed batch; no automatic full rerun'
    actual={p.name for p in directory.glob('*predictions.json')};assert actual==set(result)
    return result

def activate():
    assert not ACT.exists() and not TAIL.exists() and not(JOBS/NAME).exists()
    assert not(CONF/'analysis-private.json').exists(),'Never resume based on observed confirmation scores'
    planfile=STAGE/'confirmation-deadline-contingency-before-scoring-private.json';plan=read(planfile)
    assert plan['status']=='CONDITIONAL_CONFIRMATION_DEADLINE_CONTINUATION_BEFORE_ANY_CONFIRMATION_SCORING_NOT_ACTIVATED'
    assert not plan['confirmation_scoring_before_activation'] and plan['new_training_updates']==plan['new_training_candidates']==0
    assert sha(CONF/'selection-freeze-private.json')==plan['selection_freeze_sha256'] and sha(CONF/'launch-freeze-private.json')==plan['original_launch_sha256']
    host=read(JOBS/OLD/'host.json');assert host['uid']==plan['original_job_uid'] and host['status']=='FAILED' and host['resources_cleaned']
    logfile=JOBS/OLD/'worker.log';assert 'CONFIRM_FAILED TimeoutExpired' in logfile.read_text()
    frames=parse(logfile.read_text(),'CURRICULUM_CONFIRM_ARTIFACT');assert frames is not None
    original=CONF/'runs'
    for name,text in frames.items():assert Path(name).name==name and (original/name).read_text()==text
    receipt=read(original/'execution-receipt.json');assert receipt['status']=='FAILED' and receipt['training_updates']==0 and receipt['official_TEST_queries']==0
    assert receipt['all_endpoints_exact_reload_preflight_passed_before_queries'] and receipt['confirmation_inference_started']
    manifest=prediction_manifest(original)
    assert any(v['status']!='COMPLETE' for v in manifest.values()) or len(manifest)<8,'All files already complete: inspect CPU-only recovery instead of allocating another GPU'
    launch=read(CONF/'launch-freeze-private.json');objects=read(JOBS/OLD/'objects.json');cm=next(o for o in objects if o['kind']=='ConfigMap')
    raw=base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==launch['config']['bundle_sha256']==receipt['bundle_sha256']
    assert hashlib.sha256(cm['data']['worker.py'].encode()).hexdigest()==launch['config']['worker_sha256']==receipt['worker_sha256']
    assert receipt['selection_sha256']==launch['config']['selection_sha256']==read(CONF/'selection-freeze-private.json')['selection_sha256']
    from kali_curriculum_gpu_budget_20261117 import ledger
    budget=ledger(prospective_seconds=plan['tail_Job_seconds_max']+plan['extra_safety_reserve_seconds'])
    assert budget['stop_budget_gpu_seconds']==plan['effective_study_GPU_ceiling_seconds_unchanged']==93600
    archive=CONF/'original-deadline-failed-private';assert not archive.exists();archive.mkdir();original.rename(archive/'runs')
    save(ACT,{'status':'ACTUAL_ORIGINAL_CONFIRMATION_DEADLINE_FAILURE_SAME_COHORT_TAIL_ACTIVATED',
        'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operational_plan_sha256':sha(planfile),
        'failed_job':OLD,'failed_job_uid':host['uid'],'failed_host_sha256':sha(JOBS/OLD/'host.json'),
        'original_failed_execution_sha256':sha(archive/'runs/execution-receipt.json'),'source_prediction_files':manifest,
        'original_launch_sha256':sha(CONF/'launch-freeze-private.json'),'selection_freeze_sha256':sha(CONF/'selection-freeze-private.json'),
        'confirmation_score_inspected':False,'original_job_permanently_FAILED':True,'new_optimizer_updates':0,'new_training_candidates':0,
        'final_unique_confirmation_outputs':576,'final_unique_already_TRAIN_gap_outputs':72,'additional_tail_GPU_jobs_maximum':1,
        'tail_Pod_seconds':6600,'tail_Job_seconds':8400,'study_GPU_ceiling_seconds_unchanged':93600,
        'original_timers_or_sampling_or_data_or_selection_changed':False,
        'budget_before_tail':{k:v for k,v in budget.items() if k!='private_jobs'}})
    return plan,json.loads(gzip.decompress(raw)),cm['data']['worker.py'],launch

def main():
    plan,files,original_worker,oldlaunch=activate();TAIL.mkdir()
    for name in ['kali_curriculum_prefix_resume_20261118.py','eval_kali_curriculum_confirmation_resume_20261118.py']:
        files['scripts/'+name]=(ROOT/'scripts'/name).read_text()
    files['scripts/original_confirmation_worker_20261117.py']=original_worker
    raw=gzip.compress(json.dumps(files).encode(),mtime=0);worker=ROOT/'scripts/kali_curriculum_confirmation_tail_worker_20261118.py'
    cfg=dict(oldlaunch['config']);cfg.update(worker_sha256=sha(worker),bundle_sha256=hashlib.sha256(raw).hexdigest(),
        durable_output='/cache/kali-execution-20261114/'+NAME,runtime_seconds=6600,
        original_job_status='FAILED',new_optimizer_updates=0,additional_tail_GPU_jobs=1,
        failed_durable_output=oldlaunch['config']['durable_output'],original_failed_job_uid=read(ACT)['failed_job_uid'],
        deadline_activation_sha256=sha(ACT),source_prediction_files=read(ACT)['source_prediction_files'],
        original_eval_sha256=hashlib.sha256(files['scripts/eval_kali_curriculum_sft_20261117.py'].encode()).hexdigest())
    save(TAIL/'launch-freeze-private.json',{'config':cfg,'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()},
        'new_training_updates':0,'same_original_frozen_cohort':True,'evaluation_gold_sent_to_GPU':False})
    names=['run_kali_curriculum_confirmation_tail_20261118.py','audit_kali_curriculum_confirmation_tail_20261118.py',
        'kali_curriculum_confirmation_tail_worker_20261118.py','eval_kali_curriculum_confirmation_resume_20261118.py',
        'kali_curriculum_prefix_resume_20261118.py','kali_curriculum_gpu_budget_20261117.py']
    source=TAIL/'loaded-runtime-source-private';source.mkdir()
    for name in names:(source/name).write_bytes((ROOT/'scripts'/name).read_bytes())
    save(TAIL/'runtime-source-freeze-private.json',{name:sha(source/name) for name in names})
    pods=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
    assert not gpu_cache_conflicts(pods,'miw113-kali-two-model-cache-1115')
    nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];eligible=[]
    for n in nodes:
        labels=n['metadata'].get('labels',{})
        if n['metadata']['name']=='hcc-prp-c5038.unl.edu' or labels.get('nvidia.com/gpu.product')!='NVIDIA-RTX-A6000':continue
        if int(labels.get('nvidia.com/cuda.driver.major','0'))<570 or not int(n['status'].get('allocatable',{}).get('nvidia.com/rtxa6000','0')):continue
        if n['spec'].get('unschedulable') or any(t['effect'] in ['NoSchedule','NoExecute'] for t in n['spec'].get('taints',[])):continue
        if any(c['type']=='Ready' and c['status']=='True' for c in n['status'].get('conditions',[])):eligible.append(n['metadata']['name'])
    assert eligible
    print(json.dumps(submit(NAME,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg)},
        {'cpu':'500m','memory':'20Gi','ephemeral-storage':'24Gi','nvidia.com/rtxa6000':'1'},
        binary_files={'bundle.json.gz':raw},cache=True,readonly=False,cache_claim='miw113-kali-two-model-cache-1115',cache_region=None,
        node_names=eligible,gpu_products=['NVIDIA-RTX-A6000'],preferred_node_names=['hcc-prp-c5036.unl.edu'],runtime=6600)),flush=True)
    until=time.monotonic()+8700;collected=False;previous=None
    while time.monotonic()<until:
        try:state=poll(NAME)
        except Exception as exc:print('TRANSIENT_CONFIRM_TAIL '+type(exc).__name__,flush=True);time.sleep(30);continue
        log=JOBS/NAME/'worker.log';frames=parse(log.read_text(),'CURRICULUM_CONFIRM_ARTIFACT') if log.exists() else None
        if frames is not None:
            dest=TAIL/'runs';dest.mkdir(exist_ok=True)
            for name,text in frames.items():assert Path(name).name==name;(dest/name).write_text(text)
            collected=True
        state.pop('log_tail',None);save(TAIL/'monitor-private.json',state)
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        if state['status'] in ['FAILED','SUCCEEDED']:
            if state['status']=='SUCCEEDED':assert collected
            cleanup(NAME);assert state['status']=='SUCCEEDED','Keep actual failed tail; no automatic resubmission'
            adopt();return
        time.sleep(30)
    raise TimeoutError('Finite single confirmation tail exhausted; no duplicate')

def adopt():
    import shutil
    actual=read(TAIL/'runs/execution-receipt.json');old=read(CONF/'original-deadline-failed-private/runs/execution-receipt.json')
    assert actual['status']=='COMPLETE' and actual['original_job_status']=='FAILED' and actual['training_updates']==0
    assert actual['selection_sha256']==old['selection_sha256'] and actual['official_TEST_queries']==0
    target=CONF/'runs';assert not target.exists();target.mkdir()
    for p in (TAIL/'runs').iterdir():
        if p.name!='execution-receipt.json':shutil.copy2(p,target/p.name)
    composite=dict(actual);composite.update(derived_not_emitted_by_original_worker=True,
        completion_kind='ORIGINAL_FROZEN_COHORT_PLUS_DEADLINE_CONTINUATION',original_job_status='FAILED',
        worker_sha256=old['worker_sha256'],bundle_sha256=old['bundle_sha256'],
        original_worker_sha256=old['worker_sha256'],actual_tail_worker_sha256=actual['worker_sha256'],
        seconds=old['seconds']+actual['seconds'],confirmation_inference_started=old['confirmation_inference_started'] or actual['confirmation_inference_started'],
        original_execution_sha256=sha(CONF/'original-deadline-failed-private/runs/execution-receipt.json'),
        actual_tail_execution_sha256=sha(TAIL/'runs/execution-receipt.json'))
    save(target/'execution-receipt.json',composite)
    from audit_kali_curriculum_confirmation_tail_20261118 import audit
    proof=audit(CONF);save(TAIL/'audit-private.json',proof)
    print(json.dumps({'status':'SAME_FROZEN_COHORT_CONFIRMED_COMPLETE_AFTER_VERIFIED_DEADLINE_CONTINUATION','proof':proof}),flush=True)

if __name__=='__main__':main()
