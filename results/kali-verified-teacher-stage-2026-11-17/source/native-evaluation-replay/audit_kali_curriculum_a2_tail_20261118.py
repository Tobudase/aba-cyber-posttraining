"""Certify reuse of every R6 batch and only the original missing suffix."""
import base64,gzip,hashlib,json
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,sha
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_framed_artifacts_20261117 import parse
from kali_curriculum_prefix_resume_20261118 import validate_prefix,blocks

STAGE=OUT/'paired-sft';RESCUE=STAGE/'A2-node-eviction-private'
def read(path):return json.loads(path.read_text())

def audit_tail(pred):
    actfile=RESCUE/'deadline-tail-activation-private.json';a=read(actfile)
    planfile=STAGE/'prefix-tail-operational-plan-before-A2-score-private.json';plan=read(planfile)
    assert a['status']=='ACTUAL_DEADLINE_FAILURE_PREFIX_TAIL_ACTIVATED_BEFORE_A2_SCORE'
    assert a['operational_plan_sha256']==sha(planfile) and not a['A2_score_inspected'] and a['confirmation_queries']==0
    assert plan['new_training_candidates']==plan['new_training_updates']==0 and not plan['current_Job_cancel_resize_pause_or_deadline_change']
    failed=read(JOBS/a['failed_job']/'host.json')
    assert failed['uid']==a['failed_job_uid'] and failed['status']=='FAILED' and failed['resources_cleaned']
    assert sha(JOBS/a['failed_job']/'host.json')==a['failed_host_sha256']
    archive=RESCUE/'evaluation-replay-R6-deadline-failed-private';prefix=read(archive/'runs/reasoning-predictions.json')
    assert sha(archive/'runs/reasoning-predictions.json')==a['retained_prefix_sha256']
    assert sha(archive/'runs/execution-receipt.json')==a['failed_execution_sha256']
    assert sha(archive/'runs/eval-resume.log')==a['failed_eval_log_sha256']
    log=(JOBS/a['failed_job']/'worker.log').read_text();assert 'STAGE_FAILED TimeoutExpired' in log
    frames=parse(log,'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT');assert frames is not None
    for name,text in frames.items():assert (archive/'runs'/name).read_text()==text
    proto=read(STAGE/'evaluation-protocol.json');rows=read(STAGE/'evaluation-inputs-private.json')
    n=validate_prefix(prefix,rows,proto,pred['adapter_sha256'],minimum=plan['minimum_ordered_whole_batch_prefix'])
    assert n==a['retained_prefix_responses'] and pred['predictions'][:n]==prefix['predictions']
    proof=pred['prefix_resume'];assert proof['prefix_sha256']==a['retained_prefix_sha256']
    assert proof['retained_original_prefix_responses']==n and proof['new_suffix_unique_responses']==624-n
    assert proof['exact_first_batch_replay_responses']==16 and proof['replayed_batch_not_double_counted']
    assert proof['new_training_updates']==0
    current=RESCUE/'evaluation-replay';cfg=read(current/'launch-freeze-private.json')['config']
    assert cfg['prefix_sha256']==a['retained_prefix_sha256'] and cfg['reused_prefix_responses']==n
    assert cfg['additional_tail_GPU_jobs']==1 and cfg['runtime_seconds']==plan['tail_Pod_seconds']==6600
    assert cfg['minimum_prefix_responses']==plan['minimum_ordered_whole_batch_prefix']==416
    assert cfg['prefix_contingency_sha256']==sha(planfile)
    execution=read(current/'runs/execution-receipt.json')
    assert execution['prefix_resume_attempt'] and execution['training_updates']==0
    assert execution['reused_prefix_responses']==n and execution['prefix_sha256']==a['retained_prefix_sha256']
    assert execution['failed_full_replay_job_uid']==a['failed_job_uid'] and execution['additional_tail_GPU_jobs']==1
    assert execution['prefix_contingency_before_A2_score_sha256']==sha(planfile)
    original=read(JOBS/a['failed_job']/'objects.json');cm=next(o for o in original if o['kind']=='ConfigMap')
    bundle=json.loads(gzip.decompress(base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)))
    source=bundle['scripts/eval_kali_curriculum_sft_20261117.py']
    assert proof['original_eval_sha256']==hashlib.sha256(source.encode()).hexdigest()==a['original_eval_sha256']
    assert proof['original_generation_block_sha256']==blocks(source)[2]
    host=read(JOBS/'miw113-kali-curriculum-eval-a2-r7-1117/host.json')
    assert host['status']=='SUCCEEDED' and host['resources_cleaned']
    objects=read(JOBS/host['job']/'objects.json');pod=next(o for o in objects if o['kind']=='Job')
    assert pod['spec']['activeDeadlineSeconds']==plan['tail_Job_seconds']==8400
    assert pod['spec']['template']['spec']['activeDeadlineSeconds']==6600
    currentcm=next(o for o in objects if o['kind']=='ConfigMap')
    currentbundle=json.loads(gzip.decompress(base64.b64decode(currentcm['binaryData']['bundle.json.gz'],validate=True)))
    for name,text in bundle.items():assert currentbundle[name]==text
    for name,digest in read(current/'runtime-source-freeze-private.json').items():
        assert sha(current/'loaded-runtime-source-private'/name)==digest
    for name in ['kali_curriculum_prefix_resume_20261118.py','eval_kali_curriculum_prefix_resume_20261118.py']:
        assert currentbundle['scripts/'+name]==(current/'loaded-runtime-source-private'/name).read_text()
    assert currentcm['data']['worker.py']==(current/'loaded-runtime-source-private/kali_curriculum_a2_prefix_resume_worker_20261118.py').read_text()
    evallog=(current/'runs/eval-resume.log').read_text()
    assert 'EXACT_ORIGINAL_FIRST_BATCH_REPLAY_PASS 16' in evallog and 'EVAL_COMPLETE_WITH_EXACT_PREFIX_CONTINUATION' in evallog
    assert pred['reload_audit']['trained_vs_reloaded_probe_identical']
    return {'status':'R6_ALL_COMMITTED_BATCHES_REUSED_EXACT_FIRST16_REPLAY_AND_MISSING_SUFFIX_VERIFIED',
        'retained_R6_prefix_responses':n,'new_unique_tail_responses':624-n,'physical_first_batch_replay_responses':16,
        'distinct_scored_responses':624,'additional_tail_GPU_attempts':1,'actual_R6_job_stays_failed':True,
        'original_numerical_setup_and_generation_blocks_unchanged':True,'new_optimizer_updates':0,
        'operational_plan_sha256':sha(planfile),'activation_sha256':sha(actfile),
        'study_ceiling_before_seconds':86400,'study_ceiling_after_seconds':93600,
        'ABA_ceiling_before_seconds':32400,'ABA_ceiling_after_seconds':39600,
        'confirmation_queries_at_amendment':0,'A2_score_inspected_at_amendment':False}
