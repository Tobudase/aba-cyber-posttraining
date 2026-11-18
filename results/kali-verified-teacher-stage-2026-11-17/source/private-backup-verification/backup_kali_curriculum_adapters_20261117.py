"""Verify existing local backups, or use one finite CPU-only transfer Pod."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time
from prepare_kali_verified_curriculum_20261117 import ROOT, OUT, save, sha
from kali_execution_jobs_20261114 import k, BASE, gpu_cache_conflicts

STAGE = OUT/'paired-sft'
NAME = 'miw113-kali-cur-adapter-export-1117'
WORKER = r'''
import hashlib,http.server,io,json,re,tarfile
from pathlib import Path
cfg=json.loads(Path('/input/config.json').read_text());archive=Path('/scratch/adapters.tar.gz');manifest={}
with tarfile.open(archive,'w:gz') as out:
 for state in cfg['states']:
  root=Path(state['cache_adapter']);assert re.fullmatch(r'/cache/kali-execution-20261114/miw113-kali-curriculum-sft-(?:pair-r2|a1|a2)-1117/(?:answer_only|reasoning)/adapter',str(root))
  for name,path in [('adapter/adapter_model.safetensors',root/'adapter_model.safetensors'),('adapter/adapter_config.json',root/'adapter_config.json'),('receipt.json',root.parent/'receipt.json')]:
   assert path.is_file() and not path.is_symlink();raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();label=state['label']+'/'+name
   if name.endswith('.safetensors'):assert digest==state['adapter_sha256']
   manifest[label]={'bytes':len(raw),'sha256':digest};info=tarfile.TarInfo(label);info.size=len(raw);info.mode=0o600;out.addfile(info,io.BytesIO(raw))
 raw=json.dumps({'files':manifest,'model_weights_public':False},indent=2).encode();info=tarfile.TarInfo('manifest-private.json');info.size=len(raw);info.mode=0o600;out.addfile(info,io.BytesIO(raw))
digest=hashlib.sha256(archive.read_bytes()).hexdigest();print(json.dumps({'status':'TRANSFER_READY','bytes':archive.stat().st_size,'sha256':digest}),flush=True)
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  assert self.path=='/adapters.tar.gz';self.send_response(200);self.send_header('Content-Length',str(archive.stat().st_size));self.end_headers()
  with archive.open('rb') as f:
   for block in iter(lambda:f.read(1024**2),b''):self.wfile.write(block)
 def log_message(self,*args):pass
server=http.server.HTTPServer(('127.0.0.1',29848),Handler);server.timeout=900;server.handle_request()
# Keep PID1 alive while kubectl exec drains the downloaded bytes and exits.
# The host UID-cleans this finite Pod immediately after complete verification.
# Otherwise PID1 exit can kill the exec client and give a nonzero transport exit
# despite an exact archive, as observed during the A2 rescue.
server.timeout=600;server.handle_request();server.server_close();print('TRANSFER_POD_FINISHED',flush=True)
'''


def verify_local_backup(dest, receipts):
    """Validate archived bytes against all four actual training receipts."""
    record=json.loads((dest/'verified-private.json').read_text())
    assert record['status']=='FOUR_REAL_ADAPTERS_BACKED_UP_LOCALLY'
    assert set(receipts)==set(record['states'])=={'answer_only','reasoning','A1','A2'}
    assert sha(dest/'adapters.tar.gz')==record['archive_sha256']
    expected={cid+'/'+name for cid in receipts for name in
              ['adapter/adapter_model.safetensors','adapter/adapter_config.json','receipt.json']}
    with tarfile.open(dest/'adapters.tar.gz') as archive:
        members=archive.getmembers()
        assert len(members)==13 and {m.name for m in members}==expected|{'manifest-private.json'}
        assert all(m.isfile() for m in members)
        manifest=json.load(archive.extractfile('manifest-private.json'))
        assert set(manifest['files'])==expected and not manifest['model_weights_public']
        for name,meta in manifest['files'].items():
            raw=archive.extractfile(name).read()
            assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
        for cid,receipt_file in receipts.items():
            raw=archive.extractfile(cid+'/receipt.json').read()
            assert raw==receipt_file.read_bytes()
            receipt=json.loads(raw)
            assert manifest['files'][cid+'/adapter/adapter_model.safetensors']['sha256']==receipt['adapter_sha256']
    assert (dest/'adapters.tar.gz').stat().st_mode & 0o077 == 0
    return record


def consolidate_recovered_local_backups():
    """Reuse verified local transfers; creates no Pod and touches no live PVC."""
    early=STAGE/'early-adapter-backup-private'
    original=STAGE/'A2-node-eviction-private/original'
    source=json.loads((early/'verified-private.json').read_text())
    assert source['status']=='THREE_REAL_ADAPTERS_READ_ONLY_EARLY_BACKUP'
    assert sha(early/'three-adapters.tar.gz')==source['archive_sha256']
    recovered=json.loads((STAGE/'A2-node-eviction-private/recovered-private.json').read_text())
    assert sha(original/'reasoning/adapter/adapter_model.safetensors')==recovered['adapter_sha256']
    raw_files={}
    with tarfile.open(early/'three-adapters.tar.gz') as archive:
        members=archive.getmembers()
        assert len(members)==len(source['files'])==9 and {m.name for m in members}==set(source['files'])
        for member in members:
            assert member.isfile();raw=archive.extractfile(member).read();meta=source['files'][member.name]
            assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
            raw_files[member.name]=raw
    for name in ['adapter/adapter_model.safetensors','adapter/adapter_config.json','receipt.json']:
        raw_files['A2/'+name]=(original/'reasoning'/name).read_bytes()
    receipts={cid:STAGE/'runs/pair'/cid/'receipt.json' for cid in ['answer_only','reasoning']}
    receipts.update(A1=STAGE/'runs/A1/reasoning/receipt.json',A2=original/'reasoning/receipt.json')
    for cid,path in receipts.items():
        assert raw_files[cid+'/receipt.json']==path.read_bytes()
        assert hashlib.sha256(raw_files[cid+'/adapter/adapter_model.safetensors']).hexdigest()==json.loads(path.read_text())['adapter_sha256']
    dest=STAGE/'adapter-backup';assert not dest.exists();dest.mkdir(mode=0o700)
    manifest={'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in raw_files.items()},'model_weights_public':False}
    with tarfile.open(dest/'adapters.tar.gz','w:gz') as archive:
        for name,raw in {**raw_files,'manifest-private.json':(json.dumps(manifest,indent=2)+'\n').encode()}.items():
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;archive.addfile(info,io.BytesIO(raw))
    (dest/'adapters.tar.gz').chmod(0o600)
    save(dest/'verified-private.json',{'status':'FOUR_REAL_ADAPTERS_BACKED_UP_LOCALLY','archive_sha256':sha(dest/'adapters.tar.gz'),
        'states':list(receipts),'GPU':0,'weights_published':False,'method':'CONSOLIDATED_VERIFIED_EXISTING_LOCAL_TRANSFERS',
        'additional_cluster_objects_created':0,'early_archive_sha256':source['archive_sha256'],
        'original_A2_rescue_archive_sha256':recovered['archive_sha256']})
    verify_local_backup(dest,receipts)
    print('FOUR_REAL_ADAPTERS_LOCAL_CONSOLIDATION_VERIFIED_NO_NEW_POD',flush=True)


def main():
    selection = json.loads((STAGE/'native-selection-private.json').read_text())
    assert selection['status'] == 'NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN'
    assert json.loads((STAGE/'confirmation/analysis-private.json').read_text())['status'] == 'POST_SELECTION_CONFIRMATION_SCORED_NO_RESELECTION'
    dest=STAGE/'adapter-backup'
    if dest.exists():
        receipts={cid:STAGE/'runs/pair'/cid/'receipt.json' for cid in ['answer_only','reasoning']}
        receipts.update({cid:STAGE/'runs'/cid/'reasoning/receipt.json' for cid in ['A1','A2']})
        verify_local_backup(dest,receipts)
        print('FOUR_REAL_ADAPTERS_EXISTING_LOCAL_BACKUP_REVERIFIED_AGAINST_FINAL_RECEIPTS',flush=True)
        return
    assert not gpu_cache_conflicts(json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items'], 'miw113-kali-two-model-cache-1115')
    dest = STAGE/'adapter-backup'; assert not dest.exists(); dest.mkdir(mode=0o700)
    states = []
    for cid, arm in [('answer_only','answer_only'),('reasoning','reasoning'),('A1','reasoning'),('A2','reasoning')]:
        folder = STAGE/'runs'/('pair' if cid in ['answer_only','reasoning'] else cid)
        receipt = json.loads((folder/arm/'receipt.json').read_text())
        launch = json.loads((folder/'launch-freeze-private.json').read_text())
        states.append({'label':cid,'cache_adapter':launch['config']['durable_output']+'/'+arm+'/adapter', 'adapter_sha256':receipt['adapter_sha256']})
    labels = {'app.kubernetes.io/managed-by':'miw113','app.kubernetes.io/part-of':'kali-bounded-adapter-transfer'}
    cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':NAME,'labels':labels},'data':{'worker.py':WORKER,'config.json':json.dumps({'states':states})}}
    resources = {'cpu':'1','memory':'2Gi','ephemeral-storage':'1Gi'}
    pod = {'apiVersion':'v1','kind':'Pod','metadata':{'name':NAME,'labels':labels},'spec':{
        'restartPolicy':'Never','activeDeadlineSeconds':1800,'automountServiceAccountToken':False,
        'nodeSelector':{'kubernetes.io/arch':'amd64'},
        'containers':[{'name':'transfer','image':json.loads((ROOT/'configs/gpu-runtime-image.lock.json').read_text())['image'],
        'command':['python','-u','/input/worker.py'],'resources':{'requests':resources,'limits':resources},
        'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True},{'name':'scratch','mountPath':'/scratch'}, {'name':'cache','mountPath':'/cache','readOnly':True}]}],
        'volumes':[{'name':'input','configMap':{'name':NAME}},{'name':'scratch','emptyDir':{'sizeLimit':'1Gi'}},
                   {'name':'cache','persistentVolumeClaim':{'claimName':'miw113-kali-two-model-cache-1115','readOnly':True}}]}}
    save(dest/'objects-private.json',[cm,pod]); created = []; uid = None
    try:
        for obj in [cm,pod]: k('create','--dry-run=server','-f','-',body=obj)
        for obj in [cm,pod]: k('create','-f','-',body=obj); created.append(obj['kind'].lower())
        obj = json.loads(k('get','pod',NAME,'-o','json').stdout); uid = obj['metadata']['uid']
        until=time.monotonic()+900; ready=None
        while time.monotonic()<until:
            obj=json.loads(k('get','pod',NAME,'-o','json').stdout);assert obj['metadata']['uid']==uid
            logs=k('logs',NAME,check=False)
            for line in logs.stdout.splitlines():
                if line.startswith('{'):
                    r=json.loads(line)
                    if r.get('status')=='TRANSFER_READY':ready=r
            if ready:break
            assert obj.get('status',{}).get('phase') not in ['Failed','Succeeded'],'Transfer terminated before download'
            time.sleep(10)
        assert ready,'No archive was made; inspect bounded transfer logs'
        partial=dest/'adapters.tar.gz.partial'
        program="import sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:29848/adapters.tar.gz',timeout=120); import shutil;shutil.copyfileobj(r,sys.stdout.buffer,1024**2)"
        assert BASE.count('--request-timeout=30s')==1
        stream_base=['--request-timeout=480s' if arg=='--request-timeout=30s' else arg for arg in BASE]
        with partial.open('wb') as f:
            r=subprocess.run(stream_base+['exec',NAME,'--','python','-c',program],stdout=f,stderr=subprocess.PIPE,timeout=480)
        assert r.returncode==0,'Transfer failed, private partial retained'
        assert partial.stat().st_size==ready['bytes'] and sha(partial)==ready['sha256']
        with tarfile.open(partial) as archive:
            members=archive.getmembers();assert len({m.name for m in members})==len(members)
            assert all(m.isfile() and (dest/m.name).resolve().is_relative_to(dest.resolve()) for m in members)
            manifest=json.load(archive.extractfile('manifest-private.json'))
            assert set(manifest['files'])=={m.name for m in members}-{'manifest-private.json'}
            for name,meta in manifest['files'].items():
                raw=archive.extractfile(name).read();assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
            for state in states:
                assert manifest['files'][state['label']+'/adapter/adapter_model.safetensors']['sha256']==state['adapter_sha256']
        archive_path=dest/'adapters.tar.gz';partial.rename(archive_path);archive_path.chmod(0o600)
        save(dest/'verified-private.json',{'status':'FOUR_REAL_ADAPTERS_BACKED_UP_LOCALLY','archive_sha256':sha(archive_path),'states':[s['label'] for s in states],'GPU':0,'weights_published':False})
        print('FOUR_REAL_ADAPTERS_BACKED_UP_LOCALLY',flush=True)
    finally:
        if 'pod' in created:
            actual=k('get','pod',NAME,'-o','json',check=False)
            if actual.returncode==0:
                assert uid is not None and json.loads(actual.stdout)['metadata']['uid']==uid
                k('delete','pod',NAME,'--wait=true','--timeout=30s')
        if 'configmap' in created:k('delete','configmap',NAME,'--wait=true','--timeout=30s')


if __name__=='__main__':main()
