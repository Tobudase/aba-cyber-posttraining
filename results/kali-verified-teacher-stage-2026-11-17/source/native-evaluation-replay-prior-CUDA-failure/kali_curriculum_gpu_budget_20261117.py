"""Conservative single-study GPU allocation ledger from original host receipts.

Count even earlier same-day pilots. For assigned Pods, use submission time
(including queue) through recorded termination/authorized cleanup, rather than
pretending inference-only seconds are the full allocation cost.
"""
import datetime
import json
from pathlib import Path

from kali_execution_jobs_20261114 import OUT as JOBS
from prepare_kali_verified_curriculum_20261117 import OUT, save

LIMIT_SECONDS = 24*3600


def timestamp(value):
    return datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


def allocation_seconds(host,pod_loss_evidence=None):
    resources=host.get('resources',{})
    count=sum(int(v) for key,v in resources.items() if key.startswith('nvidia.com/'))
    if not count:return 0.
    assert count == 1, 'This stage authorizes a single GPU per Job'
    pods=host.get('pods',[])
    if not any(p.get('node') for p in pods):
        if pod_loss_evidence is not None:
            e=pod_loss_evidence
            assert e['status']=='ACTUAL_ASSIGNED_POD_LOST_AFTER_NODE_NOT_READY'
            assert e['job_uid']==host['uid'] and e['job']==host['job']
            assert e['observed_assigned_node'] and e['observed_running_responses']>=312
            assert set(e['observed_event_reasons'])>={'NodeNotReady','TaintManagerEviction'}
            assert host['status']=='FAILED' and host['resources_cleaned'] and host['aborted_at']
            elapsed=timestamp(host['aborted_at'])-timestamp(host['submitted_at_utc'])
            assert elapsed>0
            return elapsed
        assert host.get('resources_cleaned'), 'Unassigned Job must have verified cleanup'
        assert host.get('status') in ['CANCELLED_BEFORE_SCHEDULING','REPLACED_UNSCHEDULED_RESOURCE_FIT',
            'REPLACED_UNSCHEDULED_APPROVED_A100','REPLACED_UNSCHEDULED_CPU_MEMORY_FIT'], 'No completed allocation evidence'
        return 0.
    start=timestamp(host['submitted_at_utc'])
    ended=[]
    for pod in pods:
        for c in pod.get('containers',[]):
            end=c.get('state',{}).get('terminated',{}).get('finishedAt')
            if end:ended.append(timestamp(end))
    if host.get('resources_cleaned') and host.get('aborted_at'):
        ended.append(timestamp(host['aborted_at']))
    assert ended and host.get('resources_cleaned'), 'A GPU allocation has no verified termination/cleanup'
    assert max(ended)>=start
    return max(ended)-start


def ledger(prospective_seconds=0):
    rows=[]
    for path in sorted(JOBS.glob('miw113-kali-*-1117*/host.json')):
        host=json.loads(path.read_text())
        if not any(k.startswith('nvidia.com/') for k in host.get('resources',{})):continue
        lost=path.parent/'pod-loss-allocation-evidence-private.json'
        seconds=allocation_seconds(host,json.loads(lost.read_text()) if lost.exists() else None)
        rows.append({'job':host['job'],'job_uid':host['uid'],'conservative_gpu_seconds':seconds,
                     'source_host_sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest()})
    used=sum(r['conservative_gpu_seconds'] for r in rows)
    assert used+prospective_seconds<=LIMIT_SECONDS, '24 GPU-hour stop budget would be exceeded'
    result={'status':'CONSERVATIVE_24_GPU_HOUR_BUDGET_CHECK_PASSED',
        'method':'Assigned Job submission-to-recorded-termination/cleanup; includes queue as a conservative upper bound and earlier same-day pilots.',
        'conservative_consumed_gpu_seconds':used,'prospective_maximum_gpu_seconds':prospective_seconds,
        'remaining_after_prospective_gpu_seconds':LIMIT_SECONDS-used-prospective_seconds,
        'stop_budget_gpu_seconds':LIMIT_SECONDS,'private_jobs':rows}
    save(OUT/'paired-sft/gpu-budget-before-confirmation-private.json' if prospective_seconds else OUT/'paired-sft/gpu-budget-final-private.json',result)
    return result


if __name__=='__main__':
    result=ledger()
    print(json.dumps({k:v for k,v in result.items() if k!='private_jobs'},indent=2))
