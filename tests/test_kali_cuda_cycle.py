"""Guard real GPU allocation and evaluation boundaries without allocating GPUs."""
import copy,json,sys,unittest,tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_cuda_jobs import ROOT,build,canonical,frozen,sha,verified_receipt
from kali_cuda_broker import Broker
LOCAL={'context':'test','namespace':'test','PVC':'test','nodeSelector':{'nvidia.com/gpu.product':'NVIDIA-A10'}}

class CudaBoundaryTests(unittest.TestCase):
 def test_frozen_rows_and_input_projection(self):
  p,i=frozen();self.assertEqual(128,len(i['train_rows']));self.assertEqual(108,len(i['inference_rows']))
  self.assertFalse(p['confirmation_enabled']);self.assertFalse(p['official_test_enabled'])
  for r in i['inference_rows']:self.assertEqual({'id','messages','prompt_sha256','set'},set(r))
  self.assertEqual({'domain','retention'},{r['set'] for r in i['inference_rows']})
 def test_no_arbitrary_model_code_or_baseline_training(self):
  for run,phase in [('E0','train'),('E99','train'),('E2','shell')]:
   with self.assertRaises(ValueError):build(run,phase)
 def test_one_gpu_finite_no_token_and_no_reserved_tolerations(self):
  _,cm,j=build('E2','train',LOCAL);s=j['spec']['template']['spec'];c=s['containers'][0]
  self.assertEqual('1',c['resources']['requests']['nvidia.com/gpu']);self.assertEqual(c['resources']['requests'],c['resources']['limits'])
  self.assertEqual(1800,j['spec']['activeDeadlineSeconds']);self.assertEqual(0,j['spec']['backoffLimit'])
  self.assertFalse(s['automountServiceAccountToken']);self.assertNotIn('nodeName',s);self.assertNotIn('tolerations',s);self.assertNotIn('priorityClassName',s)
  self.assertEqual(['python','-u','/input/runner.py'],c['command'])
  payload=json.loads(cm['data']['payload.json']);self.assertNotIn('inference_rows',payload)
 def test_inference_has_no_targets(self):
  _,cm,_=build('E0','infer',LOCAL);payload=json.loads(cm['data']['payload.json']);self.assertNotIn('train_rows',payload)
  self.assertFalse(any('target' in r or 'native_label' in r for r in payload['inference_rows']))
 def test_broker_rejects_arbitrary_recipes_or_commands_before_execution(self):
  b=Broker()
  for r in [{'action':'train','learning_rate':1},{'action':'shell'},{'command':'id'},{'action':'candidate_score','path':'/tmp/x'}]:
   with patch('kali_cuda_broker.execute') as execute:
    with self.assertRaises(ValueError):b.call(r)
    execute.assert_not_called()
 def test_health_does_not_allocate(self):
  with patch('kali_cuda_broker.execute') as execute:
   r=Broker().call({'action':'health'});self.assertEqual('READY',r['status']);execute.assert_not_called()
  p,_=frozen()
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp);receipt={'status':'COMPLETE','protocol_sha256':sha(canonical(p)),'runner_sha256':p['runner_sha256'],'phase':'train'}
   (folder/'receipt.json').write_text(json.dumps(receipt));(folder/'verified.json').write_text(json.dumps({'status':'HOST_COLLECTION_VERIFIED','job_succeeded':True,'receipt_sha256':'forged'}))
   with self.assertRaises(ValueError):verified_receipt(folder,p)

if __name__=='__main__':unittest.main()
