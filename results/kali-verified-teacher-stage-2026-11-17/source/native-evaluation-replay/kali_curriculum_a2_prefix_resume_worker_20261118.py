"""Conditional finite zero-update prefix continuation after an actual deadline."""
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
    mp=json.loads((root/'stage/model-protocol.json').read_text());assert sha('/cache/runtime-deps.tar')==mp['runtime_archive_sha256']
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
    import shutil
    original=Path(cfg['original_output']);assert str(original)=='/cache/kali-execution-20261114/miw113-kali-curriculum-sft-a2-1117'
    adapter=original/'reasoning/adapter';assert sha(adapter/'adapter_model.safetensors')==cfg['adapter_sha256']
    assert sha(original/'reasoning/receipt.json')==cfg['original_training_receipt_sha256']
    out=Path(cfg['durable_output']);assert not out.exists();out.mkdir(parents=True)
    prefix=root/'stage/prefix-predictions-private.json'
    # Generated research outputs stay on the existing project PVC; never put
    # the response prefix in a broadly readable ConfigMap or a Job spec.
    cached_prefix=Path(cfg['prefix_cache'])
    assert str(cached_prefix)=='/cache/kali-execution-20261114/miw113-kali-curriculum-eval-a2-r6-1117/reasoning-predictions.json'
    assert not prefix.exists() and sha(cached_prefix)==cfg['prefix_sha256']
    prefix.write_bytes(cached_prefix.read_bytes())
    assert sha(prefix)==cfg['prefix_sha256'] and cfg['runtime_seconds']<=6600
    assert cfg['minimum_prefix_responses'] in [416,512]
    assert cfg['reused_prefix_responses']>=cfg['minimum_prefix_responses'] and cfg['additional_tail_GPU_jobs']==1
    assert len(json.loads(prefix.read_text())['predictions'])==cfg['reused_prefix_responses']
    assert cfg['failed_full_replay_job_uid']=='3989dd73-166b-4746-b1e5-ac2d15755c4d'
    target=out/'reasoning-predictions.json';rc=0
    try:
        remaining=cfg['runtime_seconds']-90-(time.monotonic()-began);assert remaining>0
        argv=[sys.executable,str(root/'scripts/eval_kali_curriculum_prefix_resume_20261118.py'),
              '--stage',str(root/'stage'),'--model-path',str(model),'--adapter',str(adapter),
              '--output',str(target),'--prefix',str(root/'stage/prefix-predictions-private.json'),
              '--prefix-sha256',cfg['prefix_sha256'],'--minimum-prefix-responses',str(cfg['minimum_prefix_responses']),
              '--original-eval-source',str(root/'scripts/eval_kali_curriculum_sft_20261117.py'),
              '--original-eval-sha256',cfg['original_eval_sha256']]
        print('STAGE_START exact-adapter-full-eval-replay',flush=True)
        with (out/'eval-resume.log').open('w') as f:
            result=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=remaining)
        assert result.returncode==0,'Exact adapter full evaluation replay failed'
        print('STAGE_COMPLETE exact-adapter-full-eval-replay',flush=True)
    except BaseException as exc:
        rc=1;print('STAGE_FAILED '+type(exc).__name__+' '+str(exc)[:200],flush=True)
    receipt={'status':'COMPLETE' if rc==0 else 'FAILED','worker_sha256':cfg['worker_sha256'],
        'bundle_sha256':cfg['bundle_sha256'],'training_updates':0,'original_job_uid':cfg['original_job_uid'],
        'original_prediction_file_zero_bytes':True,'original_adapter_sha256':cfg['adapter_sha256'],
        'original_training_receipt_sha256':cfg['original_training_receipt_sha256'],
        'model_revision':mp['model_revision'],'seconds':time.monotonic()-began,
        'official_TEST_queries':0,'confirmation_queries':0,'durable_output':str(out),'prefix_resume_attempt':True,
        'failed_full_replay_job_uid':cfg['failed_full_replay_job_uid'],
        'reused_prefix_responses':cfg['reused_prefix_responses'],'prefix_sha256':cfg['prefix_sha256'],
        'original_eval_sha256':cfg['original_eval_sha256'],'additional_tail_GPU_jobs':1,
        'prefix_contingency_before_A2_score_sha256':cfg['prefix_contingency_sha256']}
    (out/'execution-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    artifacts={str(f.relative_to(out)):f.read_text() for f in out.rglob('*') if f.is_file() and f.suffix in ['.json','.log']}
    sys.path.insert(0,str(root/'scripts'));from kali_framed_artifacts_20261117 import emit
    emit(artifacts,'CURRICULUM_A2_EVAL_REPLAY_ARTIFACT');print('A2_EVAL_REPLAY_DONE',flush=True)
    assert rc==0
if __name__=='__main__':main()
