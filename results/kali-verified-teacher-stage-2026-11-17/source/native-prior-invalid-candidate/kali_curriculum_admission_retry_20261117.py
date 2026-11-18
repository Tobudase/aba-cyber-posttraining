"""Retry transient admission transport failures without bypassing policy or duplicating Jobs."""
import contextlib
import datetime
import json
import subprocess
import time


def subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k,v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected)==len(actual) and all(subset(e,a) for e,a in zip(expected,actual))
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
