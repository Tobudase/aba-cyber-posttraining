"""Complete two real native-trained checkpoints after rejecting an E0 fallback.

This completion run performs ZERO new optimization; original native dispatches
performed32 genuine updates per candidate. Baseline is legal ONLY during Setup.
"""
import hashlib
import json

import kali_curriculum_native_bridge_20261117 as original
from audit_kali_curriculum_complete_20261117 import validate_training,validate_predictions
from kali_execution_jobs_20261114 import OUT as JOBS
from kali_curriculum_protocol_completion_client_20261117 import ARTIFACT_README

STAGE=original.STAGE
ARCHIVE=STAGE/'native-attempt2-invalid-candidate-private'
MODE='EXPLICIT_EXISTING_A1_A2_REVALIDATION'


def protocol_failure():
    proof=json.loads((STAGE/'native-protocol-recovery-before-A1-score-private.json').read_text())
    protocol=json.loads((STAGE/'both-existing-native-completion-protocol-private.json').read_text())
    journal=json.loads((ARCHIVE/'journal-private.json').read_text())
    host=json.loads((ARCHIVE/'host-private.json').read_text())
    freeze=json.loads((ARCHIVE/'native-task-freeze-private.json').read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert proof['status']=='OBSERVED_INVALID_E0_FALLBACK_IN_A1_NATIVE_BRANCH'
    assert protocol['mode']==MODE and protocol['new_optimizer_updates_in_completion_run']=={'A1':0,'A2':0}
    assert not proof['native_timeout_claimed'] and not protocol['terminal_timeout_claimed']
    assert host['status']=='INTERRUPTED_AFTER_INVALID_BASELINE_CANDIDATE' and not host['native_completed']
    assert not host['cleanup_pending'] and not host['cleanup_errors']
    assert digest(ARCHIVE/'actually-loaded-host-driver-private.py')==host['driver_sha256']==freeze['runtime_source_sha256']['run_kali_curriculum_native_20261117.py']
    assert digest(ARCHIVE/'actually-loaded-admission-helper-private.py')==freeze['runtime_source_sha256']['kali_curriculum_admission_retry_20261117.py']
    assert digest(ARCHIVE/'actually-loaded-sft-backend-private.py')==freeze['runtime_source_sha256']['kali_curriculum_sft_jobs_20261117.py']
    assert digest(ARCHIVE/'config.json')==host['config_sha256']==freeze['config_sha256']
    assert journal['run_id']==proof['original_native_run_id'] and journal['task_hashes']==freeze['task_sha256']
    score_source=json.loads((ARCHIVE/'task/setup_payload.json').read_text())['score_py']
    assert journal['grading_proxy_sha256']==hashlib.sha256(score_source.encode()).hexdigest()
    worker=next(a for a in journal['actions'] if a['target']=='search_1/complete_worker_1/worker_1')
    composite=next(a for a in journal['actions'] if a['target']=='search_1/complete_worker_1')
    assert worker['output']['failed'] is False and composite['output']['failed'] is False
    files=journal['scored_outputs'][composite['output']['output_dir']]
    pointer=json.loads(files['final_model/model.json']['text'])
    assert pointer==json.loads((ARCHIVE/'task/base_model.json').read_text())
    assert pointer['candidate_id']=='E0' and pointer['optimizer_steps']==0 and pointer['adapter_sha256'] is None
    return journal,proof,protocol


def prior_candidate(cid):
    assert cid in ['A1','A2']
    journal,proof,protocol=protocol_failure()
    dispatch_file=ARCHIVE/(cid+'-native-dispatch-private.json')
    dispatch=json.loads(dispatch_file.read_text())
    assert dispatch['run_id']==journal['run_id']
    assert hashlib.sha256(dispatch_file.read_bytes()).hexdigest()==proof['original_'+cid+'_dispatch_sha256']
    lr={'A1':5e-6,'A2':2e-5}[cid]
    assert dispatch['request']['candidate_id']==cid and dispatch['request']['learning_rate']==lr
    assert 'search_1/complete_worker_'+str(1 if cid=='A1' else 2)+'/worker_1' in dispatch['active_actions']
    directory=STAGE/'runs'/cid
    recovered=json.loads((directory/'existing-backend-recovery-private.json').read_text())
    assert recovered['status']=='ORIGINAL_NATIVE_DISPATCHED_CANDIDATE_COLLECTED'
    assert recovered['original_native_dispatch_run_id']==journal['run_id']
    assert recovered['new_optimizer_updates_in_recovery']==0 and not recovered['native_run_completion_claimed']
    host=json.loads((JOBS/('miw113-kali-curriculum-sft-'+cid.lower()+'-1117')/'host.json').read_text())
    assert host['uid']==recovered['job_uid'] and host['resources_cleaned']
    if cid=='A2' and recovered.get('evaluation_replay_after_node_eviction'):
        from audit_kali_curriculum_a2_eviction_replay_20261118 import audit
        assert audit()['new_optimizer_updates']==0 and host['status']=='FAILED'
        assert recovered['original_job_stays_failed']
    else:assert host['status']=='SUCCEEDED'
    data=json.loads((STAGE/'paired-training-private.json').read_text());data['protocol']['learning_rate']=lr
    receipt=json.loads((directory/'reasoning/receipt.json').read_text());trace=json.loads((directory/'reasoning/trace.json').read_text())
    execution=json.loads((directory/'execution-receipt.json').read_text());launch=json.loads((directory/'launch-freeze-private.json').read_text())
    assert execution['status']=='COMPLETE' and execution['worker_sha256']==launch['config']['worker_sha256']
    assert execution['bundle_sha256']==launch['config']['bundle_sha256'] and execution['official_TEST_queries']==execution['confirmation_queries']==0
    validate_training(data,'reasoning',receipt,trace,hashlib.sha256((json.dumps(data)+'\n').encode()).hexdigest(),lr)
    assert receipt['initial_adapter_sha256']==json.loads((STAGE/'runs/pair/reasoning/receipt.json').read_text())['initial_adapter_sha256']
    validate_predictions(json.loads((directory/'reasoning-predictions.json').read_text()),
        json.loads((STAGE/'evaluation-inputs-private.json').read_text()),json.loads((STAGE/'evaluation-protocol.json').read_text()),receipt['adapter_sha256'])
    pointer=json.loads((directory/'adapter-pointer-private.json').read_text())['pointer']
    assert pointer==recovered['adapter_pointer'] and pointer['adapter_sha256']==receipt['adapter_sha256']
    training_receipt={'optimizer_steps':32,'nonzero_gradient_steps':32,'learning_rate':lr,'reload_probe_identical':True,
        'adapter_sha256':receipt['adapter_sha256'],'training_data_sha256':receipt['data_sha256'],
        'new_optimizer_steps_this_run':0,'new_optimizer_steps_in_current_native_run':0,
        'original_native_dispatch_optimizer_steps':32,'total_optimizer_steps_in_this_study':32,
        'original_native_run_id_sha256':hashlib.sha256(journal['run_id'].encode()).hexdigest()}
    provenance={'execution':'REVALIDATION_OF_ORIGINAL_NATIVE_TRAINING','new_optimizer_steps_this_run':0,
        'reused_candidate_training':True,'new_optimizer_steps_in_study':32,'original_native_run_id':journal['run_id'],
        'original_native_dispatch_sha256':proof['original_'+cid+'_dispatch_sha256'],
        'original_run_protocol_invalid':True,'original_A1_framework_worker_failed':False}
    return {'status':'REAL_GPU_TRAINING_COMPLETE','candidate_id':cid,'pointer':pointer,
            'training_receipt':training_receipt,'training_provenance':provenance}


class CompletionBroker(original.Broker):
    def __init__(self,driver):
        super().__init__(driver)
        self.priors={cid:prior_candidate(cid) for cid in ['A1','A2']}
        self.client_sha256=hashlib.sha256((driver.OUT/'task/train_client.py').read_bytes()).hexdigest()
        self.readme_sha256=hashlib.sha256(ARTIFACT_README.encode()).hexdigest()

    def call(self,req):
        if req.get('action')=='score_artifact':
            assert set(req)=={'action','pointer','artifact_proof'}
            pointer=req['pointer']
            if pointer!=self.baseline['pointer']:
                cid=pointer['candidate_id'];assert cid in self.started
                proof=req['artifact_proof']
                assert proof['client_sha256']==self.client_sha256,'Candidate run.py must be the unmodified certified client'
                assert proof['train_metrics']==self.priors[cid]['training_receipt'],'Candidate metrics must be the actual prior-training/zero-current receipt'
                assert proof['readme_sha256']==self.readme_sha256,'Do not relabel existing checkpoints as fresh training'
            return self.call({'action':'score','pointer':pointer})
        if req.get('action')=='score' and req.get('pointer')==self.baseline['pointer']:
            journal=self.driver.collect_journal()
            candidate_phase=any('/complete_worker_' in target for target in journal['started_actions'])
            assert not candidate_phase and not self.started,'E0 is valid only during pre-candidate Setup verification; a search candidate must return its actual certified adapter'
        if req.get('action')=='health' and set(req)=={'action'}:
            return {'status':'READY','existing_verified_checkpoints':['A1','A2'],
                'fixed_recipes':{'A1':5e-6,'A2':2e-5},'new_updates_current_run':{'A1':0,'A2':0},
                'original_native_dispatch_updates':{'A1':32,'A2':32},'GPU_jobs_this_run':0,'official_TEST_rows':0}
        if req.get('action')=='train_data':
            raise AssertionError('Completion only: no training or data export is permitted')
        if req.get('action')=='submit':
            assert set(req)=={'action','candidate_id','learning_rate','manifest_sha256'}
            cid=req['candidate_id'];assert cid in ['A1','A2'] and req['learning_rate']=={'A1':5e-6,'A2':2e-5}[cid]
            with self.lock:
                assert req['manifest_sha256']==self.manifest_sha256
                assert self.current is None and cid not in self.started
                assert cid==['A1','A2'][len(self.started)],'Fixed original proposal order'
                journal=self.driver.collect_journal()
                assert any(a['target'].endswith('/setup_1') and a['output'].get('failed') is False for a in journal['actions'])
                active=set(journal['started_actions'])-{a['target'] for a in journal['actions']}
                wanted='search_1/complete_worker_'+str(1 if cid=='A1' else 2)+'/worker_1'
                assert wanted in active,'Only the assigned active native Worker may load this candidate'
                assert journal['grading_proxy_sha256']==self.grading_proxy_sha256
                self.started.append(cid);self.recipes[cid]=req['learning_rate'];self.states[cid]=self.priors[cid]
                record={'run_id':journal['run_id'],'active_actions':sorted(active),'request':req,
                    'dispatch_kind':'EXPLICIT_EXISTING_CHECKPOINT_REVALIDATION','new_optimizer_steps_this_run':0,
                    'original_native_run_id':self.priors[cid]['training_provenance']['original_native_run_id']}
                (self.driver.OUT/(cid+'-native-dispatch-private.json')).write_text(json.dumps(record,indent=2)+'\n')
            return {'status':'EXISTING_NATIVE_CHECKPOINT_LOADED','candidate_id':cid,'new_updates_budget':0}
        result=super().call(req)
        if req.get('action')=='score':
            cid=req['pointer']['candidate_id']
            result['components'].update(new_optimizer_steps_in_current_native_run=0,
                original_native_dispatch_optimizer_steps=32 if cid in ['A1','A2'] else 0)
        return result


def bridge(driver,stop):
    import kali_qwen_native_bridge_20261115 as transport
    transport.Broker=CompletionBroker
    return transport.bridge(driver,stop)
