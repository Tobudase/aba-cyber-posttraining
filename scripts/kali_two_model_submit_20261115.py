"""Dedicated two-model pilot submitter with explicit bounded concurrency.

Derived from the existing bounded Job submitter. All server-side dry runs,
requests=limits, node restrictions, deadlines and cleanup metadata are retained.
Only the local conservation rule differs: one existing independent one-GPU study
may coexist with this one-GPU pilot (maximum two owned GPUs requested in total).
It never changes namespace quotas, priority, taints, tolerations or other Jobs.
"""
import datetime,json
from kali_execution_jobs_20261114 import ROOT,OUT,k,write
def submit_pilot(name,files,resources,command=None,cache=False,readonly=True,gpu_products=None,runtime=1800,binary_files=None,node_names=None,cache_claim='miw113-kali-cuda-cache',cache_region='us-west',preferred_node_names=None,extra_volumes=None,extra_mounts=None):
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
        owned=[x for x in active if x.get('status',{}).get('phase') in ['Pending','Running']]
        existing=sum(int(v) for x in owned for c in x['spec']['containers'] for key,v in c.get('resources',{}).get('requests',{}).items() if key.startswith('nvidia.com/'))
        assert existing<=1,'Pilot allows at most two total owned requested GPUs across independent studies'
        assert not any(x['metadata'].get('labels',{}).get('job-name')==name for x in owned),'Duplicate current pilot allocation'
        pod['affinity']={'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'nvidia.com/gpu.product','operator':'In','values':gpu_products}]}]}}}
    if node_names:
        if not gpu_products:
            pod['affinity']={'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':[]}]}}}
        pod['affinity']['nodeAffinity']['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'][0]['matchExpressions'].append({'key':'kubernetes.io/hostname','operator':'In','values':node_names})
    if preferred_node_names:
        pod.setdefault('affinity',{}).setdefault('nodeAffinity',{})['preferredDuringSchedulingIgnoredDuringExecution']=[{'weight':100,'preference':{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':preferred_node_names}]}}]
    if extra_volumes:
        assert all(v.get('persistentVolumeClaim',{}).get('claimName','').startswith('miw113-kali-two-model') for v in extra_volumes)
        pod['volumes'].extend(extra_volumes)
        pod['containers'][0]['volumeMounts'].extend(extra_mounts or [])
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
