"""Audit the same once-frozen cohort across an actual deadline-only tail."""
import base64,gzip,hashlib,json
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,sha,save
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_framed_artifacts_20261117 import parse
from kali_curriculum_prefix_resume_20261118 import validate_prefix,blocks

STAGE=OUT/'paired-sft'
def read(path):return json.loads(path.read_text())

def audit(folder):
    folder=Path(folder);tail=folder/'tail';original=folder/'original-deadline-failed-private/runs'
    activation=read(folder/'deadline-tail-activation-private.json')
    assert activation['status']=='ACTUAL_ORIGINAL_CONFIRMATION_DEADLINE_FAILURE_SAME_COHORT_TAIL_ACTIVATED'
    planfile=STAGE/'confirmation-deadline-contingency-before-scoring-private.json';plan=read(planfile)
    assert sha(planfile)==activation['operational_plan_sha256'] and not activation['confirmation_score_inspected']
    assert activation['new_optimizer_updates']==activation['new_training_candidates']==0
    assert not activation['original_timers_or_sampling_or_data_or_selection_changed']
    assert sha(folder/'selection-freeze-private.json')==activation['selection_freeze_sha256']==plan['selection_freeze_sha256']
    assert sha(folder/'launch-freeze-private.json')==activation['original_launch_sha256']==plan['original_launch_sha256']
    freeze=read(folder/'selection-freeze-private.json');launch=read(folder/'launch-freeze-private.json')
    oldhost=read(JOBS/activation['failed_job']/'host.json')
    assert oldhost['uid']==activation['failed_job_uid'] and oldhost['status']=='FAILED' and oldhost['resources_cleaned']
    assert sha(JOBS/activation['failed_job']/'host.json')==activation['failed_host_sha256']
    oldlog=(JOBS/activation['failed_job']/'worker.log').read_text();assert 'CONFIRM_FAILED TimeoutExpired' in oldlog
    frames=parse(oldlog,'CURRICULUM_CONFIRM_ARTIFACT');assert frames is not None
    for name,text in frames.items():assert (original/name).read_text()==text
    old=read(original/'execution-receipt.json');assert old['status']=='FAILED' and old['training_updates']==0
    assert old['all_endpoints_exact_reload_preflight_passed_before_queries'] and old['confirmation_inference_started']
    assert sha(original/'execution-receipt.json')==activation['original_failed_execution_sha256']
    oldcm=next(o for o in read(JOBS/activation['failed_job']/'objects.json') if o['kind']=='ConfigMap')
    raw=base64.b64decode(oldcm['binaryData']['bundle.json.gz'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==launch['config']['bundle_sha256']==old['bundle_sha256']
    assert hashlib.sha256(oldcm['data']['worker.py'].encode()).hexdigest()==launch['config']['worker_sha256']==old['worker_sha256']
    oldbundle=json.loads(gzip.decompress(raw))
    from run_kali_curriculum_confirmation_tail_20261118 import prediction_manifest
    manifest=prediction_manifest(original);assert manifest==activation['source_prediction_files']
    host=read(JOBS/'miw113-kali-curriculum-confirm-tail-1117/host.json')
    assert host['status']=='SUCCEEDED' and host['resources_cleaned'] and host['gpu']
    assert host['resources']=={'cpu':'500m','memory':'20Gi','ephemeral-storage':'24Gi','nvidia.com/rtxa6000':'1'}
    objects=read(JOBS/host['job']/'objects.json');cm=next(o for o in objects if o['kind']=='ConfigMap');job=next(o for o in objects if o['kind']=='Job')
    assert job['spec']['activeDeadlineSeconds']==8400 and job['spec']['template']['spec']['activeDeadlineSeconds']==6600
    cfg=read(tail/'launch-freeze-private.json')['config'];assert json.loads(cm['data']['config.json'])==cfg
    assert cfg['states']==freeze['states']==launch['config']['states']
    assert cfg['source_prediction_files']==manifest and cfg['original_failed_job_uid']==oldhost['uid']
    assert cfg['deadline_activation_sha256']==sha(folder/'deadline-tail-activation-private.json')
    assert cfg['runtime_seconds']==6600 and cfg['new_optimizer_updates']==0 and cfg['additional_tail_GPU_jobs']==1
    raw=base64.b64decode(cm['binaryData']['bundle.json.gz'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==cfg['bundle_sha256']
    assert hashlib.sha256(cm['data']['worker.py'].encode()).hexdigest()==cfg['worker_sha256']
    bundle=json.loads(gzip.decompress(raw))
    for name,text in oldbundle.items():assert bundle[name]==text,'Frozen original queries/protocol/numerical scripts must remain byte-identical'
    assert not any('references' in n or 'groups-private' in n or 'paired-training' in n for n in bundle)
    assert bundle['scripts/original_confirmation_worker_20261117.py']==oldcm['data']['worker.py']
    oldsource=oldcm['data']['worker.py'];newsource=cm['data']['worker.py']
    marker="        for state in cfg['states']:\n            label=state['label'];cmd="
    assert oldsource[oldsource.index('        import gc,torch'):oldsource.index(marker)]==newsource[newsource.index('        import gc,torch'):newsource.index('        # This conditional worker')]
    for name,digest in read(tail/'runtime-source-freeze-private.json').items():assert sha(tail/'loaded-runtime-source-private'/name)==digest
    assert newsource==(tail/'loaded-runtime-source-private/kali_curriculum_confirmation_tail_worker_20261118.py').read_text()
    for name in ['kali_curriculum_prefix_resume_20261118.py','eval_kali_curriculum_confirmation_resume_20261118.py']:
        assert bundle['scripts/'+name]==(tail/'loaded-runtime-source-private'/name).read_text()
    actual_frames=parse((JOBS/host['job']/'worker.log').read_text(),'CURRICULUM_CONFIRM_ARTIFACT');assert actual_frames is not None
    for name,text in actual_frames.items():assert (tail/'runs'/name).read_text()==text
    actual=read(tail/'runs/execution-receipt.json')
    assert actual['status']=='COMPLETE' and actual['original_job_status']=='FAILED' and actual['training_updates']==0
    assert actual['worker_sha256']==cfg['worker_sha256'] and actual['bundle_sha256']==cfg['bundle_sha256']
    assert actual['selection_sha256']==old['selection_sha256']==freeze['selection_sha256']
    assert actual['deadline_activation_sha256']==cfg['deadline_activation_sha256'] and actual['original_failed_job_uid']==oldhost['uid']
    assert actual['confirmation_cohort_unchanged'] and actual['additional_tail_GPU_jobs']==1 and actual['official_TEST_queries']==0
    assert actual['all_endpoints_exact_reload_preflight_passed_before_queries'] and actual['GPU']==old['GPU']=='NVIDIA RTX A6000'
    adapters={s['label']:s for s in freeze['states'] if s['pointer']['adapter_sha256']}
    assert set(actual['TRAIN_receipt_preflight'])==set(old['TRAIN_receipt_preflight'])==set(adapters)
    for label,state in adapters.items():
        for receipt in [old,actual]:
            check=receipt['TRAIN_receipt_preflight'][label]
            assert check['exact_original_TRAIN_logit_probe_identical'] and check['adapter_sha256']==state['pointer']['adapter_sha256']
    descriptors=actual['resume_descriptor_by_file'];counts={'confirmation':{'retained':0,'new':0,'replayed':0},'already_TRAIN_gap':{'retained':0,'new':0,'replayed':0}}
    expected_names=set();partial_files=copied_files=fresh_files=0
    original_eval=oldbundle['scripts/eval_kali_curriculum_sft_20261117.py'];original_eval_sha=hashlib.sha256(original_eval.encode()).hexdigest()
    assert cfg['original_eval_sha256']==original_eval_sha
    for state in freeze['states']:
        label=state['label'];assert actual['states'][label]['responses']==144 and actual['states'][label]['known_TRAIN_gap_responses']==18
        assert actual['states'][label]['adapter_sha256']==state['pointer']['adapter_sha256']
        for gap in [False,True]:
            filename=label+('-gap-predictions.json' if gap else '-predictions.json');expected_names.add(filename)
            stage=STAGE/'gap-diagnostic' if gap else folder;proto=read(stage/'evaluation-protocol.json');rows=read(stage/'evaluation-inputs-private.json')
            expected=18 if gap else 144;path=tail/'runs'/filename;final=read(path)
            assert (folder/'runs'/filename).read_bytes()==path.read_bytes()
            assert final['status']=='COMPLETE' and validate_prefix(final,rows,proto,state['pointer']['adapter_sha256'],minimum=1)==expected
            assert final['inputs_sha256']==proto['input_sha256'] and final['no_evaluation_gold_loaded']
            if state['pointer']['adapter_sha256']:assert final['reload_audit']['trained_vs_reloaded_probe_identical']
            d=descriptors[filename];meta=manifest.get(filename)
            if meta and meta['status']=='COMPLETE':
                copied_files+=1;assert d['kind']=='COPIED_COMPLETE_BYTE_FOR_BYTE'
                assert sha(path)==meta['sha256'] and path.read_bytes()==(original/filename).read_bytes()
                assert d['retained_responses']==expected and d['new_unique_responses']==d['first_batch_replay_responses']==0
            elif meta:
                partial_files+=1;assert d['kind']=='CONTINUED_ALL_COMMITTED_PREFIX'
                before=read(original/filename);n=meta['responses'];assert final['predictions'][:n]==before['predictions']
                proof=final['prefix_resume'];assert proof['prefix_sha256']==meta['sha256'] and proof['original_eval_sha256']==original_eval_sha
                assert proof['original_generation_block_sha256']==blocks(original_eval)[2]
                assert proof['retained_original_prefix_responses']==d['retained_responses']==n and proof['new_suffix_unique_responses']==d['new_unique_responses']==expected-n
                batch=min(len(rows),proto['batch_size']);assert d['first_batch_replay_responses']==proof['exact_first_batch_replay_responses']==batch
                assert proof['replayed_batch_not_double_counted'] and proof['new_training_updates']==0
                log=(tail/'runs'/(filename+'.log')).read_text();assert 'EXACT_ORIGINAL_FIRST_BATCH_REPLAY_PASS '+str(batch) in log
                assert 'FROZEN_COHORT_FILE_COMPLETE_WITH_EXACT_PREFIX_CONTINUATION' in log
            else:
                fresh_files+=1;assert not(original/filename).exists() and d['kind']=='FIRST_TIME_NO_COMMITTED_PREFIX_FILE'
                assert d['retained_responses']==d['first_batch_replay_responses']==0 and d['new_unique_responses']==expected and d['original_sha256'] is None
                assert 'EVAL_COMPLETE' in (tail/'runs'/(filename+'.log')).read_text()
            if meta:assert d['original_sha256']==meta['sha256']
            c=counts['already_TRAIN_gap' if gap else 'confirmation'];c['retained']+=d['retained_responses'];c['new']+=d['new_unique_responses'];c['replayed']+=d['first_batch_replay_responses']
    assert set(descriptors)==expected_names and set(actual['states'])=={s['label'] for s in freeze['states']}
    assert counts['confirmation']['retained']+counts['confirmation']['new']==576
    assert counts['already_TRAIN_gap']['retained']+counts['already_TRAIN_gap']['new']==72
    composite=read(folder/'runs/execution-receipt.json');expected=dict(actual)
    expected.update(derived_not_emitted_by_original_worker=True,completion_kind='ORIGINAL_FROZEN_COHORT_PLUS_DEADLINE_CONTINUATION',original_job_status='FAILED',
        worker_sha256=old['worker_sha256'],bundle_sha256=old['bundle_sha256'],original_worker_sha256=old['worker_sha256'],actual_tail_worker_sha256=actual['worker_sha256'],
        seconds=old['seconds']+actual['seconds'],confirmation_inference_started=old['confirmation_inference_started'] or actual['confirmation_inference_started'],
        original_execution_sha256=sha(original/'execution-receipt.json'),actual_tail_execution_sha256=sha(tail/'runs/execution-receipt.json'))
    assert composite==expected,'Composite receipt must explicitly identify original failure and actual successful tail'
    return {'status':'SAME_FROZEN_CONFIRMATION_COHORT_AND_ALL_PREFIXES_AUDITED_AFTER_ACTUAL_DEADLINE',
        'original_job_stays_FAILED':True,'same_selected_models_cohort_seeds_numeric_code_and_scoring':True,
        'all_committed_outputs_retained_without_quality_selection':True,'completed_files_copied_byte_for_byte':copied_files,
        'partial_files_first_batch_replayed_identically':partial_files,'files_without_committed_prefix_generated':fresh_files,
        'unique_confirmation_tasks':24,'unique_confirmation_responses':576,'unique_already_TRAIN_gap_responses':72,
        'counts_by_stream':counts,'additional_tail_GPU_jobs':1,'new_training_updates':0,'new_training_candidates':0,
        'confirmation_scores_inspected_before_activation':False,'selection_changed':False,'official_TEST_queries':0,
        'actual_tail_remaining_confirmation_queries_started':actual['new_remaining_confirmation_calls_started'],
        'original_TRAIN_probe_passed_before_original_queries':True,'all_adapter_original_TRAIN_probes_passed_before_tail':True,
        'tail_Pod_seconds':6600,'tail_Job_seconds':8400,'study_GPU_ceiling_seconds_unchanged':93600,
        'activation_sha256':sha(folder/'deadline-tail-activation-private.json'),'audit_source_sha256':sha(__file__)}

if __name__=='__main__':
    result=audit(STAGE/'confirmation');save(STAGE/'confirmation/tail/audit-private.json',result);print(json.dumps(result,indent=2))
