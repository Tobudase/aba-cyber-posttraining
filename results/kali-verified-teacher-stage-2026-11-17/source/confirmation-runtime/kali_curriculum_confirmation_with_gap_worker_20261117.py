"""Finite confirmation/TRAIN diagnostics; preflight all adapters before queries."""
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
    out=Path(cfg['durable_output']);assert not out.exists();out.mkdir(parents=True);rc=0;states={};preflight={};preflight_passed=False;confirmation_started=False
    try:
        import gc,torch
        from transformers import AutoModelForCausalLM
        from peft import PeftModel
        sys.path.insert(0,str(root/'scripts'))
        from kali_exact_adapter_loading_20261115 import load_exact_adapter
        assert torch.cuda.get_device_name(0) in mp['allowed_GPU_models']
        # These are original TRAIN receipt probes, not confirmation questions.
        # Fail BEFORE any hidden question if a permitted different GPU cannot
        # reproduce every selected adapter's exact original trained logit probe.
        torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=False
        for state in cfg['states']:
            if not state['adapter_cache']:continue
            adapter=Path(state['adapter_cache']);r=json.loads((adapter.parent/'receipt.json').read_text())
            assert sha(adapter/'adapter_model.safetensors')==state['pointer']['adapter_sha256']==r['adapter_sha256']
            check=AutoModelForCausalLM.from_pretrained(model,local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
            check=PeftModel.from_pretrained(check,adapter,is_trainable=False);check.eval();check.requires_grad_(False)
            load_exact_adapter(check,adapter,'default',is_trainable=False)
            probe=torch.tensor([r['reload_probe_input_ids']],device='cuda')
            with torch.inference_mode():values=check(input_ids=probe,use_cache=False).logits[:,-1].float().cpu()
            assert torch.isfinite(values).all() and hashlib.sha256(values.numpy().tobytes()).hexdigest()==r['reload_probe_logits_sha256']
            preflight[state['label']]={'adapter_sha256':r['adapter_sha256'],'exact_original_TRAIN_logit_probe_identical':True}
            del check,probe,values;gc.collect();torch.cuda.empty_cache()
        preflight_passed=True;print('ALL_ENDPOINT_RELOAD_PREFLIGHT_PASS_BEFORE_CONFIRMATION',flush=True)
        for state in cfg['states']:
            label=state['label'];cmd=[sys.executable,str(root/'scripts/eval_kali_curriculum_sft_20261117.py'),'--stage',str(root/'stage'),'--model-path',str(model),'--output',str(out/(label+'-predictions.json'))]
            if state['adapter_cache']:
                import re
                assert re.fullmatch(r'/cache/kali-execution-20261114/miw113-kali-curriculum-sft-(?:pair(?:-r2)?|a1|a2)-1117/(?:answer_only|reasoning)/adapter',state['adapter_cache'])
                adapter=Path(state['adapter_cache']);assert sha(adapter/'adapter_model.safetensors')==state['pointer']['adapter_sha256'];cmd+=['--adapter',str(adapter)]
            else:assert state['pointer']['adapter_sha256'] is None
            print('CONFIRM_STATE_START '+label,flush=True)
            confirmation_started=True
            with (out/(label+'.log')).open('w') as log:
                remaining=cfg['runtime_seconds']-300-(time.monotonic()-began);assert remaining>0
                result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=remaining)
            assert result.returncode==0,'Confirmation inference failed'
            pred=json.loads((out/(label+'-predictions.json')).read_text());assert pred['status']=='COMPLETE';states[label]={'responses':len(pred['predictions']),'adapter_sha256':pred.get('adapter_sha256'),'reload_audit':pred.get('reload_audit')};print('CONFIRM_STATE_COMPLETE '+label,flush=True)
            # Separate known TRAIN gap diagnostic, never confirmation/search feedback.
            gapcmd=list(cmd);gapcmd[gapcmd.index('--stage')+1]=str(root/'gap-stage');gapcmd[gapcmd.index('--output')+1]=str(out/(label+'-gap-predictions.json'))
            print('TRAIN_GAP_START '+label,flush=True)
            with (out/(label+'-gap.log')).open('w') as log:
                remaining=cfg['runtime_seconds']-300-(time.monotonic()-began);assert remaining>0
                gapresult=subprocess.run(gapcmd,stdout=log,stderr=subprocess.STDOUT,timeout=remaining)
            assert gapresult.returncode==0,'Known TRAIN gap diagnostic inference failed'
            gap=json.loads((out/(label+'-gap-predictions.json')).read_text());assert gap['status']=='COMPLETE' and len(gap['predictions'])==18
            states[label]['known_TRAIN_gap_responses']=18;print('TRAIN_GAP_COMPLETE '+label,flush=True)

    except BaseException as e:rc=1;print('CONFIRM_FAILED '+type(e).__name__+' '+str(e)[:180],flush=True)
    import torch
    receipt={'status':'COMPLETE' if rc==0 else 'FAILED','returncode':rc,'GPU':torch.cuda.get_device_name(0),'seconds':time.monotonic()-began,'worker_sha256':cfg['worker_sha256'],'bundle_sha256':cfg['bundle_sha256'],'selection_sha256':cfg['selection_sha256'],'states':states,'training_updates':0,'original_model_verified':True,'official_TEST_queries':0,'confirmation_unique_tasks':24,'all_endpoints_exact_reload_preflight_passed_before_queries':preflight_passed,'confirmation_inference_started':confirmation_started,'TRAIN_receipt_preflight':preflight}
    (out/'execution-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    artifacts={f.name:f.read_text() for f in out.glob('*') if f.is_file() and f.suffix in ['.json','.log']}
    sys.path.insert(0,str(root/'scripts'));from kali_framed_artifacts_20261117 import emit;emit(artifacts,'CURRICULUM_CONFIRM_ARTIFACT');print('CONFIRM_DONE '+json.dumps(receipt),flush=True);assert rc==0
if __name__=='__main__':main()
