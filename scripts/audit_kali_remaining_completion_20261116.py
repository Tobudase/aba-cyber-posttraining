"""Verify bounded-study completion, exported weights, and owned-object cleanup."""
import datetime
import hashlib
import json
from pathlib import Path
from kali_execution_jobs_20261114 import OUT, ROOT, k

names = [
    'miw113-kali-objective-v11-1116', 'miw113-kali-objective-v11-r2-1116',
    *['miw113-kali-cf-'+p+'-v11-1116' for p in ['teacher','early','fit','primary','shifted']],
    'miw113-kali-path-v12-1116', 'miw113-kali-path-grade-v12-1116',
    'miw113-kali-retention-v13-1116',
    *['miw113-kali-cf-'+p+'-v13-1116' for p in ['early','fit','primary','shifted']],
]
rows = []
for name in names:
    d = OUT/name
    h = json.loads((d/'host.json').read_text())
    assert h.get('resources_cleaned'), name
    assert h['status'] == ('FAILED' if name == 'miw113-kali-objective-v11-1116' else 'SUCCEEDED'), name
    objects = json.loads((d/'objects.json').read_text())
    job = objects[1]
    pod = job['spec']['template']['spec']
    resource = pod['containers'][0]['resources']
    assert resource['requests'] == resource['limits']
    assert job['spec']['backoffLimit'] == 0 and 0 < pod['activeDeadlineSeconds'] <= 10800
    assert pod['automountServiceAccountToken'] is False
    assert not pod.get('hostNetwork') and not pod.get('hostPID') and not pod.get('tolerations')
    assert all(not c.get('securityContext',{}).get('privileged') for c in pod['containers'])
    term = h['pods'][0]['containers'][0]['state']['terminated']
    if h['gpu']:
        assert resource['requests']['nvidia.com/gpu'] == '1'
    rows.append({'job':name,'uid':h['uid'],'status':h['status'],'GPU_requested':int(h['gpu']),
                 'resources_cleaned':True,'container_started_at':term['startedAt'],
                 'container_finished_at':term['finishedAt'],'activeDeadlineSeconds':pod['activeDeadlineSeconds'],
                 'host_receipt_sha256':hashlib.sha256((d/'host.json').read_bytes()).hexdigest()})
# Only inspect the named study objects. Never fetch other users' ConfigMap contents.
for kind in ['job','configmap','networkpolicy']:
    assert not k('get',kind,*names,'--ignore-not-found','-o','name').stdout.strip(), kind+' remains'
pods = json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
owned_pods = [p['metadata']['name'] for p in pods if p['metadata'].get('labels',{}).get('job-name') in names]
assert not owned_pods
parse = lambda x: datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
gpu = sorted([r for r in rows if r['GPU_requested']], key=lambda r:r['container_started_at'])
assert all(parse(a['container_finished_at']) <= parse(b['container_started_at']) for a,b in zip(gpu,gpu[1:])), 'GPU containers overlapped'
exports = {}
for name in ['miw113-kali-objective-v11-r2-1116','miw113-kali-retention-v13-1116']:
    d = OUT/name
    e = json.loads((d/'export-audit.json').read_text())
    assert hashlib.sha256((d/'experimental-adapters.tar.gz').read_bytes()).hexdigest() == e['archive_sha256']
    verified = {}
    for label, record in e['checkpoints'].items():
        path = d/'experimental-adapters'/record['adapter_relative_path']
        for filename, field in [('adapter_model.safetensors','weights_sha256'),('adapter_config.json','config_sha256')]:
            assert hashlib.sha256((path/filename).read_bytes()).hexdigest() == record[field]
        verified[label] = record['weights_sha256']
    exports[name] = {'archive_sha256':e['archive_sha256'],'reverified_weight_sha256':verified}
value = {'status':'ALL_NAMED_STUDIES_TERMINAL_AND_CLEANED','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'exports_reverified_from_local_bytes':exports,'jobs':rows,'named_jobs':len(rows),'GPU_containers_sequential':True,
         'container_wall_GPU_seconds':sum((parse(r['container_finished_at'])-parse(r['container_started_at'])).total_seconds() for r in gpu),
         'cost_scope':'Container wall time, including load/inference/waits and the zero-update failed attempt; not billed GPU time or pure training time.',
         'scope':'Only v11/v12/v13 owned objects; persistent data caches retained and other namespace users untouched.'}
(OUT/'remaining-experiments-resource-audit-20261116.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value,indent=2))
