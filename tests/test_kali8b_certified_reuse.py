"""Synthetic metadata fixtures only;never represent these as model training."""
import copy,hashlib,json,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import kali8b_native_reuse as reuse
import kali8b_native_bridge as bridge
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def fixture(root):
 s=root/'study';a=root/'archive';run=s/'P13/run';adapter=run/'adapter-bundle-private/adapter';adapter.mkdir(parents=True);(adapter/'adapter_model.safetensors').write_bytes(b'dummy unit test bytes,not tensors')
 write(s/'P13/protocol-private.json',{'test':'synthetic'});write(s/'grading-lock-private.json',{'test':'synthetic'})
 pointer={'candidate_id':'P13','adapter_sha256':sha(adapter/'adapter_model.safetensors'),'grading_lock_sha256':sha(s/'grading-lock-private.json')};receipt={'optimizer_steps':733,'nonzero_gradient_steps':733,'supervised_token_presentations':17439,'adapter_sha256':pointer['adapter_sha256'],'protocol_sha256':sha(s/'P13/protocol-private.json')}
 write(run/'host-private.json',{'status':'COLLECTED','cleanup_errors':[]});write(run/'receipt-private.json',receipt);write(run/'scores-private.json',{'ABA_score':-1,'sealed_final64_used':False})
 texts={'run.py':'# synthetic fixture\n','README.md':'dummy\n','train_metrics.json':json.dumps(receipt),'final_model/model.json':json.dumps(pointer)};files={n:{'text':v,'sha256':hashlib.sha256(v.encode()).hexdigest()} for n,v in texts.items()}
 journal={'run_id':'original-native','head':{'result':'completed'},'actions':[{'target':'search_1','output':{'output':{'output_dir':'/full','score':-1}}}],'scored_outputs':{'/full':files}}
 write(a/'journal-private.json',journal);write(a/'native-artifacts-private.json',{'exit':{'returncode':0},'files':{'/deliverable/'+n:v for n,v in files.items()}});write(a/'native-task-freeze-private.json',{'runtime_source_sha256':{'kali8b_native_client.py':files['run.py']['sha256']}})
 proof={'status':'CERTIFIED_PREVIOUS_NATIVE_TRAIN_SCORE_FINALIZER_P13','candidate_id':'P13','new_optimizer_steps_on_reuse':0,'source_journal_sha256':sha(a/'journal-private.json'),'source_artifacts_sha256':sha(a/'native-artifacts-private.json'),'source_native_run_id':journal['run_id'],'deliverable_sha256':{n:v['sha256'] for n,v in files.items()},'protocol_sha256':receipt['protocol_sha256'],'adapter_sha256':receipt['adapter_sha256'],'native_DEV_score':-1};write(s/'P13-certified-native-reuse-private.json',proof)
 return s,a
class ReuseTest(unittest.TestCase):
 def test_prior_native_proof_preserves_zero_new_update_lineage(self):
  with tempfile.TemporaryDirectory() as tmp:
   s,a=fixture(pathlib.Path(tmp));state=reuse.certified_reuse(s,a);self.assertEqual(state['training_provenance']['new_optimizer_steps_this_run'],0);self.assertEqual(state['training_receipt']['optimizer_steps'],733);self.assertTrue(state['training_receipt']['execution_provenance']['reuse_is_not_new_training'])
 def test_changed_adapter_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   s,a=fixture(pathlib.Path(tmp));(s/'P13/run/adapter-bundle-private/adapter/adapter_model.safetensors').write_bytes(b'changed')
   with self.assertRaises(AssertionError):reuse.certified_reuse(s,a)
 def test_changed_source_journal_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   s,a=fixture(pathlib.Path(tmp));(a/'journal-private.json').write_text('{}')
   with self.assertRaises(AssertionError):reuse.certified_reuse(s,a)
 def test_broker_cache_hit_never_submits_gpu_or_counts_new_updates(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s,a=fixture(root);state=reuse.certified_reuse(s,a);out=root/'out';write(out/'task/training_manifest.json',{'certified_cache_reuse':{'P13':state['training_provenance']}})
   journal={'run_id':'new-native','actions':[{'target':'search_1/setup_1','output':{'failed':False}}],'started_actions':['search_1/setup_1','search_1/worker_1']};driver=types.SimpleNamespace(OUT=out,collect_journal=lambda:journal)
   with patch.object(bridge,'S',s),patch.object(bridge,'freeze_baseline',return_value={'candidate_id':'E0'}),patch.object(bridge,'certified_reuse',side_effect=lambda study:reuse.certified_reuse(study,a)),patch.object(bridge.jobs,'submit') as submit:
    b=bridge.Broker(driver);request={'action':'submit','candidate_id':'P13','manifest_sha256':sha(out/'task/training_manifest.json')};answer=b.call(request);self.assertEqual(answer['status'],'CERTIFIED_PRIOR_NATIVE_ARM_REUSED');submit.assert_not_called();self.assertEqual(b.states['P13']['training_provenance']['new_optimizer_steps_this_run'],0)
    with self.assertRaises(AssertionError):b.call(request)
if __name__=='__main__':unittest.main()
