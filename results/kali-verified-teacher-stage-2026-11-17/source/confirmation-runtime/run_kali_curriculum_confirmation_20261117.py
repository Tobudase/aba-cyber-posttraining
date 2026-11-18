"""One post-selection confirmation. No retries/reselection on observed scores."""
import argparse,base64,gzip,hashlib,json,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT as JOBS,k,submit,poll,cleanup,gpu_cache_conflicts
from prepare_kali_verified_curriculum_20261117 import OUT,save,sha
from kali_curriculum_teacher_20261117 import SYSTEM
from kali_framed_artifacts_20261117 import parse as parse_frames
STAGE=OUT/'paired-sft';CONF=STAGE/'confirmation';NAME='miw113-kali-curriculum-confirm-1117'
def prepare():
    selection_file=STAGE/'native-selection-private.json';selection=json.loads(selection_file.read_text());host=json.loads((STAGE/'native-controller/host-private.json').read_text())
    assert selection['status']=='NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN' and host['native_completed'] and not host.get('cleanup_pending') and not host.get('cleanup_errors')
    from kali_curriculum_native_facts_20261117 import require_two_scored_native_candidates
    require_two_scored_native_candidates(json.loads((STAGE/'native-controller/journal-private.json').read_text()))
    assert not selection['confirmation_used'] and selection['official_TEST_rows']==0
    pre=json.loads((STAGE/'confirmation-protocol-before-results.json').read_text());assert pre['confirmation_model_queries_at_freeze']==0 and pre['no_reselection']
    assert not CONF.exists(),'Never overwrite or create a second confirmation';CONF.mkdir()
    fixed=json.loads((STAGE/'paired-training-private.json').read_text());mp=fixed['model_protocol'];base_pointer={'candidate_id':'E0','model_id':mp['model_id'],'model_revision':mp['model_revision'],'adapter_sha256':None,'optimizer_steps':0}
    states=[{'label':'E0','pointer':base_pointer,'adapter_cache':None}]
    for arm in ['answer_only','reasoning']:
        r=json.loads((STAGE/'runs/pair'/arm/'receipt.json').read_text());cfg=json.loads((STAGE/'runs/pair/launch-freeze-private.json').read_text())['config']
        states.append({'label':'fixed_'+arm,'pointer':{'candidate_id':arm,'model_id':mp['model_id'],'model_revision':mp['model_revision'],'adapter_sha256':r['adapter_sha256'],'optimizer_steps':r['updates']},'adapter_cache':cfg['durable_output']+'/'+arm+'/adapter'})
    pointer=selection['native_selected_pointer'];cid=pointer['candidate_id'];record=json.loads((STAGE/'runs'/cid/'adapter-pointer-private.json').read_text());assert record['pointer']==pointer
    states.append({'label':'native_selected','pointer':pointer,'adapter_cache':record['cache_adapter']})
    unique=[];aliases={};seen={}
    for state in states:
        key=(state['pointer']['model_revision'],state['pointer']['adapter_sha256'])
        if key in seen:aliases[state['label']]=seen[key]
        else:seen[key]=state['label'];unique.append(state)
    # The selection is already frozen BEFORE this first use of confirmation inputs.
    source=ROOT/'data/benchkit/kali-teacher-screen-2026-11-16';sp=json.loads((source/'protocol.json').read_text());assert sha(source/'splits-private.json')==sp['split_sha256'];split=json.loads((source/'splits-private.json').read_text());rows=split['confirmation'];assert len(rows)==24 and len({r['id'] for r in rows})==24
    inputs=[{'id':r['id'],'panel':'confirmation24','messages':[{'role':'system','content':SYSTEM},{'role':'user','content':r['native_label']['query']}]} for r in rows];refs={r['id']:r['native_label'] for r in rows}
    existing=json.loads((STAGE/'evaluation-inputs-private.json').read_text());train=json.loads((STAGE/'paired-training-private.json').read_text())['encoded']['reasoning'];assert not set(refs)&({r['id'] for r in existing}|{r['id'] for r in train})
    save(CONF/'evaluation-inputs-private.json',inputs);save(CONF/'references-private.json',refs);save(CONF/'groups-private.json',{r['id']:r['group_id'] for r in rows});save(CONF/'model-protocol.json',mp)
    ep=json.loads((STAGE/'evaluation-protocol.json').read_text());ep.update(status='CONFIRMATION_FROZEN_AFTER_SELECTION',rows=24,panels={'confirmation24':24},input_sha256=sha(CONF/'evaluation-inputs-private.json'));save(CONF/'evaluation-protocol.json',ep)
    freeze={'status':'SELECTED_ENDPOINTS_AND_CONFIRMATION_FROZEN_BEFORE_CALLS','selection_sha256':sha(selection_file),'prespecified_protocol_sha256':sha(STAGE/'confirmation-protocol-before-results.json'),'states':unique,'aliases':aliases,'rows':24,'expected_responses_per_state':144,'expected_total_responses':144*len(unique),'input_sha256':sha(CONF/'evaluation-inputs-private.json'),'reference_sha256':sha(CONF/'references-private.json'),'protocol_sha256':sha(CONF/'evaluation-protocol.json'),'groups_sha256':sha(CONF/'groups-private.json'),'no_reselection':True,'official_TEST_queries':0}
    save(CONF/'selection-freeze-private.json',freeze);return freeze
def run():
    from kali_curriculum_gpu_budget_20261117 import ledger
    ledger(prospective_seconds=18000)  # Pre-call 4.5h Pod +30min Job, after node-eviction replay.
    freeze=prepare();files={'stage/'+n:(CONF/n).read_text() for n in ['evaluation-inputs-private.json','evaluation-protocol.json','model-protocol.json']}
    gap=STAGE/'gap-diagnostic';gapfreeze=json.loads((gap/'protocol-before-results-private.json').read_text())
    assert gapfreeze['unique_known_training_gap_tasks']==3 and gapfreeze['not_generalization'] and gapfreeze['does_not_change_selection_or_confirmation']
    assert sha(gap/'evaluation-inputs-private.json')==gapfreeze['inputs_sha256'] and sha(gap/'evaluation-protocol.json')==gapfreeze['protocol_sha256']
    for n in ['evaluation-inputs-private.json','evaluation-protocol.json']:files['gap-stage/'+n]=(gap/n).read_text()
    for n in ['eval_kali_curriculum_sft_20261117.py','kali_exact_adapter_loading_20261115.py','kali_framed_artifacts_20261117.py']:files['scripts/'+n]=(ROOT/'scripts'/n).read_text()
    assert not any('references' in n or 'groups' in n for n in files)
    # One unchanged confirmation, with four endpoints and separate TRAIN fit.
    # Fixed-pair timing showed that a 4h process cap could truncate this once-only
    # evaluation. This is a pre-call runtime ceiling amendment, not extra samples.
    bundle=gzip.compress(json.dumps(files).encode(),mtime=0);worker=ROOT/'scripts/kali_curriculum_confirmation_with_gap_worker_20261117.py';cfg={'worker_sha256':sha(worker),'bundle_sha256':hashlib.sha256(bundle).hexdigest(),'durable_output':'/cache/kali-execution-20261114/'+NAME,'runtime_seconds':16200,'selection_sha256':freeze['selection_sha256'],'states':freeze['states'],'known_TRAIN_gap_protocol_sha256':sha(gap/'protocol-before-results-private.json')}
    save(CONF/'launch-freeze-private.json',{'config':cfg,'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()},'training_updates':0,'evaluation_gold_sent_to_GPU':False,'submitted_source_snapshot_required':True,'all_endpoints_original_TRAIN_reload_probe_before_first_confirmation':True})
    snapshots=CONF/'submitted-source-private';snapshots.mkdir()
    source_names=['run_kali_curriculum_confirmation_20261117.py','kali_curriculum_confirmation_with_gap_worker_20261117.py',
        'eval_kali_curriculum_sft_20261117.py','kali_exact_adapter_loading_20261115.py','kali_framed_artifacts_20261117.py','kali_curriculum_gpu_budget_20261117.py']
    for name in source_names:(snapshots/name).write_bytes((ROOT/'scripts'/name).read_bytes())
    save(CONF/'submitted-source-freeze-private.json',{name:sha(snapshots/name) for name in source_names})
    until=time.monotonic()+180
    while True:
        active=json.loads(k('get','pods','-l','app.kubernetes.io/managed-by=miw113','-o','json').stdout)['items']
        if not gpu_cache_conflicts(active,'miw113-kali-two-model-cache-1115'):break
        assert time.monotonic()<until,'Previous native GPU/cache not yet released';time.sleep(5)
    original_gpu_required=(STAGE/'A2-node-eviction-private/A6000-fingerprint-recovery-private.json').exists()
    use_a100=(STAGE/'A2-node-eviction-private/A100-hardware-migration-private.json').exists() and not original_gpu_required
    cpu_fit=STAGE/'A2-node-eviction-private/A6000-CPU-fit-private.json'
    cpu_request=json.loads(cpu_fit.read_text())['after']['cpu'] if cpu_fit.exists() else '1'
    products=['NVIDIA-A100-SXM4-80GB','NVIDIA-A100-80GB-PCIe'] if use_a100 else ['NVIDIA-RTX-A6000']
    resource='nvidia.com/a100' if use_a100 else 'nvidia.com/rtxa6000'
    fit_resource=use_a100 and (STAGE/'A2-node-eviction-private/A100-resource-fit-private.json').exists()
    nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];eligible=[n['metadata'].get('labels',{}).get('kubernetes.io/hostname') for n in nodes if n['metadata']['name']!='hcc-prp-c5038.unl.edu' and n['metadata'].get('labels',{}).get('nvidia.com/gpu.product') in products and (not use_a100 or int(n['status'].get('allocatable',{}).get('nvidia.com/a100','0'))>0) and int(n['metadata'].get('labels',{}).get('nvidia.com/cuda.driver.major','0'))>=570 and not n['spec'].get('unschedulable') and not any(t['effect'] in ['NoSchedule','NoExecute'] for t in n['spec'].get('taints',[])) and any(c['type']=='Ready' and c['status']=='True' for c in n['status'].get('conditions',[]))]
    assert eligible,'No healthy ordinary compatible GPU node; do not silently relax affinity'
    # Worker writes ONLY its new unique output directory on this volume. A RO
    # mount would fail mkdir before inference; original checkpoints are read only
    # by the worker and no concurrent GPU shares this PVC.
    print(json.dumps(submit(NAME,{'worker.py':worker.read_text(),'config.json':json.dumps(cfg)},{'cpu':cpu_request,'memory':'20Gi' if fit_resource or original_gpu_required else '24Gi' if use_a100 else '16Gi','ephemeral-storage':'24Gi' if fit_resource or original_gpu_required else '30Gi',resource:'1'},binary_files={'bundle.json.gz':bundle},cache=True,readonly=False,cache_claim='miw113-kali-two-model-cache-1115',cache_region=None,node_names=[n for n in eligible if n],gpu_products=products,runtime=16200)),flush=True)
    until=time.monotonic()+24000;previous=None;collected=False
    while time.monotonic()<until:
        try:state=poll(NAME)
        except Exception as e:print('TRANSIENT '+type(e).__name__,flush=True);time.sleep(30);continue
        state.pop('log_tail',None);log=JOBS/NAME/'worker.log'
        if log.exists():
            lines=log.read_text().splitlines();state['progress']=[s for s in lines if s.startswith(('CONFIRM_STATE','CONFIRM_FAILED'))][-3:];artifact=parse_frames(log.read_text(),'CURRICULUM_CONFIRM_ARTIFACT')
            if artifact is not None:
                data=artifact;dest=CONF/'runs';dest.mkdir(exist_ok=True)
                for n,t in data.items():assert Path(n).name==n;(dest/n).write_text(t)
                collected=True
        if state!=previous:print(json.dumps(state),flush=True);previous=state
        save(CONF/'monitor-private.json',state)
        if state['status'] in ['SUCCEEDED','FAILED']:
            if state['status']=='SUCCEEDED':assert collected
            cleanup(NAME)
            if state['status']=='FAILED':raise RuntimeError('Original confirmation attempt failed, preserve all partials; no retuning/reselection')
            receipt=json.loads((CONF/'runs/execution-receipt.json').read_text());assert receipt['status']=='COMPLETE' and receipt['selection_sha256']==freeze['selection_sha256'] and receipt['bundle_sha256']==cfg['bundle_sha256'];return
        time.sleep(45)
    raise TimeoutError('Finite confirmation deadline; do not resubmit blindly')
if __name__=='__main__':run()
