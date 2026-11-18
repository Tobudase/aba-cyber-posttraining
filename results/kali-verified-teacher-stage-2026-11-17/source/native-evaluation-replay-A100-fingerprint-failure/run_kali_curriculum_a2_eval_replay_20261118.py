"""One zero-training full evaluation replay after a documented node eviction."""
import datetime,gzip,hashlib,json,subprocess,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT as JOBS,k,submit,poll,cleanup,gpu_cache_conflicts
from prepare_kali_verified_curriculum_20261117 import OUT,save,sha
from kali_framed_artifacts_20261117 import parse
from audit_kali_curriculum_a2_eviction_replay_20261118 import ORIGINAL,REPLAY,RESCUE,STAGE

def main():
    dest=RESCUE/'evaluation-replay';assert not dest.exists();dest.mkdir()
    recovered=json.loads((RESCUE/'recovered-private.json').read_text())
    migration=json.loads((RESCUE/'A100-hardware-migration-private.json').read_text())
    assert migration['allocated_GPU_seconds']==0 and migration['model_protocol_already_allowed_A100_80GB']
    fit=json.loads((RESCUE/'A100-resource-fit-private.json').read_text())
    assert fit['allocated_GPU_seconds']==0 and fit['same_original_model_weights_data_code_seed_decoder_and_score']
    assert json.loads((RESCUE/'resource-fit-verification-private.json').read_text())['scratch_bound_fits_24GiB']
    retry=json.loads((RESCUE/'zero-response-CUDA-retry-protocol-private.json').read_text())
    assert retry['completed_response_outputs']==retry['new_optimizer_updates']==0 and not retry['A2_quality_available']
    assert recovered['actual_updates']==32 and recovered['prefix_responses_available']==0
    assert not (STAGE/'runs/A2/score-private.json').exists() and not (STAGE/'native-controller').exists() and not (STAGE/'confirmation').exists()
    from kali_curriculum_gpu_budget_20261117 import ledger
    budget=ledger(prospective_seconds=12600+18000)
    protocol={'status':'NODE_EVICTION_REPLAY_FROZEN_BEFORE_A2_QUALITY_AND_CONFIRMATION',
        'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_job_remains_failed':True,
        'original_adapter_sha256':recovered['adapter_sha256'],'new_training_updates':0,'new_training_candidates':0,
        'reused_prediction_responses':0,'replayed_same_frozen_unique_responses':624,
        'input_protocol_scoring_model_and_seed_changes':False,'official_TEST_queries':0,'confirmation_queries':0,
        'ABA_allocation_ceiling_before_seconds':28800,'ABA_allocation_ceiling_after_seconds':32400,
        'reason':'Original A2 node NotReady caused eviction and0byte prediction file. First replay on recovered same node failed with CUDA unspecified launch failure before any completed response. Preserve both failed jobs; exclude that node, re-evaluate original32-step weights with unchanged data/code once. No A2 score was available. ABA allocation8h->9h solely infrastructure-only inference;64training updates unchanged.',
        'prior_zero_response_CUDA_retry_protocol_sha256':sha(RESCUE/'zero-response-CUDA-retry-protocol-private.json'),
        'explicitly_excluded_nodes':['hcc-prp-c5038.unl.edu'],'GPU_resource':'nvidia.com/a100','GPU_count':1,
        'GPU_hardware_already_allowed_in_original_model_protocol':True,'extra_zero_allocation_unassigned_hardware_request':1,
        'hardware_note':'Only1already-authorized A10080GB; original A6000 request finally DELETED with no node. Same exact reload probe remains mandatory; actual GPU difference from fixed controls is disclosed.',
        'resource_fit_proof_sha256':sha(RESCUE/'A100-resource-fit-private.json'),
        'resource_fit_verification_sha256':sha(RESCUE/'resource-fit-verification-private.json'),
        'study_GPU_ceiling_unchanged_seconds':86400,'A2_replay_Pod_seconds':10800,'A2_replay_Job_seconds':21600,
        'confirmation_Pod_ceiling_seconds_before':21600,'confirmation_Pod_ceiling_seconds_after':16200,
        'confirmation_Job_ceiling_seconds_after':18000,'prospective_conservative_budget_fits':budget['remaining_after_prospective_gpu_seconds']>=0,
        'confirmation_runtime_note':'Pre-call operational ceiling only; all24tasks,3seeds,2modes,4096tokens and4endpoints unchanged. No model selection uses confirmation.'}
    save(RESCUE/'replay-protocol-before-results-private.json',protocol)
    data=json.loads((STAGE/'paired-training-private.json').read_text());original=RESCUE/'original'
    receipt=json.loads((original/'reasoning/receipt.json').read_text());assert receipt['adapter_sha256']==recovered['adapter_sha256']
    files={'stage/model-protocol.json':json.dumps(data['model_protocol'])+'\n'}
    for name in ['evaluation-inputs-private.json','evaluation-protocol.json']:files['stage/'+name]=(STAGE/name).read_text()
    for name in ['eval_kali_curriculum_sft_20261117.py','kali_exact_adapter_loading_20261115.py','kali_framed_artifacts_20261117.py']:files['scripts/'+name]=(ROOT/'scripts'/name).read_text()
    assert not any('references' in n or 'paired-training' in n for n in files)
    bundle=gzip.compress(json.dumps(files).encode(),mtime=0);worker=ROOT/'scripts/kali_curriculum_a2_eval_replay_worker_20261118.py'
    old=json.loads((JOBS/ORIGINAL/'host.json').read_text());assert old['status']=='FAILED' and old['resources_cleaned']
    cfg={'worker_sha256':sha(worker),'bundle_sha256':hashlib.sha256(bundle).hexdigest(),
        'original_output':'/cache/kali-execution-20261114/'+ORIGINAL,'original_job_uid':old['uid'],
        'adapter_sha256':receipt['adapter_sha256'],'original_training_receipt_sha256':sha(original/'reasoning/receipt.json'),
        'durable_output':'/cache/kali-execution-20261114/'+REPLAY,'runtime_seconds':10800}
    save(dest/'launch-freeze-private.json',{'config':cfg,'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()},
        'training_updates':0,'evaluation_gold_sent_to_GPU':False,'original_job_stays_failed':True})
    snapshots=dest/'loaded-runtime-source-private';snapshots.mkdir()
    runtime_names=['run_kali_curriculum_a2_eval_replay_20261118.py','kali_curriculum_a2_eval_replay_worker_20261118.py',
        'audit_kali_curriculum_a2_eviction_replay_20261118.py','kali_curriculum_gpu_budget_20261117.py',
        'collect_kali_curriculum_queued_a2_20261118.py']
    for name in runtime_names:(snapshots/name).write_bytes((ROOT/'scripts'/name).read_bytes())
    save(dest/'runtime-source-freeze-private.json',{name:sha(snapshots/name) for name in runtime_names})
    active=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
    assert not gpu_cache_conflicts(active,'miw113-kali-two-model-cache-1115')
    nodes=json.loads(k('get','nodes','-o','json').stdout)['items']
    products=['NVIDIA-A100-SXM4-80GB','NVIDIA-A100-80GB-PCIe']
    eligible=[n['metadata']['name'] for n in nodes if n['metadata']['name']!='hcc-prp-c5038.unl.edu' and n['metadata'].get('labels',{}).get('nvidia.com/gpu.product') in products
        and int(n['status'].get('allocatable',{}).get('nvidia.com/a100','0'))>0
        and int(n['metadata'].get('labels',{}).get('nvidia.com/cuda.driver.major','0'))>=570
        and not n['spec'].get('unschedulable') and not any(t['effect'] in ['NoSchedule','NoExecute'] for t in n['spec'].get('taints',[]))
        and any(c['type']=='Ready' and c['status']=='True' for c in n['status'].get('conditions',[]))]
    assert eligible,'No healthy compatible already-authorized A10080GB node; do not bypass scheduling policy'
    submitted=submit(REPLAY,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg)},
        fit['after'],binary_files={'bundle.json.gz':bundle},
        cache=True,readonly=False,cache_claim='miw113-kali-two-model-cache-1115',cache_region=None,
        node_names=eligible,gpu_products=products,runtime=10800)
    patch=[{'op':'test','path':'/metadata/uid','value':submitted['uid']},{'op':'replace','path':'/spec/activeDeadlineSeconds','value':21600}]
    after=json.loads(k('patch','job',REPLAY,'--type=json','-p',json.dumps(patch),'-o','json').stdout)
    assert after['spec']['template']['spec']['activeDeadlineSeconds']==10800
    save(dest/'initial-queue-window-private.json',{'job_uid':submitted['uid'],'Job_seconds':21600,'GPU_Pod_seconds':10800})
    print(json.dumps(submitted),flush=True)
    until=time.monotonic()+22000;collected=False;previous=None
    while time.monotonic()<until:
        try:state=poll(REPLAY)
        except AssertionError:raise
        except Exception as exc:print('TRANSIENT_REPLAY_POLL '+type(exc).__name__,flush=True);time.sleep(30);continue
        from collect_kali_curriculum_queued_a2_20261118 import observe_assignment
        try:
            pods=json.loads(k('get','pods','-l','job-name='+REPLAY,'-o','json').stdout)['items']
            if len(pods)==1:observe_assignment({'job_uid':submitted['uid'],'pod_uid':pods[0]['metadata']['uid']})
        except subprocess.TimeoutExpired:print('TRANSIENT_ASSIGNMENT_READ_TIMEOUT',flush=True)
        except RuntimeError as exc:
            if not any(v in str(exc).lower() for v in ['timeout','timed out','unable to connect','unexpected eof','network is unreachable','connection refused','transport is closing']):raise
            print('TRANSIENT_ASSIGNMENT_READ_NETWORK',flush=True)
        artifact=parse((JOBS/REPLAY/'worker.log').read_text(),'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT') if (JOBS/REPLAY/'worker.log').exists() else None
        if artifact is not None:
            for name,text in artifact.items():
                path=dest/'runs'/name;assert path.resolve().is_relative_to((dest/'runs').resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            collected=True
        state.pop('log_tail',None);save(dest/'monitor-private.json',state)
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        if state['status'] in ['SUCCEEDED','FAILED']:
            if state['status']=='SUCCEEDED':assert collected
            cleanup(REPLAY)
            assert state['status']=='SUCCEEDED','Replay failed; preserve original checkpoint and all partial results, no resubmission'
            break
        time.sleep(30)
    else:raise TimeoutError('Finite one replay deadline; no resubmission')
    adopt_collected_replay()

def adopt_collected_replay():
    dest=RESCUE/'evaluation-replay';original=RESCUE/'original'
    receipt=json.loads((original/'reasoning/receipt.json').read_text());old=json.loads((JOBS/ORIGINAL/'host.json').read_text())
    execution=json.loads((dest/'runs/execution-receipt.json').read_text());assert execution['status']=='COMPLETE' and execution['training_updates']==0
    canonical=STAGE/'runs/A2'
    for name in ['receipt.json','trace.json']:
        path=canonical/'reasoning'/name;path.parent.mkdir(exist_ok=True)
        assert not path.exists();path.write_bytes((original/'reasoning'/name).read_bytes())
    assert not (canonical/'reasoning-predictions.json').exists()
    (canonical/'reasoning-predictions.json').write_bytes((dest/'runs/reasoning-predictions.json').read_bytes())
    launch=json.loads((canonical/'launch-freeze-private.json').read_text());newhost=json.loads((JOBS/REPLAY/'host.json').read_text())
    derived={'status':'COMPLETE','derived_not_emitted_by_original_worker':True,
        'completion_kind':'ORIGINAL_TRAINING_PLUS_ZERO_UPDATE_FULL_EVALUATION_REPLAY','original_job_status':'FAILED',
        'worker_sha256':launch['config']['worker_sha256'],'bundle_sha256':launch['config']['bundle_sha256'],
        'evaluation_replay_job_uid':newhost['uid'],'evaluation_replay_execution_sha256':sha(dest/'runs/execution-receipt.json'),
        'official_TEST_queries':0,'confirmation_queries':0,'new_optimizer_updates_in_recovery':0}
    save(canonical/'execution-receipt.json',derived)
    from audit_kali_curriculum_a2_eviction_replay_20261118 import audit
    audited=audit();save(RESCUE/'replay-audit-private.json',audited)
    from score_kali_curriculum_sft_20261117 import score_predictions,grade
    base=score_predictions(STAGE/'runs/pair/base-predictions.json');result=score_predictions(canonical/'reasoning-predictions.json')
    save(canonical/'score-private.json',{'grade':grade(result,base),'details':result})
    pointer={'schema':'kali.verified-teacher.v1','candidate_id':'A2','model_id':'Qwen/Qwen3-8B',
        'model_revision':receipt['model_revision'],'adapter_sha256':receipt['adapter_sha256'],'optimizer_steps':32,'protocol_sha256':sha(STAGE/'evaluation-protocol.json')}
    save(canonical/'adapter-pointer-private.json',{'pointer':pointer,'cache_adapter':launch['config']['durable_output']+'/reasoning/adapter'})
    lease=json.loads((STAGE/'existing-A2-backend-lease-private.json').read_text())
    save(canonical/'existing-backend-recovery-private.json',{'status':'ORIGINAL_NATIVE_DISPATCHED_CANDIDATE_COLLECTED',
        'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_native_dispatch_run_id':lease['native_dispatch_run_id'],
        'job_uid':old['uid'],'new_optimizer_updates_in_recovery':0,'native_run_completion_claimed':False,
        'adapter_pointer':pointer,'evaluation_replay_after_node_eviction':True,'original_job_stays_failed':True,
        'evaluation_replay_audit_sha256':sha(RESCUE/'replay-audit-private.json')})
    print('ORIGINAL_A2_AND_ZERO_UPDATE_EVALUATION_REPLAY_VERIFIED',flush=True)

if __name__=='__main__':main()
