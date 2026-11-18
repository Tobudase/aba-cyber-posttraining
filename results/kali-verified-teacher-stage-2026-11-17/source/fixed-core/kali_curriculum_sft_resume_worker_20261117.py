"""Finite single-GPU execution; new adapters always start from original weights."""
import base64,concurrent.futures,gzip,hashlib,json,os,subprocess,sys,tarfile,time
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def main():
    began=time.monotonic();cfg=json.loads(Path('/input/config.json').read_text());assert sha('/input/worker.py')==cfg['worker_sha256'] and sha('/input/bundle.json.gz')==cfg['bundle_sha256']
    bundle=json.loads(gzip.decompress(Path('/input/bundle.json.gz').read_bytes()));root=Path('/scratch/experiment');root.mkdir()
    for name,text in bundle.items():
        p=root/name;assert p.resolve().is_relative_to(root);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    data=json.loads((root/'stage/paired-training-private.json').read_text());mp=data['model_protocol'];assert sha('/cache/runtime-deps.tar')==mp['runtime_archive_sha256']
    deps=Path('/scratch/deps');deps.mkdir()
    with tarfile.open('/cache/runtime-deps.tar') as t:
        assert all(m.isfile() and (deps/m.name).resolve().is_relative_to(deps) for m in t.getmembers());t.extractall(deps,filter='data')
    os.environ['PYTHONPATH']=str(deps);sys.path.insert(0,str(deps))
    from importlib.metadata import version
    for k,v in mp['expected_packages'].items():assert version(k)==v
    model=Path('/scratch/model');model.mkdir()
    def fetch(item):
        import requests
        name,digest=item
        for attempt in range(3):
            try:
                with requests.get('https://huggingface.co/'+mp['model_id']+'/resolve/'+mp['model_revision']+'/'+name,stream=True,timeout=(20,120)) as r:
                    r.raise_for_status()
                    with (model/name).open('wb') as f:
                        for b in r.iter_content(8*1024**2):
                            if b:f.write(b)
                assert sha(model/name)==digest;print('MODEL_VERIFIED '+name,flush=True);return
            except Exception:
                if attempt==2:raise
                time.sleep(5*(attempt+1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,mp['checkpoint_files'].items()))
    out=Path(cfg['durable_output']);assert not out.exists();out.mkdir(parents=True);rc=0
    def run(argv,label):
        nonlocal rc
        remaining=cfg['runtime_seconds']-300-(time.monotonic()-began);assert remaining>0,'Finite GPU runtime budget'
        print('STAGE_START '+label,flush=True)
        with (out/(label+'.log')).open('w') as f:r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=remaining)
        if r.returncode:rc=r.returncode;raise RuntimeError('Stage failed: '+label)
        print('STAGE_COMPLETE '+label,flush=True)
    ev=[sys.executable,str(root/'scripts/eval_kali_curriculum_sft_resume_20261117.py'),'--stage',str(root/'stage'),'--model-path',str(model)]
    if cfg.get('resume_prefix_sha256'):
        import shutil
        source=root/'stage/base-resume-private.json';assert sha(source)==cfg['resume_prefix_sha256'];shutil.copy2(source,out/'base-predictions.json')
    try:
        if cfg['mode']=='pair':
            run(ev+['--output',str(out/'base-predictions.json')]+(['--resume-prefix'] if cfg.get('resume_prefix_sha256') else []),'eval-base')
            arms=['answer_only','reasoning']
        else:
            assert cfg['mode']=='native_candidate';arms=['reasoning']
            data['protocol']['learning_rate']=cfg['learning_rate'];(root/'stage/paired-training-private.json').write_text(json.dumps(data)+'\n')
        for arm in arms:
            digest=sha(root/'stage/paired-training-private.json')
            run([sys.executable,str(root/'scripts/train_kali_curriculum_sft_20261117.py'),'--data',str(root/'stage/paired-training-private.json'),'--expected-sha256',digest,'--arm',arm,'--model-path',str(model),'--output',str(out/arm)],'train-'+arm)
            run(ev+['--adapter',str(out/arm/'adapter'),'--output',str(out/(arm+'-predictions.json'))],'eval-'+arm)
        if len(arms)==2:
            receipts=[json.loads((out/arm/'receipt.json').read_text()) for arm in arms];assert receipts[0]['initial_adapter_sha256']==receipts[1]['initial_adapter_sha256']
    except BaseException as e:
        rc=rc or 1;print('STAGE_FAILED '+type(e).__name__+' '+str(e)[:200],flush=True)
    import torch
    receipt={'status':'COMPLETE' if rc==0 else 'FAILED','returncode':rc,'GPU':torch.cuda.get_device_name(0),'seconds':time.monotonic()-began,'worker_sha256':cfg['worker_sha256'],'bundle_sha256':cfg['bundle_sha256'],'mode':cfg['mode'],'candidate':cfg.get('candidate'),'learning_rate':cfg.get('learning_rate',data['protocol']['learning_rate']),'original_model_verified':True,'model_revision':mp['model_revision'],'official_TEST_queries':0,'confirmation_queries':0,'fresh_original_for_each_arm':True,'resume_prefix_sha256':cfg.get('resume_prefix_sha256'),'prior_attempt_job':cfg.get('prior_attempt_job'),'durable_output':str(out)}
    (out/'execution-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    artifacts={str(f.relative_to(out)):f.read_text() for f in out.rglob('*') if f.is_file() and f.suffix in ['.json','.log'] and 'adapter' not in f.parts}
    sys.path.insert(0,str(root/'scripts'));from kali_framed_artifacts_20261117 import emit;emit(artifacts,'CURRICULUM_SFT_ARTIFACT');print('CURRICULUM_SFT_DONE '+json.dumps(receipt),flush=True)
    assert rc==0
if __name__=='__main__':main()
