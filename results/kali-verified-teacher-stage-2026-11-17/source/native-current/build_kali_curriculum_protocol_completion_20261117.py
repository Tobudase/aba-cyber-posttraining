"""Fresh native validation of both already trained original native candidates."""
import json
from pathlib import Path

from build_kali_curriculum_native_20261117 import build_task as original_build
from prepare_kali_verified_curriculum_20261117 import ROOT,save,sha
from kali_curriculum_sft_jobs_20261117 import STAGE
from kali_curriculum_protocol_completion_bridge_20261117 import MODE


def build_task(out):
    from kali_curriculum_protocol_completion_bridge_20261117 import prior_candidate
    priors={cid:prior_candidate(cid) for cid in ['A1','A2']}
    out=Path(out);config=original_build(out);task=out/'task'
    manifest=json.loads((task/'training_manifest.json').read_text())
    manifest.update(execution_mode=MODE,learning_rates=[5e-6,2e-5],fixed_recipes={'A1':5e-6,'A2':2e-5},
        current_run_updates_by_candidate={'A1':0,'A2':0},max_new_updates_total=0,
        original_native_dispatch_updates={'A1':32,'A2':32},total_new_study_updates=64,
        existing_pointers={cid:p['pointer'] for cid,p in priors.items()},
        recovery_reason='Original first native branch returned/scored E0 while actual A1 backend was evaluating; original cycle is protocol invalid, not a terminal timeout.',
        no_new_GPU_jobs=True,no_new_training=True)
    (task/'training_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (task/'train_client.py').write_bytes((ROOT/'scripts/kali_curriculum_protocol_completion_client_20261117.py').read_bytes())
    readme='''# Native protocol completion: two EXISTING actual trained candidates
The original genuine native Designer/Workers dispatched A1 lr5e-6 and A2 lr2e-5.
Each REALLY trained32updates from original Qwen3-8B and finished the SAME624
frozen evaluations, exact adapter reload and host scoring. Original branchA1
incorrectly delivered the E0 pointer while its backend was still evaluating.
That branch is protocol INVALID despite a framework-success return. It was
NOT a recorded terminal timeout. Original source/journal/checkpoints survive.

This NEW run VALIDATES BOTH EXISTING trained checkpoints. There are ZERO new
optimizer updates and ZERO GPU Jobs in this run. Original native updates32+32
remain64 for the whole study. Never relabel reuse as fresh training.

Setup FIRST read setup_scaffold.md and use prepare_contract.py. The E0 baseline
is legal ONLY during Setup. Do not train, export data or invent a judge.
Designer read ONLY this README and training_manifest.json; propose exactly TWO
fixed plans IN ORDER: A1(existing,lr5e-6), A2(existing,lr2e-5), requested_gpus=0.
No changes to recipe, data, validation or decoding; no additional experiment.

Worker use ONLY the UNMODIFIED train_client.py to create artifacts/full.
Set DATA_DIR=PUBLIC OUTPUT_DIR=artifacts/full. Submit assigned ID ONCE with its
fixed --lr; response is EXISTING_NATIVE_CHECKPOINT_LOADED. A wait call returns
REAL_GPU_TRAINING_COMPLETE, meaning32original native-dispatched updates and0new
updates in this completion run. If transport is unavailable, repeat ONE long
wait --seconds 420 in Bash timeout600000; it is not evidence that no training ran.
The CPU controller intentionally has0visibleGPUs; original GPU jobs were external.
Finalize assigned ID using train_client.py, inspect actual four files, and submit:
final_model/model.json,train_metrics.json,run.py,README.md. Never hand-write/copy
baseline artifacts. Do not read setup_payload.json or base_model.json to make a
candidate. Host rejects E0 after Setup and rejects uncertified/incorrect pointers.
No training, model downloads, installations, data exports, grading or new recipes.
Use revisions=[] if permitted; any schema-required revision is metadata only,
not a new experiment. The search is capped at the same two existing candidates.

Finalizer copies selected four files byte-for-byte. Same host-only DEV24/old64
strict/partial metric, both-mode per-seed retention/reliability gates. E0 can
remain the external retained model. Confirmation and official TEST stay hidden.
This is an internal pilot, not official KaliBench accuracy or broad ABA search.
'''
    (task/'README.md').write_text(readme)
    payload=json.loads((task/'setup_payload.json').read_text());payload['readme']=readme
    payload['score_py']='''import hashlib,json,urllib.request
from pathlib import Path
def score(output_dir):
 root=Path(output_dir);pointer=json.loads((root/'final_model/model.json').read_text())
 proof={'client_sha256':hashlib.sha256((root/'run.py').read_bytes()).hexdigest(),
        'train_metrics':json.loads((root/'train_metrics.json').read_text()),
        'readme_sha256':hashlib.sha256((root/'README.md').read_bytes()).hexdigest()}
 req=urllib.request.Request('http://127.0.0.1:29847/candidate',data=json.dumps({'action':'score_artifact','pointer':pointer,'artifact_proof':proof}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=100) as response:result=json.load(response)
 assert 'score' in result and result.get('status')!='FAILED'
 return result
'''
    (task/'setup_payload.json').write_text(json.dumps(payload,indent=2)+'\n')
    config['run']['budget']['wall_clock_minutes']=45
    config['llm']['system_instructions'].update(
        designer='Read ONLY README.md and training_manifest.json. Propose exactly two existing-checkpoint validation plans IN ORDER:A1lr5e-6,A2lr2e-5, requested_gpus=0. ZERO new training/GPUs; original32updates each. No recipe changes/research.',
        worker='Use unmodified train_client.py ONLY. DATA_DIR=PUBLIC OUTPUT_DIR=artifacts/full. Submit assigned fixedID/lr once; wait then finalize certified EXISTING checkpoint. Both adapters have32original updates and0newthisrun. Never hand-write artifacts or copy E0. E0 forbidden afterSetup. No training, dataexport, installs or judge access.',
        finalizer='Copy selected final_model/model.json,train_metrics.json,run.py,README.md byte-for-byte and submit immediately. Both candidates are real existing trained adapters; this run adds0updates.')
    for unit in config['work_units']:
        if unit['budget']['kind']=='pipeline':continue
        unit['budget']['minutes']=15 if unit['name'] in ['worker','training','setup'] else 10 if unit['name']=='finalizer' else 5
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    freeze=json.loads((out/'native-task-freeze-private.json').read_text())
    freeze.update(config_sha256=sha(out/'config.json'),task_sha256={p.name:sha(p) for p in task.iterdir()},
        execution_mode=MODE,new_updates_current_run=0,new_updates_prior_native_dispatch=64,
        recovery_protocol_sha256=sha(STAGE/'both-existing-native-completion-protocol-private.json'),
        protocol_failure_proof_sha256=sha(STAGE/'native-protocol-recovery-before-A1-score-private.json'))
    for name in ['run_kali_curriculum_protocol_completion_20261117.py','build_kali_curriculum_protocol_completion_20261117.py',
                 'kali_curriculum_protocol_completion_bridge_20261117.py','kali_curriculum_protocol_completion_client_20261117.py',
                 'collect_kali_curriculum_existing_candidate_20261117.py','kali_curriculum_native_facts_20261117.py',
                 'audit_kali_curriculum_complete_20261117.py','kali_curriculum_gpu_budget_20261117.py',
                 'audit_kali_curriculum_a2_eviction_replay_20261118.py']:
        freeze['runtime_source_sha256'][name]=sha(ROOT/'scripts'/name)
    save(out/'native-task-freeze-private.json',freeze)
    return config
