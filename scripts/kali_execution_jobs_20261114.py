"""Bounded submit/poll/collect for the authorized Nov 14 experiment execution.

No automatic resubmission; failed attempts and their persistent outputs survive.
"""
import argparse, datetime, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=['/opt/homebrew/bin/kubectl','--context=nautilus','-n','ecepxie','--request-timeout=30s']
OUT=ROOT/'data/benchkit/kali-execution-2026-11-14'
def k(*args,body=None,check=True):
    p=subprocess.run(BASE+list(args),input=json.dumps(body) if body is not None else None,capture_output=True,text=True,timeout=50)
    if check and p.returncode:raise RuntimeError(p.stderr[-1200:])
    return p
def write(p,obj):
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(obj,indent=2)+'\n');temp.replace(p)
def submit(name,files,resources,command=None,cache=False,readonly=True,gpu_products=None,runtime=1800,binary_files=None,node_names=None,cache_claim='miw113-kali-cuda-cache',cache_region='us-west',preferred_node_names=None):
    d=OUT/name;d.mkdir(exist_ok=False)
    labels={'app.kubernetes.io/managed-by':'miw113','app.kubernetes.io/part-of':'kali-execution-20261114'}
    cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'labels':labels},'data':files}
    if binary_files:
        import base64
        assert not set(binary_files)&set(files)
        cm['binaryData']={key:base64.b64encode(value).decode() for key,value in binary_files.items()}
    pod={'restartPolicy':'Never','activeDeadlineSeconds':runtime,'automountServiceAccountToken':False,
         'nodeSelector':{'kubernetes.io/arch':'amd64'},
         'containers':[{'name':'worker','image':json.loads((ROOT/'configs/gpu-runtime-image.lock.json').read_text())['image'],
          'command':command or ['python','-u','/input/worker.py'],
          'env':[{'name':'CUBLAS_WORKSPACE_CONFIG','value':':4096:8'},{'name':'PYTHONDONTWRITEBYTECODE','value':'1'},{'name':'OMP_NUM_THREADS','value':'2'}],
          'resources':{'requests':resources,'limits':resources},
          'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True},{'name':'scratch','mountPath':'/scratch'}]}],
         'volumes':[{'name':'input','configMap':{'name':name}},{'name':'scratch','emptyDir':{'sizeLimit':resources.get('ephemeral-storage','2Gi')}}]}
    if cache:
        pod['containers'][0]['volumeMounts'].append({'name':'cache','mountPath':'/cache','readOnly':readonly})
        pod['volumes'].append({'name':'cache','persistentVolumeClaim':{'claimName':cache_claim,'readOnly':readonly}})
        if cache_region:pod['nodeSelector']['topology.kubernetes.io/region']=cache_region
    if gpu_products:
        active=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
        assert not any(x.get('status',{}).get('phase') in ['Pending','Running'] and any(any(a.startswith('nvidia.com/') for a in c.get('resources',{}).get('requests',{})) for c in x['spec']['containers']) for x in active),'Existing owned GPU allocation'
        pod['affinity']={'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'nvidia.com/gpu.product','operator':'In','values':gpu_products}]}]}}}
    if node_names:
        if not gpu_products:
            pod['affinity']={'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':[]}]}}}
        pod['affinity']['nodeAffinity']['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'][0]['matchExpressions'].append({'key':'kubernetes.io/hostname','operator':'In','values':node_names})
    if preferred_node_names:
        pod.setdefault('affinity',{}).setdefault('nodeAffinity',{})['preferredDuringSchedulingIgnoredDuringExecution']=[{'weight':100,'preference':{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':preferred_node_names}]}}]
    job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'labels':labels},'spec':{'backoffLimit':0,'activeDeadlineSeconds':runtime+1800,'ttlSecondsAfterFinished':86400,'template':{'metadata':{'labels':labels},'spec':pod}}}
    write(d/'objects.json',[cm,job]);created=[]
    for obj in [cm,job]:k('create','--dry-run=server','-f','-',body=obj)
    try:
        for obj in [cm,job]:
            k('create','-f','-',body=obj);created.append(obj['kind'].lower())
    except Exception as e:
        write(d/'submission-error.json',{'error':str(e),'created':created});raise
    actual=json.loads(k('get','job',name,'-o','json').stdout)
    record={'status':'SUBMITTED','job':name,'uid':actual['metadata']['uid'],'submitted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu':any(x.startswith('nvidia.com/') for x in resources),'resources':resources}
    write(d/'host.json',record);return record
def poll(name):
    d=OUT/name;record=json.loads((d/'host.json').read_text());job=json.loads(k('get','job',name,'-o','json').stdout)
    assert job['metadata']['uid']==record['uid']
    pods=json.loads(k('get','pods','-l','job-name='+name,'-o','json').stdout)['items']
    record['job_status']=job.get('status',{});record['pods']=[{'name':x['metadata']['name'],'node':x['spec'].get('nodeName'),'phase':x.get('status',{}).get('phase'),'conditions':x.get('status',{}).get('conditions',[]),'containers':x.get('status',{}).get('containerStatuses',[])} for x in pods]
    done=bool(job.get('status',{}).get('succeeded') or job.get('status',{}).get('failed'))
    record['status']='SUCCEEDED' if job.get('status',{}).get('succeeded') else 'FAILED' if done else (pods[0].get('status',{}).get('phase','QUEUED') if pods else 'QUEUED')
    if pods and pods[0].get('status',{}).get('phase')!='Pending':
        logs=k('logs','job/'+name,check=False)
        if logs.returncode==0:
            (d/'worker.log').write_text(logs.stdout)
            visible=[line for line in logs.stdout.splitlines() if not line.startswith(('ARTIFACT_BASE64=','FIT64_PREDICTIONS=','FIT16_OUTPUT_','FIT16_TRAIN_RECEIPT_','FIT16_RECEIPT='))]
            record['log_tail']='\n'.join(visible[-12:])[-1800:]
    write(d/'host.json',record)
    return {'job':name,'status':record['status'],'node':pods[0]['spec'].get('nodeName') if pods else None,'log_tail':record.get('log_tail'),'pending_reason':[c.get('message') for x in pods for c in x.get('status',{}).get('conditions',[]) if c.get('type')=='PodScheduled' and c.get('status')=='False']}
def cleanup(name):
    d=OUT/name;r=json.loads((d/'host.json').read_text());assert r['status'] in ['SUCCEEDED','FAILED'] and (d/'worker.log').exists(),'Collect logs before cleanup'
    actual=json.loads(k('get','job',name,'-o','json').stdout);assert actual['metadata']['uid']==r['uid']
    for kind in ['job','configmap']:k('delete',kind,name,'--wait=true','--timeout=30s')
    r['resources_cleaned']=True;write(d/'host.json',r)
def snapshot(name):
    """Copy atomic diagnostic progress locally while the GPU is still running."""
    import base64,gzip,hashlib
    d=OUT/name;r=json.loads((d/'host.json').read_text());assert r['status']=='Running'
    objs=json.loads((d/'objects.json').read_text());config=objs[0]['data']['config.json'];cfg=json.loads(config)
    root=cfg['durable_output'];assert root.startswith('/cache/kali-execution-20261114/')
    actual=json.loads(k('get','job',name,'-o','json').stdout);assert actual['metadata']['uid']==r['uid']
    program="import base64,gzip,json;from pathlib import Path;p=Path("+repr(root)+");files={f.name:json.loads(f.read_text()) for f in p.glob('*.json') if f.name!='effective-config.json'};print(base64.b64encode(gzip.compress(json.dumps(files).encode())).decode())"
    packed=k('exec','job/'+name,'--','python','-c',program).stdout.strip()
    files=json.loads(gzip.decompress(base64.b64decode(packed,validate=True)));dest=d/'snapshots';dest.mkdir(exist_ok=True)
    for filename,value in files.items():
        assert Path(filename).name==filename
        if filename.startswith('progress-'):assert value['config_sha256']==hashlib.sha256(config.encode()).hexdigest()
        write(dest/filename,value)
    audit={'copied_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'job_uid':r['uid'],'files':{n:hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in files},'rows':{n:len(v['rows']) for n,v in files.items() if n.startswith('progress-')}}
    write(dest/'snapshot-audit.json',audit);return audit['rows']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['poll','cleanup','snapshot']);p.add_argument('name');a=p.parse_args()
    result={'poll':poll,'cleanup':cleanup,'snapshot':snapshot}[a.action](a.name);print(json.dumps(result,indent=2))
