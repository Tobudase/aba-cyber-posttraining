"""Reconcile exact saved resources after API timeout; never create a second Job."""
import datetime,json,time
from kali_execution_jobs_20261114 import OUT,k,write

def subset(expected,actual):
 if isinstance(expected,dict):return isinstance(actual,dict) and all(k in actual and subset(v,actual[k]) for k,v in expected.items())
 if isinstance(expected,list):return isinstance(actual,list) and len(expected)==len(actual) and all(subset(e,a) for e,a in zip(expected,actual))
 return expected==actual

def recover(name):
 d=OUT/name;assert not (d/'host.json').exists();objects=json.loads((d/'objects.json').read_text());assert [o['kind'] for o in objects]==['ConfigMap','Job'] and all(o['metadata']['name']==name for o in objects)
 for obj in objects:
  for attempt in range(5):
   result=k('get',obj['kind'].lower(),name,'-o','json',check=False)
   if result.returncode==0:
    actual=json.loads(result.stdout)
    if obj['kind']=='ConfigMap':assert actual['data']==obj['data'] and actual.get('binaryData',{})==obj.get('binaryData',{})
    else:
     expected=obj['spec']['template']['spec'];got=actual['spec']['template']['spec']
     for key in ['volumes','nodeSelector','affinity','activeDeadlineSeconds','automountServiceAccountToken']:assert subset(expected.get(key),got.get(key)),(key,'Saved Job differs')
     for key in ['image','command','env','resources','volumeMounts']:assert subset(expected['containers'][0][key],got['containers'][0][key]),key
    break
   if 'NotFound' not in result.stderr:
    print('SUBMISSION_RECONCILE_RETRY '+obj['kind']+' '+str(attempt),flush=True);time.sleep(5);continue
   dry=k('create','--dry-run=server','-f','-',body=obj,check=False)
   if dry.returncode:
    print('SERVER_DRYRUN_RETRY '+obj['kind']+' '+str(attempt),flush=True);time.sleep(5);continue
   result=k('create','-f','-',body=obj,check=False)
   if result.returncode and not any(x in result.stderr for x in ['AlreadyExists','Timeout','deadline exceeded']):raise RuntimeError(result.stderr[-500:])
  else:raise TimeoutError('Cannot reconcile saved '+obj['kind'])
 actual=json.loads(k('get','job',name,'-o','json').stdout);resources=actual['spec']['template']['spec']['containers'][0]['resources']['requests'];r={'status':'SUBMITTED','job':name,'uid':actual['metadata']['uid'],'submitted_at_utc':actual['metadata']['creationTimestamp'],'gpu':any(x.startswith('nvidia.com/') for x in resources),'resources':resources,'API_reconciliation':True};write(d/'host.json',r);return r
