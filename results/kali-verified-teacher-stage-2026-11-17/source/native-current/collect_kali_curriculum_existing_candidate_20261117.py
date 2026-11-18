"""Collect one existing native-dispatched Job after explicit ownership transfer.

Never submits training or changes a failed native journal to success. This is
only a bounded collector for the original, already-trained adapter and its
unchanged evaluation. The original native run remains separately auditable.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from audit_kali_curriculum_complete_20261117 import validate_predictions, validate_training
from kali_curriculum_sft_jobs_20261117 import STAGE, name_for
from kali_execution_jobs_20261114 import OUT as JOBS, k, poll, cleanup
from kali_framed_artifacts_20261117 import parse
from prepare_kali_verified_curriculum_20261117 import save, sha


def validate_identity(lease, actual, host, launch):
    assert lease['status'] == 'EXPLICIT_EXISTING_BACKEND_OWNERSHIP_TRANSFER'
    assert lease['candidate_id'] in ['A1', 'A2']
    assert actual['metadata']['name'] == name_for(lease['candidate_id'])
    assert actual['metadata']['uid'] == host['uid'] == lease['job_uid']
    assert actual['metadata']['labels']['app.kubernetes.io/managed-by'] == 'miw113'
    assert launch['config']['candidate'] == lease['candidate_id']
    assert launch['config']['learning_rate'] == lease['learning_rate']
    assert launch['config']['worker_sha256'] == lease['worker_sha256']
    assert launch['config']['bundle_sha256'] == lease['bundle_sha256']
    assert lease['native_dispatch_run_id'] and lease['new_optimizer_updates_in_recovery'] == 0


def assert_original_driver_stopped(pid):
    assert isinstance(pid, int) and pid > 1 and pid != os.getpid()
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'stat=,command='], capture_output=True, text=True, check=False)
    assert result.returncode == 1 or (result.returncode == 0 and result.stdout.strip().startswith('Z')), 'Original collector still active; no concurrent takeover'


def complete_existing(lease_path,lease,launch,*,cleanup_job):
    cid=lease['candidate_id'];name=name_for(cid);dest=STAGE/'runs'/cid
    execution=json.loads((dest/'execution-receipt.json').read_text())
    assert execution['status']=='COMPLETE'
    assert execution['worker_sha256']==lease['worker_sha256'] and execution['bundle_sha256']==lease['bundle_sha256']
    assert execution['official_TEST_queries']==execution['confirmation_queries']==0
    data=json.loads((STAGE/'paired-training-private.json').read_text());data['protocol']['learning_rate']=lease['learning_rate']
    expected=hashlib.sha256((json.dumps(data)+'\n').encode()).hexdigest()
    receipt=json.loads((dest/'reasoning/receipt.json').read_text());trace=json.loads((dest/'reasoning/trace.json').read_text())
    training=validate_training(data,'reasoning',receipt,trace,expected,lease['learning_rate'])
    assert receipt['initial_adapter_sha256']==json.loads((STAGE/'runs/pair/reasoning/receipt.json').read_text())['initial_adapter_sha256']
    evaluation=validate_predictions(json.loads((dest/'reasoning-predictions.json').read_text()),
        json.loads((STAGE/'evaluation-inputs-private.json').read_text()),json.loads((STAGE/'evaluation-protocol.json').read_text()),receipt['adapter_sha256'])
    pointer={'schema':'kali.verified-teacher.v1','candidate_id':cid,'model_id':'Qwen/Qwen3-8B',
        'model_revision':receipt['model_revision'],'adapter_sha256':receipt['adapter_sha256'],
        'optimizer_steps':receipt['updates'],'protocol_sha256':sha(STAGE/'evaluation-protocol.json')}
    pointer_record={'pointer':pointer,'cache_adapter':launch['config']['durable_output']+'/reasoning/adapter'}
    if (dest/'adapter-pointer-private.json').exists():assert json.loads((dest/'adapter-pointer-private.json').read_text())==pointer_record
    else:save(dest/'adapter-pointer-private.json',pointer_record)
    from score_kali_curriculum_sft_20261117 import score_predictions,grade
    base=score_predictions(STAGE/'runs/pair/base-predictions.json');result=score_predictions(dest/'reasoning-predictions.json')
    score={'grade':grade(result,base),'details':result}
    if (dest/'score-private.json').exists():assert json.loads((dest/'score-private.json').read_text())==score
    else:save(dest/'score-private.json',score)
    if cleanup_job:cleanup(name)
    host=json.loads((JOBS/name/'host.json').read_text())
    assert host['uid']==lease['job_uid'] and host['resources_cleaned'] and host['status']=='SUCCEEDED'
    save(dest/'existing-backend-recovery-private.json',{'status':'ORIGINAL_NATIVE_DISPATCHED_CANDIDATE_COLLECTED',
        'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'lease_sha256':sha(lease_path),
        'original_native_dispatch_run_id':lease['native_dispatch_run_id'],'job_uid':lease['job_uid'],
        'training':training,'evaluation':evaluation,'new_optimizer_updates_in_recovery':0,
        'native_run_completion_claimed':False,'adapter_pointer':pointer,
        'already_collected_and_cleaned_before_takeover':not cleanup_job})
    print('ORIGINAL_NATIVE_DISPATCHED_CANDIDATE_COLLECTED '+cid,flush=True)


def collect(lease_path):
    lease_path = Path(lease_path)
    lease = json.loads(lease_path.read_text())
    assert_original_driver_stopped(lease['previous_host_driver_pid'])
    cid = lease['candidate_id']; name = name_for(cid); dest = STAGE/'runs'/cid
    launch = json.loads((dest/'launch-freeze-private.json').read_text())
    host = json.loads((JOBS/name/'host.json').read_text())
    assert host['uid']==lease['job_uid'] and launch['config']['candidate']==cid
    assert launch['config']['worker_sha256']==lease['worker_sha256'] and launch['config']['bundle_sha256']==lease['bundle_sha256']
    if host.get('resources_cleaned'):
        assert host['status']=='SUCCEEDED','Do not adopt failed work as completed'
        artifact=parse((JOBS/name/'worker.log').read_text(),'CURRICULUM_SFT_ARTIFACT')
        assert artifact is not None
        for filename,raw in artifact.items():
            path=dest/filename;assert not Path(filename).is_absolute() and path.resolve().is_relative_to(dest.resolve())
            assert path.read_text()==raw,'Saved canonical artifact differs from the actual original GPU frame'
        complete_existing(lease_path,lease,launch,cleanup_job=False)
        return
    actual = json.loads(k('get', 'job', name, '-o', 'json').stdout)
    validate_identity(lease, actual, host, launch)
    import fcntl
    with (dest/'recovery-collector-private.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started=actual.get('status',{}).get('startTime') or actual['metadata']['creationTimestamp']
        original_deadline=datetime.datetime.fromisoformat(started.replace('Z','+00:00')).timestamp()+actual['spec']['activeDeadlineSeconds']
        until=time.monotonic()+min(16200,max(60,original_deadline-time.time()+300))
        collected = False
        while time.monotonic() < until:
            assert_original_driver_stopped(lease['previous_host_driver_pid'])
            try:state=poll(name)
            except subprocess.TimeoutExpired:
                print('TRANSIENT_EXISTING_JOB_READ_TIMEOUT_NO_RESUBMIT',flush=True);time.sleep(15);continue
            except RuntimeError as exc:
                message=str(exc).lower()
                if any(s in message for s in ['unable to connect','timed out','timeout','network is unreachable','no route','connection refused','context deadline','unexpected eof','transport is closing']):
                    print('TRANSIENT_EXISTING_JOB_NETWORK_NO_RESUBMIT',flush=True);time.sleep(15);continue
                raise
            artifact = parse((JOBS/name/'worker.log').read_text(), 'CURRICULUM_SFT_ARTIFACT') if (JOBS/name/'worker.log').exists() else None
            if artifact is not None:
                for filename, raw in artifact.items():
                    p = dest/filename
                    assert not Path(filename).is_absolute() and p.resolve().is_relative_to(dest.resolve())
                    p.parent.mkdir(parents=True, exist_ok=True)
                    if p.exists(): assert p.read_text() == raw, 'Never overwrite divergent evidence'
                    else: p.write_text(raw)
                collected = True
            state.pop('log_tail', None)
            save(dest/'recovery-monitor-private.json', state)
            if state['status'] in ['SUCCEEDED', 'FAILED']:
                if state['status'] == 'FAILED':
                    save(dest/'recovery-failure-private.json', {'status': 'ORIGINAL_JOB_FAILED_NOT_RETRAINED', 'job_uid': lease['job_uid']})
                    raise RuntimeError('Original Job failed; partials and logs preserved')
                assert collected, 'Never clean a successful Job without actual framed artifacts'
                complete_existing(lease_path,lease,launch,cleanup_job=True)
                return
            time.sleep(30)
        raise TimeoutError('Finite collector timeout; no duplicate training submission')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('lease',type=Path);collect(p.parse_args().lease)
