"""Audit original training plus zero-update full evaluation replay after eviction."""
import base64,gzip,hashlib,json
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,sha
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_framed_artifacts_20261117 import parse

STAGE=OUT/'paired-sft';RESCUE=STAGE/'A2-node-eviction-private'
ORIGINAL='miw113-kali-curriculum-sft-a2-1117';REPLAY='miw113-kali-curriculum-eval-a2-r1-1117'

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
        'lost_original_inference_telemetry_at_least':312}
    return result

if __name__=='__main__':print(json.dumps(audit(),indent=2))
