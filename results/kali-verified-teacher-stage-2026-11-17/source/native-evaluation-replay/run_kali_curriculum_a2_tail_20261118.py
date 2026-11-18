"""Conditional finite continuation after actual R6 deadline failure; zero SFT.

Never invoked merely for poor scores. Reuses every committed complete batch,
replays the first batch exactly, and generates only the missing original tail.
"""
import argparse,base64,datetime,gzip,hashlib,json,time
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save,sha
from kali_execution_jobs_20261114 import OUT as JOBS,k,poll,submit,cleanup,gpu_cache_conflicts
from kali_framed_artifacts_20261117 import parse
from kali_curriculum_prefix_resume_20261118 import validate_prefix

STAGE=OUT/'paired-sft';RESCUE=STAGE/'A2-node-eviction-private'
OLD='miw113-kali-curriculum-eval-a2-r6-1117'
NAME='miw113-kali-curriculum-eval-a2-r7-1117'
ACT=RESCUE/'deadline-tail-activation-private.json'

def read(path):return json.loads(path.read_text())

def activate():
    assert not ACT.exists() and not (JOBS/NAME).exists(),'No repeated tail Job'
    assert not (STAGE/'runs/A2/score-private.json').exists() and not (STAGE/'confirmation').exists()
    planfile=STAGE/'prefix-tail-operational-plan-before-A2-score-private.json';plan=read(planfile)
    assert plan['status']=='CONDITIONAL_OPERATIONAL_PLAN_FROZEN_BEFORE_A2_SCORE_NOT_ACTIVATED'
    assert not plan['A2_score_inspected'] and plan['confirmation_queries']==plan['official_TEST_queries']==0
    host=read(JOBS/OLD/'host.json')
    assert host['uid']==plan['failed_full_replay_job_uid'] and host['status']=='FAILED' and host['resources_cleaned']
    old=RESCUE/'evaluation-replay';execution=read(old/'runs/execution-receipt.json')
    assert execution['status']=='FAILED' and execution['training_updates']==0
    assert 'STAGE_FAILED TimeoutExpired' in (JOBS/OLD/'worker.log').read_text(),'Actual original subprocess deadline required'
    frames=parse((JOBS/OLD/'worker.log').read_text(),'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT');assert frames is not None
    for name,text in frames.items():assert (old/'runs'/name).read_text()==text
    source=old/'runs/reasoning-predictions.json';prefix=read(source)
    receipt=read(RESCUE/'original/reasoning/receipt.json')
    n=validate_prefix(prefix,read(STAGE/'evaluation-inputs-private.json'),read(STAGE/'evaluation-protocol.json'),receipt['adapter_sha256'],minimum=plan['minimum_ordered_whole_batch_prefix'])
    assert n<624,'A complete prediction artifact requires a different explicit audit, not this tail path'
    launch=read(old/'launch-freeze-private.json')
    assert execution['worker_sha256']==launch['config']['worker_sha256'] and execution['bundle_sha256']==launch['config']['bundle_sha256']
    actual=read(JOBS/OLD/'objects.json');cm=next(o for o in actual if o['kind']=='ConfigMap')
    raw=base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==execution['bundle_sha256']
    assert hashlib.sha256(cm['data']['worker.py'].encode()).hexdigest()==execution['worker_sha256']
    bundle=json.loads(gzip.decompress(raw))
    assert hashlib.sha256(bundle['scripts/eval_kali_curriculum_sft_20261117.py'].encode()).hexdigest()==sha(ROOT/'scripts/eval_kali_curriculum_sft_20261117.py')
    archive=RESCUE/'evaluation-replay-R6-deadline-failed-private';assert not archive.exists()
    record={'status':'ACTUAL_DEADLINE_FAILURE_PREFIX_TAIL_ACTIVATED_BEFORE_A2_SCORE',
        'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operational_plan_sha256':sha(planfile),
        'prior_frozen_contingency_sha256':sha(STAGE/'conditional-prefix-resume-before-A2-score-private.json'),
        'failed_job':OLD,'failed_job_uid':host['uid'],'failed_host_sha256':sha(JOBS/OLD/'host.json'),
        'failed_execution_sha256':sha(old/'runs/execution-receipt.json'),'failed_eval_log_sha256':sha(old/'runs/eval-resume.log'),
        'retained_prefix_sha256':sha(source),'retained_prefix_responses':n,'original_eval_sha256':sha(ROOT/'scripts/eval_kali_curriculum_sft_20261117.py'),
        'new_unique_tail_responses':624-n,'first_batch_exact_replay_required':16,'minimum_prefix_responses':plan['minimum_ordered_whole_batch_prefix'],
        'study_ceiling_before_seconds':plan['study_ceiling_before_seconds'],'study_ceiling_after_seconds':plan['study_ceiling_after_seconds'],
        'ABA_ceiling_before_seconds':plan['ABA_ceiling_before_seconds'],'ABA_ceiling_after_seconds':plan['ABA_ceiling_after_seconds'],
        'new_optimizer_updates':0,'new_training_candidates':0,'A2_score_inspected':False,'confirmation_queries':0,'official_TEST_queries':0,
        'tail_Pod_seconds':plan['tail_Pod_seconds'],'tail_Job_seconds':plan['tail_Job_seconds'],'failed_job_permanently_failed':True}
    old.rename(archive);save(ACT,record)
    from kali_curriculum_gpu_budget_20261117 import ledger
    budget=ledger(prospective_seconds=plan['tail_Job_seconds']+plan['confirmation_Job_reserve_seconds']+plan['safety_reserve_seconds'])
    native_used=sum(r['conservative_gpu_seconds'] for r in budget['private_jobs']
        if r['job'] in ['miw113-kali-curriculum-sft-a1-1117','miw113-kali-curriculum-sft-a2-1117'] or r['job'].startswith('miw113-kali-curriculum-eval-a2-r'))
    assert native_used+plan['tail_Job_seconds']<=plan['ABA_ceiling_after_seconds'],'Tail must also fit the independently frozen ABA allocation ceiling'
    save(RESCUE/'tail-precall-budget-private.json',{'study':{k:v for k,v in budget.items() if k!='private_jobs'},
        'ABA_completed_allocation_seconds':native_used,'ABA_prospective_tail_seconds':plan['tail_Job_seconds'],
        'ABA_ceiling_seconds':plan['ABA_ceiling_after_seconds'],'confirmation_Job_reserve_seconds':18000,'safety_reserve_seconds':300})
    return record,bundle,launch,plan

def resume_unsubmitted():
    assert ACT.exists() and not (JOBS/NAME).exists(),'Only resume before ANY Job submission'
    assert not (STAGE/'runs/A2/score-private.json').exists() and not (STAGE/'confirmation').exists()
    a=read(ACT);plan=read(STAGE/'prefix-tail-operational-plan-before-A2-score-private.json')
    assert a['operational_plan_sha256']==sha(STAGE/'prefix-tail-operational-plan-before-A2-score-private.json')
    old=RESCUE/'evaluation-replay-R6-deadline-failed-private';failed=read(JOBS/OLD/'host.json')
    assert failed['status']=='FAILED' and failed['resources_cleaned'] and sha(JOBS/OLD/'host.json')==a['failed_host_sha256']
    prepared=RESCUE/'evaluation-replay';cfg=read(prepared/'launch-freeze-private.json')['config']
    for name,digest in read(prepared/'runtime-source-freeze-private.json').items():
        assert sha(prepared/'loaded-runtime-source-private'/name)==digest
        if name!='run_kali_curriculum_a2_tail_20261118.py':assert sha(ROOT/'scripts'/name)==digest
    error=(STAGE/'A2-evaluation-replay-monitor.log').read_text()
    assert 'connect: operation not permitted' in error and 'read_pods' in error
    (prepared/'pre-submit-error-monitor.log').write_text(error)
    save(prepared/'local-pre-submit-failure-private.json',{'status':'LOCAL_SANDBOX_NETWORK_DENIED_BEFORE_SUBMISSION','GPU_Job_created':False,'GPU_seconds':0,'new_training_updates':0})
    archive=RESCUE/'tail-pre-submit-network-denied-private';assert not archive.exists();prepared.rename(archive)
    cm=next(o for o in read(JOBS/OLD/'objects.json') if o['kind']=='ConfigMap')
    bundle=json.loads(gzip.decompress(base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)))
    return a,bundle,read(old/'launch-freeze-private.json'),plan,cfg

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume-unsubmitted',action='store_true');args=parser.parse_args()
    expected_cfg=None
    if args.resume_unsubmitted:activation,files,oldlaunch,plan,expected_cfg=resume_unsubmitted()
    else:activation,files,oldlaunch,plan=activate()
    dest=RESCUE/'evaluation-replay';dest.mkdir()
    for name in ['kali_curriculum_prefix_resume_20261118.py','eval_kali_curriculum_prefix_resume_20261118.py']:
        files['scripts/'+name]=(ROOT/'scripts'/name).read_text()
    worker=ROOT/'scripts/kali_curriculum_a2_prefix_resume_worker_20261118.py'
    raw=gzip.compress(json.dumps(files).encode(),mtime=0);cfg=dict(oldlaunch['config'])
    cfg.update(worker_sha256=sha(worker),bundle_sha256=hashlib.sha256(raw).hexdigest(),
        durable_output='/cache/kali-execution-20261114/'+NAME,runtime_seconds=plan['tail_Pod_seconds'],
        prefix_cache='/cache/kali-execution-20261114/'+OLD+'/reasoning-predictions.json',
        prefix_sha256=activation['retained_prefix_sha256'],reused_prefix_responses=activation['retained_prefix_responses'],
        minimum_prefix_responses=activation['minimum_prefix_responses'],failed_full_replay_job_uid=activation['failed_job_uid'],
        original_eval_sha256=activation['original_eval_sha256'],additional_tail_GPU_jobs=1,
        prefix_contingency_sha256=sha(STAGE/'prefix-tail-operational-plan-before-A2-score-private.json'))
    if expected_cfg is not None:assert cfg==expected_cfg,'Do not change the prepared GPU payload during host network recovery'
    save(dest/'launch-freeze-private.json',{'config':cfg,'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()},
        'training_updates':0,'evaluation_gold_sent_to_GPU':False,'deadline_prefix_continuation':True,'activation_sha256':sha(ACT)})
    snap=dest/'loaded-runtime-source-private';snap.mkdir()
    names=['run_kali_curriculum_a2_tail_20261118.py','kali_curriculum_a2_prefix_resume_worker_20261118.py',
        'kali_curriculum_prefix_resume_20261118.py','eval_kali_curriculum_prefix_resume_20261118.py',
        'audit_kali_curriculum_a2_eviction_replay_20261118.py','audit_kali_curriculum_a2_tail_20261118.py',
        'kali_curriculum_gpu_budget_20261117.py','run_kali_curriculum_a2_eval_replay_20261118.py']
    for name in names:(snap/name).write_bytes((ROOT/'scripts'/name).read_bytes())
    save(dest/'runtime-source-freeze-private.json',{n:sha(snap/n) for n in names})
    active=read_pods();assert not gpu_cache_conflicts(active,'miw113-kali-two-model-cache-1115')
    nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];eligible=[]
    for node in nodes:
        if node['metadata']['name']=='hcc-prp-c5038.unl.edu':continue
        labels=node['metadata'].get('labels',{})
        if labels.get('nvidia.com/gpu.product')!='NVIDIA-RTX-A6000' or int(labels.get('nvidia.com/cuda.driver.major','0'))<570:continue
        if not int(node['status'].get('allocatable',{}).get('nvidia.com/rtxa6000','0')):continue
        if node['spec'].get('unschedulable') or any(t['effect'] in ['NoSchedule','NoExecute'] for t in node['spec'].get('taints',[])):continue
        if any(c['type']=='Ready' and c['status']=='True' for c in node['status'].get('conditions',[])):eligible.append(node['metadata']['name'])
    assert eligible
    resources=read(RESCUE/'A6000-CPU-fit-private.json')['after']
    submitted=submit(NAME,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg)},resources,
        binary_files={'bundle.json.gz':raw},cache=True,readonly=False,cache_claim='miw113-kali-two-model-cache-1115',cache_region=None,
        node_names=eligible,gpu_products=['NVIDIA-RTX-A6000'],preferred_node_names=['hcc-prp-c5036.unl.edu'],runtime=plan['tail_Pod_seconds'])
    assert read(JOBS/NAME/'objects.json')[1]['spec']['activeDeadlineSeconds']==plan['tail_Job_seconds']
    print(json.dumps(submitted),flush=True);until=time.monotonic()+plan['tail_Job_seconds']+300;collected=False;previous=None
    while time.monotonic()<until:
        try:state=poll(NAME)
        except Exception as exc:print('TRANSIENT_TAIL_POLL '+type(exc).__name__,flush=True);time.sleep(30);continue
        logfile=JOBS/NAME/'worker.log';frames=parse(logfile.read_text(),'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT') if logfile.exists() else None
        if frames is not None:
            for name,text in frames.items():
                path=dest/'runs'/name;assert path.resolve().is_relative_to((dest/'runs').resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            collected=True
        state.pop('log_tail',None);save(dest/'monitor-private.json',state)
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        if state['status'] in ['FAILED','SUCCEEDED']:
            if state['status']=='SUCCEEDED':assert collected
            cleanup(NAME);assert state['status']=='SUCCEEDED','One finite tail attempt failed; keep all evidence, no automatic resubmission'
            from run_kali_curriculum_a2_eval_replay_20261118 import adopt_collected_replay
            adopt_collected_replay();return
        time.sleep(30)
    raise TimeoutError('Finite single tail interval exhausted; do not duplicate')

def read_pods():return json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']

if __name__=='__main__':main()
