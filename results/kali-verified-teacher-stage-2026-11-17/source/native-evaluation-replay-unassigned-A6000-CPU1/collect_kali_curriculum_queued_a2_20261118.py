"""Collect the SAME finite A2 replay Job; never submit or retrain anything.

Record server Pod snapshots while unscheduled. Use the request-start time of
the last observed unassigned snapshot minus60seconds as a conservative bound
on this same Pod's API node allocation. Earlier failed costs remain unchanged.
"""
import datetime,hashlib,json,os,subprocess,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT as JOBS,k,poll,cleanup
from prepare_kali_verified_curriculum_20261117 import save,sha
from audit_kali_curriculum_a2_eviction_replay_20261118 import REPLAY,RESCUE,STAGE
from kali_framed_artifacts_20261117 import parse
from collect_kali_curriculum_existing_candidate_20261117 import assert_original_driver_stopped

DEST=RESCUE/'evaluation-replay';LEASE=RESCUE/'queue-only-handoff-private.json'

def observe_assignment(lease):
    began=datetime.datetime.now(datetime.timezone.utc).isoformat()
    items=json.loads(k('get','pods','-l','job-name='+REPLAY,'-o','json').stdout)['items']
    assert len(items)==1,'No unique actual Pod; do not invent allocation evidence'
    pod=items[0];assert pod['metadata']['uid']==lease['pod_uid']
    assert any(o.get('kind')=='Job' and o.get('uid')==lease['job_uid'] for o in pod['metadata']['ownerReferences'])
    path=JOBS/REPLAY/'gpu-allocation-start-bound-private.json'
    prior=json.loads(path.read_text()) if path.exists() else None
    if pod['spec'].get('nodeName'):
        if prior is None:return  # Immediate scheduling: keep full submission-time upper bound.
        if prior and prior.get('status')=='SAME_POD_API_NODE_ASSIGNMENT_BOUNDED':return
        assert prior and prior['status']=='LAST_OBSERVED_UNASSIGNED_SAME_POD'
        prior.update(status='SAME_POD_API_NODE_ASSIGNMENT_BOUNDED',first_observed_assigned_pod=pod,
            first_assignment_observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        assert pod['spec']['nodeName']!='hcc-prp-c5038.unl.edu';save(path,prior)
    else:
        assert pod['status']['phase']=='Pending'
        assert not prior or prior['status']!='SAME_POD_API_NODE_ASSIGNMENT_BOUNDED','Never reset an assigned allocation to pending'
        record={'status':'LAST_OBSERVED_UNASSIGNED_SAME_POD','job_uid':lease['job_uid'],
            'last_unassigned_request_started_at_utc':began,'last_observed_unassigned_pod':pod,
            'request_completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'counting_scope':'API node assignment, not undocumented internal scheduler reservation or exact physical GPU usage',
            'extra_conservative_seconds':60}
        save(path,record)
        with (JOBS/REPLAY/'unassigned-observation-history-private.jsonl').open('a') as f:
            f.write(json.dumps({'request_started_at_utc':began,'pod_uid':pod['metadata']['uid'],
                'resourceVersion':pod['metadata']['resourceVersion'],'nodeName':None,'snapshot_sha256':sha(path)})+'\n')

def main():
    lease=json.loads(LEASE.read_text());assert lease['status']=='SAME_UNASSIGNED_JOB_QUEUE_WINDOW_AMENDED_NO_GPU_RUNTIME_CHANGE'
    assert_original_driver_stopped(lease['old_collector_pid'])
    job=json.loads(k('get','job',REPLAY,'-o','json').stdout)
    assert job['metadata']['uid']==lease['job_uid'] and job['spec']['activeDeadlineSeconds']==21600
    assert job['spec']['template']['spec']['activeDeadlineSeconds']==10800
    launch=json.loads((DEST/'launch-freeze-private.json').read_text())
    assert launch['config']['worker_sha256']==lease['worker_sha256'] and launch['config']['bundle_sha256']==lease['bundle_sha256']
    import fcntl
    with (DEST/'queue-collector-private.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        snapshots=DEST/'queue-collector-runtime-source-private';assert not snapshots.exists();snapshots.mkdir()
        names=['collect_kali_curriculum_queued_a2_20261118.py','run_kali_curriculum_a2_eval_replay_20261118.py',
            'audit_kali_curriculum_a2_eviction_replay_20261118.py','kali_curriculum_gpu_budget_20261117.py']
        for name in names:(snapshots/name).write_bytes((ROOT/'scripts'/name).read_bytes())
        save(DEST/'queue-collector-source-freeze-private.json',{name:sha(snapshots/name) for name in names})
        subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=datetime.datetime.fromisoformat(job['metadata']['creationTimestamp'].replace('Z','+00:00')).timestamp()+21600
        until=time.monotonic()+max(60,deadline-time.time()+300);collected=False;previous=None
        while time.monotonic()<until:
            try:
                observe_assignment(lease);state=poll(REPLAY)
            except subprocess.TimeoutExpired:
                print('TRANSIENT_EXISTING_REPLAY_READ_TIMEOUT',flush=True);time.sleep(20);continue
            except RuntimeError as exc:
                if not any(x in str(exc).lower() for x in ['timed out','timeout','unable to connect','network is unreachable','connection refused','no route','unexpected eof','context deadline','transport is closing']):raise
                print('TRANSIENT_EXISTING_REPLAY_READ_NETWORK',flush=True);time.sleep(20);continue
            log=JOBS/REPLAY/'worker.log';artifact=parse(log.read_text(),'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT') if log.exists() else None
            if artifact is not None:
                for name,text in artifact.items():
                    path=DEST/'runs'/name;assert path.resolve().is_relative_to((DEST/'runs').resolve());path.parent.mkdir(parents=True,exist_ok=True)
                    if path.exists():assert path.read_text()==text
                    else:path.write_text(text)
                collected=True
            state.pop('log_tail',None);save(DEST/'monitor-private.json',state)
            if state!=previous:print(json.dumps(state),flush=True);previous=state
            if state['status'] in ['SUCCEEDED','FAILED']:
                if state['status']=='SUCCEEDED':assert collected
                cleanup(REPLAY)
                assert state['status']=='SUCCEEDED','Same replay Job failed; preserve actual evidence and do not resubmit'
                from run_kali_curriculum_a2_eval_replay_20261118 import adopt_collected_replay
                adopt_collected_replay();return
            time.sleep(30)
        raise TimeoutError('Finite same-Job queue/collection deadline exhausted; no duplicate Job')

if __name__=='__main__':main()
