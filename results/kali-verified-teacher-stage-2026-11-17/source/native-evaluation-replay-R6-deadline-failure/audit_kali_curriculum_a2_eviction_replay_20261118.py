"""Audit original training plus zero-update full evaluation replay after eviction."""
import base64,gzip,hashlib,json
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,sha
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_framed_artifacts_20261117 import parse

STAGE=OUT/'paired-sft';RESCUE=STAGE/'A2-node-eviction-private'
ORIGINAL='miw113-kali-curriculum-sft-a2-1117';REPLAY='miw113-kali-curriculum-eval-a2-r6-1117'

def read(p):return json.loads(p.read_text())

def audit():
    from audit_kali_curriculum_complete_20261117 import validate_training,validate_predictions
    recovered=read(RESCUE/'recovered-private.json');original=RESCUE/'original'
    assert recovered['status']=='ORIGINAL_A2_WEIGHTS_AND_TRAINING_RECOVERED_PREDICTION_FILE_ZERO_BYTES'
    assert sha(RESCUE/'original-a2.tar.gz')==recovered['archive_sha256']
    assert sha(original/'rescue-manifest-private.json')==recovered['manifest_sha256']
    manifest=read(original/'rescue-manifest-private.json')
    for name,meta in manifest['files'].items():
        path=original/name;assert path.resolve().is_relative_to(original.resolve())
        assert path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256']
    assert (original/'reasoning-predictions.json').stat().st_size==0
    evidence=read(RESCUE/'original-cluster-evidence-private.json')
    assert evidence['job']['metadata']['uid']=='bb4abe45-cdd5-48ba-ad23-93982101b650'
    assert set(e['reason'] for e in evidence['pod_events']['items'])>={'NodeNotReady','TaintManagerEviction'}
    old_host=read(JOBS/ORIGINAL/'host.json')
    assert old_host['uid']==evidence['job']['metadata']['uid'] and old_host['status']=='FAILED' and old_host['resources_cleaned']
    old_launch=read(STAGE/'runs/A2/launch-freeze-private.json')
    objects=read(JOBS/ORIGINAL/'objects.json');cm=next(o for o in objects if o['kind']=='ConfigMap')
    raw=base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==old_launch['config']['bundle_sha256']
    assert hashlib.sha256(cm['data']['worker.py'].encode()).hexdigest()==old_launch['config']['worker_sha256']
    original_bundle=json.loads(gzip.decompress(raw))
    data=read(STAGE/'paired-training-private.json');data['protocol']['learning_rate']=2e-5
    actual_training=json.loads(original_bundle['stage/paired-training-private.json']);actual_training['protocol']['learning_rate']=2e-5
    assert actual_training==data
    receipt=read(original/'reasoning/receipt.json');trace=read(original/'reasoning/trace.json')
    validate_training(data,'reasoning',receipt,trace,hashlib.sha256((json.dumps(data)+'\n').encode()).hexdigest(),2e-5)
    assert sha(original/'reasoning/adapter/adapter_model.safetensors')==receipt['adapter_sha256']==recovered['adapter_sha256']
    replay=RESCUE/'evaluation-replay';launch=read(replay/'launch-freeze-private.json');cfg=launch['config']
    host=read(JOBS/REPLAY/'host.json');assert host['status']=='SUCCEEDED' and host['resources_cleaned']
    if (RESCUE/'queue-only-handoff-private.json').exists():
        queue=read(RESCUE/'queue-only-handoff-private.json')
        assert queue['status']=='SAME_UNASSIGNED_JOB_QUEUE_WINDOW_AMENDED_NO_GPU_RUNTIME_CHANGE'
        assert queue['Pod_GPU_runtime_seconds_UNCHANGED']==10800
        assert queue['old_Job_activeDeadlineSeconds']==12600 and queue['actual_Job_deadline_after']==21600
        assert queue['same_Pod_UID_verified_after_patch'] and queue['new_optimizer_updates']==0
        migration=read(RESCUE/'A100-hardware-migration-private.json')
        assert migration['cancelled_job_uid']==queue['job_uid'] and migration['allocated_GPU_seconds']==0
        cancelled=read(JOBS/migration['cancelled_job']/'host.json')
        assert cancelled['status']=='REPLACED_UNSCHEDULED_APPROVED_A100' and cancelled['resources_cleaned']
        deleted_file=RESCUE/'unassigned-A6000-to-A100-migration-private/final-deleted-Pod-private.json'
        assert sha(deleted_file)==migration['final_deleted_Pod_evidence_sha256']
        deleted=read(deleted_file);assert not deleted['spec'].get('nodeName') and deleted['metadata']['uid']==migration['cancelled_pod_uid']
        fit=read(RESCUE/'A100-resource-fit-private.json');cancelled=read(JOBS/fit['cancelled_job']/'host.json')
        assert fit['allocated_GPU_seconds']==0 and fit['new_optimizer_updates']==0
        assert cancelled['status']=='REPLACED_UNSCHEDULED_RESOURCE_FIT' and cancelled['resources_cleaned']
        path=RESCUE/'unassigned-A100-resource-fit-private/final-deleted-Pod-private.json'
        assert sha(path)==fit['final_deleted_Pod_evidence_sha256'] and not read(path)['spec'].get('nodeName')
        assert host['resources']==read(RESCUE/'A6000-CPU-fit-private.json')['after']
    retry=read(RESCUE/'zero-response-CUDA-retry-protocol-private.json')
    failed=read(JOBS/retry['failed_replay_job']/'host.json')
    assert failed['status']=='FAILED' and failed['resources_cleaned'] and failed['uid']==retry['failed_replay_job_uid']
    first=RESCUE/'evaluation-replay-attempt1-failed-private/runs'
    assert sha(first/'execution-receipt.json')==retry['receipt_sha256'] and sha(first/'eval-resume.log')==retry['log_sha256']
    assert 'CUDA error: unspecified launch failure' in (first/'eval-resume.log').read_text()
    assert not(first/'reasoning-predictions.json').exists() and retry['completed_response_outputs']==0
    assert all(p.get('node')!='hcc-prp-c5038.unl.edu' for p in host['pods'])
    recovery=read(RESCUE/'A6000-fingerprint-recovery-private.json')
    failed_cross=read(JOBS/recovery['failed_job']/'host.json')
    assert failed_cross['status']=='FAILED' and failed_cross['resources_cleaned'] and failed_cross['uid']==recovery['failed_job_uid']
    cross=RESCUE/'evaluation-replay-A100-fingerprint-failed-private/runs'
    assert sha(cross/'execution-receipt.json')==recovery['failed_receipt_sha256'] and sha(cross/'eval-resume.log')==recovery['failed_log_sha256']
    assert 'Reloaded model differs from trained adapter probe' in (cross/'eval-resume.log').read_text() and not(cross/'reasoning-predictions.json').exists()
    assert recovery['completed_responses']==recovery['new_optimizer_updates']==0 and recovery['fingerprint_check_not_relaxed']
    cpu_fit=read(RESCUE/'A6000-CPU-fit-private.json')
    cancelled=read(JOBS/cpu_fit['cancelled_job']/'host.json')
    assert cancelled['uid']==cpu_fit['cancelled_job_uid'] and cancelled['status']=='REPLACED_UNSCHEDULED_CPU_MEMORY_FIT' and cancelled['resources_cleaned']
    deleted_file=RESCUE/'unassigned-A6000-CPU-fit-private/final-deleted-Pod-private.json'
    deleted=read(deleted_file)
    assert sha(deleted_file)==cpu_fit['final_deleted_Pod_evidence_sha256'] and deleted['metadata']['uid']==cpu_fit['cancelled_pod_uid']
    assert not deleted['spec'].get('nodeName') and deleted['status']['phase']=='Pending'
    assert cpu_fit['allocated_GPU_seconds']==cpu_fit['new_optimizer_updates']==0
    actual=parse((JOBS/REPLAY/'worker.log').read_text(),'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT');assert actual is not None
    for name,text in actual.items():assert (replay/'runs'/name).read_text()==text
    execution=read(replay/'runs/execution-receipt.json')
    assert execution['status']=='COMPLETE' and execution['training_updates']==0
    assert execution['worker_sha256']==cfg['worker_sha256'] and execution['bundle_sha256']==cfg['bundle_sha256']
    assert execution['original_job_uid']==old_host['uid'] and execution['original_adapter_sha256']==receipt['adapter_sha256']
    assert execution['original_training_receipt_sha256']==sha(original/'reasoning/receipt.json')
    assert execution['original_prediction_file_zero_bytes'] and execution['official_TEST_queries']==execution['confirmation_queries']==0
    submitted=read(JOBS/REPLAY/'objects.json');cm=next(o for o in submitted if o['kind']=='ConfigMap')
    raw=base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==cfg['bundle_sha256'] and hashlib.sha256(cm['data']['worker.py'].encode()).hexdigest()==cfg['worker_sha256']
    bundle=json.loads(gzip.decompress(raw));assert not any('references' in name or 'paired-training' in name for name in bundle)
    for name in ['evaluation-inputs-private.json','evaluation-protocol.json']:
        assert bundle['stage/'+name]==(STAGE/name).read_text()==original_bundle['stage/'+name]
    assert json.loads(bundle['stage/model-protocol.json'])==data['model_protocol']
    assert bundle['scripts/eval_kali_curriculum_sft_20261117.py']==original_bundle['scripts/eval_kali_curriculum_sft_20261117.py']
    pred=read(replay/'runs/reasoning-predictions.json')
    assert pred['GPU'] in data['model_protocol']['allowed_GPU_models'] and pred['GPU']=='NVIDIA RTX A6000'
    measured=validate_predictions(pred,read(STAGE/'evaluation-inputs-private.json'),read(STAGE/'evaluation-protocol.json'),receipt['adapter_sha256'])
    assert (STAGE/'runs/A2/reasoning-predictions.json').read_text()==(replay/'runs/reasoning-predictions.json').read_text()
    for name in ['receipt.json','trace.json']:assert (STAGE/'runs/A2/reasoning'/name).read_bytes()==(original/'reasoning'/name).read_bytes()
    derived=read(STAGE/'runs/A2/execution-receipt.json')
    assert derived['status']=='COMPLETE' and derived['derived_not_emitted_by_original_worker']
    assert derived['completion_kind']=='ORIGINAL_TRAINING_PLUS_ZERO_UPDATE_FULL_EVALUATION_REPLAY'
    assert derived['worker_sha256']==old_launch['config']['worker_sha256'] and derived['bundle_sha256']==old_launch['config']['bundle_sha256']
    assert derived['original_job_status']=='FAILED' and derived['evaluation_replay_job_uid']==host['uid']
    assert derived['evaluation_replay_execution_sha256']==sha(replay/'runs/execution-receipt.json')
    result={'status':'ORIGINAL_A2_TRAINING_AND_ZERO_UPDATE_FULL_EVAL_REPLAY_AUDITED',
        'actual_original_training_updates':32,'new_optimizer_updates':0,'original_job_stays_failed':True,
        'original_prediction_file_zero_bytes':True,'reused_prediction_responses':0,
        'replayed_evaluation_responses':measured['responses'],'replayed_inference_seeds':[3407,4407,5407],
        'same_original_adapter_and_numerical_evaluation_code':True,'official_TEST_queries':0,
        'lost_original_inference_telemetry_at_least':312,
        'full_replay_GPU_attempts':3,'first_replay_GPU_attempt_stays_failed':True,
        'first_replay_completed_response_outputs':0,'failed_node_explicitly_excluded_from_completed_replay':True,
        'unassigned_A6000_hardware_request_cancelled_GPU_seconds':0,
        'completed_GPU_model':pred['GPU'],'completed_GPU_was_in_original_allowed_list':True,
        'different_GPU_from_fixed_controls':False,'A100_attempt_rejected_before_any_completed_response':True,'A100_original_logit_fingerprint_check_not_relaxed':True,'exact_original_adapter_reload_logit_probe_passed':True,
        'unassigned_A100_resource_fit_request_cancelled_GPU_seconds':0,
        'unassigned_A6000_CPU_fit_request_cancelled_GPU_seconds':0,'completed_resource_requests':host['resources']}
    return result

if __name__=='__main__':print(json.dumps(audit(),indent=2))
