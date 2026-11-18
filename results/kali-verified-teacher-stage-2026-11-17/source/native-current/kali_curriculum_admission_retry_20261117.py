"""Retry transient admission transport failures without bypassing policy or duplicating Jobs."""
import contextlib
import datetime
import json
import subprocess
import time


def subset(expected, actual, path=()):
    if isinstance(expected, dict):
        if not isinstance(actual,dict):return False
        for key,value in expected.items():
            if key not in actual:
                # Kubernetes omits default-false mount fields on round-trip.
                # Never generalize this to security-sensitive defaults such as
                # automountServiceAccountToken (whose omitted default is true).
                default_false_mount=(key=='readOnly' and value is False and
                                     ('volumeMounts' in path or path[-1:] == ('persistentVolumeClaim',)))
                if not default_false_mount:return False
            elif not subset(value,actual[key],path+(key,)):return False
        return True
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected)==len(actual) and all(subset(e,a,path+(i,)) for i,(e,a) in enumerate(zip(expected,actual)))
    return expected == actual


def transient(error):
    return 'failed calling webhook' in error.lower() and any(x in error.lower() for x in [
        'failed to call webhook', 'context deadline exceeded', 'no endpoints available',
        'connection refused', 'i/o timeout', 'service unavailable'])


def create(call, args, body, *, check=True, sleep=time.sleep, record=lambda x:None, attempts=5):
    assert args[0]=='create' and body and body['kind'] in ['ConfigMap','Job']
    dry='--dry-run=server' in args
    last=None
    for attempt in range(attempts):
        timed_out=False
        try:
            result=call(*args,body=body,check=False)
            if result.returncode==0:return result
            last=result.stderr
        except subprocess.TimeoutExpired:
            timed_out=True;last='create subprocess timed out; reconcile before any retry'
        if not timed_out and not transient(last):
            if check:raise RuntimeError(last[-1200:])
            return result
        record({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'attempt':attempt+1,'kind':body['kind'],'name':body['metadata']['name'],
                'server_dry_run':dry,'error':last[-1000:]})
        if not dry:
            # A lost acknowledgement may still have created the original object.
            found=call('get',body['kind'].lower(),body['metadata']['name'],'-o','json',check=False)
            if found.returncode==0:
                obj=json.loads(found.stdout)
                assert obj['metadata'].get('labels',{}).get('app.kubernetes.io/managed-by')=='miw113'
                assert subset(body,obj), 'Existing object differs from the frozen request; never adopt/overwrite'
                return subprocess.CompletedProcess(args,0,found.stdout,'')
            assert 'NotFound' in found.stderr, 'Create outcome unknown; do not repeat mutation'
        if attempt+1<attempts:sleep([5,15,30,60][min(attempt,3)])
    raise RuntimeError('Finite admission retry exhausted; no duplicate resubmission: '+str(last)[-600:])


@contextlib.contextmanager
def admission_retry(name, destination):
    # Only one backend submission per process; never alters the study payload.
    import kali_execution_jobs_20261114 as jobs
    original=jobs.k;events=[]
    def record(event):
        events.append(event)
        (destination/'admission-retry-private.json').write_text(json.dumps({'job':name,'events':events,'bypass_policy':False},indent=2)+'\n')
    def wrapped(*args,body=None,check=True):
        if args and args[0]=='create':return create(original,args,body,check=check,record=record)
        return original(*args,body=body,check=check)
    jobs.k=wrapped
    try:yield
    finally:jobs.k=original
