"""Fresh single-GPU pair/native backend with immutable payloads and cleanup."""
import argparse,base64,gzip,hashlib,json,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT as JOBS,k,submit,poll,cleanup,gpu_cache_conflicts
from prepare_kali_verified_curriculum_20261117 import OUT,save,sha
from kali_framed_artifacts_20261117 import parse as parse_frames
from kali_curriculum_admission_retry_20261117 import admission_retry
STAGE=OUT/'paired-sft'
def name_for(label):return 'miw113-kali-curriculum-sft-'+label.lower()+'-1117'
def run(label,lr=None):
    assert label=='pair' and lr is None or label in ['A1','A2'] and lr in [5e-6,1e-5,2e-5]
    until_release=time.monotonic()+180
    while True:
        active=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
        if not gpu_cache_conflicts(active,'miw113-kali-two-model-cache-1115'):break
        assert time.monotonic()<until_release,'Previous owned GPU/cache not yet released; do not duplicate'
        time.sleep(5)
    dest=STAGE/'runs'/label;assert not dest.exists(),'A completed or failed candidate must never be relabeled as fresh';dest.mkdir(parents=True)
    data=json.loads((STAGE/'paired-training-private.json').read_text());audit=json.loads((STAGE/'encoding-audit.json').read_text());assert sha(STAGE/'paired-training-private.json')==audit['payload_sha256']
    files={}
    for n in ['paired-training-private.json','evaluation-inputs-private.json','evaluation-protocol.json']:files['stage/'+n]=(STAGE/n).read_text()
    for n in ['train_kali_curriculum_sft_20261117.py','eval_kali_curriculum_sft_20261117.py','kali_exact_adapter_loading_20261115.py','kali_framed_artifacts_20261117.py']:files['scripts/'+n]=(ROOT/'scripts'/n).read_text()
    assert not any('references' in n or 'confirmation' in n for n in files),'Evaluation references are host-only'
    bundle=gzip.compress(json.dumps(files).encode(),mtime=0);worker=ROOT/'scripts/kali_curriculum_sft_framed_worker_20261117.py';name=name_for(label)
    cfg={'mode':'pair' if label=='pair' else 'native_candidate','candidate':label,'learning_rate':lr if lr is not None else data['protocol']['learning_rate'],'worker_sha256':sha(worker),'bundle_sha256':hashlib.sha256(bundle).hexdigest(),'durable_output':'/cache/kali-execution-20261114/'+name,'runtime_seconds':12600}
    save(dest/'launch-freeze-private.json',{'config':cfg,'scripts_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items() if n.startswith('scripts/')},'original_data_sha256':sha(STAGE/'paired-training-private.json'),'new_updates_planned':data['protocol']['optimizer_updates_per_arm']*(2 if label=='pair' else 1),'evaluation_gold_sent_to_GPU':False,'resources':{'GPU':'one ordinary RTX A6000 48GB','CPU':1,'memory_GiB':16}})
    nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];eligible=[n['metadata'].get('labels',{}).get('kubernetes.io/hostname') for n in nodes if n['metadata'].get('labels',{}).get('nvidia.com/gpu.product')=='NVIDIA-RTX-A6000' and int(n['metadata'].get('labels',{}).get('nvidia.com/cuda.driver.major','0'))>=570 and not n['spec'].get('unschedulable') and not any(t['effect'] in ['NoSchedule','NoExecute'] for t in n['spec'].get('taints',[])) and any(c['type']=='Ready' and c['status']=='True' for c in n['status'].get('conditions',[]))]
    with admission_retry(name,dest):
        submitted=submit(name,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg)},{'cpu':'1','memory':'16Gi','ephemeral-storage':'30Gi','nvidia.com/rtxa6000':'1'},binary_files={'bundle.json.gz':bundle},cache=True,readonly=False,cache_claim='miw113-kali-two-model-cache-1115',cache_region=None,node_names=[n for n in eligible if n],gpu_products=['NVIDIA-RTX-A6000'],runtime=12600)
    print(json.dumps(submitted),flush=True)
    until=time.monotonic()+14700;previous=None;collected=False
    while time.monotonic()<until:
        try:state=poll(name)
        except Exception as e:
            print('TRANSIENT_POLL '+type(e).__name__,flush=True);time.sleep(30);continue
        state.pop('log_tail',None);log=JOBS/name/'worker.log'
        if log.exists():
            lines=log.read_text().splitlines();state['progress']=[s for s in lines if s.startswith(('STAGE_START','STAGE_COMPLETE','STAGE_FAILED'))][-3:]
            artifact=parse_frames(log.read_text(),'CURRICULUM_SFT_ARTIFACT')
            if artifact is not None:
                for n,t in artifact.items():
                    p=dest/n;assert p.resolve().is_relative_to(dest.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
                collected=True
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        save(dest/'monitor-private.json',state)
        if state['status'] in ['SUCCEEDED','FAILED']:
            if state['status']=='SUCCEEDED':assert collected,'Do not clean successful job without artifacts'
            cleanup(name)
            if state['status']=='FAILED':raise RuntimeError('Fresh experiment failed; original logs preserved')
            receipt=json.loads((dest/'execution-receipt.json').read_text());assert receipt['status']=='COMPLETE' and receipt['bundle_sha256']==cfg['bundle_sha256'] and receipt['worker_sha256']==cfg['worker_sha256']
            for arm in ['answer_only','reasoning'] if label=='pair' else ['reasoning']:
                r=json.loads((dest/arm/'receipt.json').read_text());e=json.loads((dest/(arm+'-predictions.json')).read_text());assert r['updates']==data['protocol']['optimizer_updates_per_arm'] and e['reload_audit']['trained_vs_reloaded_probe_identical']
            if label=='pair':
                from score_kali_curriculum_sft_20261117 import main as score_pair
                score_pair()
            else:
                from score_kali_curriculum_sft_20261117 import score_predictions,grade
                base=score_predictions(STAGE/'runs/pair/base-predictions.json');result=score_predictions(dest/'reasoning-predictions.json');save(dest/'score-private.json',{'grade':grade(result,base),'details':result})
            return dest
        time.sleep(45)
    raise TimeoutError('Finite candidate runtime including queue reached; inspect original job, never duplicate submit')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label',choices=['pair','A1','A2']);p.add_argument('--lr',type=float);a=p.parse_args();run(a.label,a.lr)
