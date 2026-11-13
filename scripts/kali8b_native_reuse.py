"""Explicit replay of a prior real native candidate; never count new updates."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12'
ARCHIVE=ROOT/'docs/verification/kali8b-native-v64-20261112-attempt13-turn-limit-P13-collected-private'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def certified_reuse(study=S,archive=ARCHIVE):
 study,archive=Path(study),Path(archive);proof_path=study/'P13-certified-native-reuse-private.json';proof=json.loads(proof_path.read_text());assert proof['status']=='CERTIFIED_PREVIOUS_NATIVE_TRAIN_SCORE_FINALIZER_P13' and proof['candidate_id']=='P13' and proof['new_optimizer_steps_on_reuse']==0
 journal=json.loads((archive/'journal-private.json').read_text());art=json.loads((archive/'native-artifacts-private.json').read_text());freeze=json.loads((archive/'native-task-freeze-private.json').read_text())
 assert sha(archive/'journal-private.json')==proof['source_journal_sha256'] and sha(archive/'native-artifacts-private.json')==proof['source_artifacts_sha256']
 assert journal['run_id']==proof['source_native_run_id'] and journal['head']['result']=='completed' and art['exit']['returncode']==0
 selected=next(a['output']['output'] for a in reversed(journal['actions']) if a['target']=='search_1');files=journal['scored_outputs'][selected['output_dir']]
 for name,expected in proof['deliverable_sha256'].items():
  matching=[v for path,v in art['files'].items() if path.endswith('/deliverable/'+name)];assert len(matching)==1 and matching[0]==files[name] and files[name]['sha256']==expected;assert hashlib.sha256(files[name]['text'].encode()).hexdigest()==expected
 assert set(proof['deliverable_sha256'])=={'run.py','README.md','train_metrics.json','final_model/model.json'}
 assert files['run.py']['sha256']==freeze['runtime_source_sha256']['kali8b_native_client.py']
 run=study/'P13/run';host=json.loads((run/'host-private.json').read_text());receipt=json.loads((run/'receipt-private.json').read_text());score=json.loads((run/'scores-private.json').read_text());pointer=json.loads(files['final_model/model.json']['text'])
 assert host['status']=='COLLECTED' and not host['cleanup_errors'];assert receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==733 and receipt['supervised_token_presentations']==17439
 assert receipt['protocol_sha256']==proof['protocol_sha256']==sha(study/'P13/protocol-private.json');assert pointer['candidate_id']=='P13' and pointer['adapter_sha256']==receipt['adapter_sha256']==proof['adapter_sha256']==sha(run/'adapter-bundle-private/adapter/adapter_model.safetensors')
 assert pointer['grading_lock_sha256']==sha(study/'grading-lock-private.json');assert selected['score']==score['ABA_score']==proof['native_DEV_score'];assert not score['sealed_final64_used'] and not(study/'confirmation').exists()
 provenance={'execution':'CERTIFIED_PREVIOUS_NATIVE_ARM_REUSED','source_native_run_id':proof['source_native_run_id'],'source_proof_sha256':sha(proof_path),'original_optimizer_steps':733,'new_optimizer_steps_this_run':0,'reuse_is_not_new_training':True}
 view=copy.deepcopy(receipt);view['execution_provenance']=provenance
 return {'status':'REAL_GPU_TRAINING_COMPLETE','candidate_id':'P13','pointer':pointer,'training_receipt':view,'training_provenance':provenance,'official_TEST_rows':0}
