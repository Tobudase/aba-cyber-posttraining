import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_qwen_aba_client_v2_20261115 import wait_status
class Deadline(unittest.TestCase):
 def test_zero_seconds_is_one_normal_length_status_request(self):
  seen=[]
  def call(req,timeout):seen.append((req,timeout));return {'status':'IN_PROGRESS'}
  self.assertEqual(wait_status('A2',0,call_fn=call)['status'],'IN_PROGRESS');self.assertEqual(len(seen),1);self.assertEqual(seen[0][1],30)
 def test_deadline_socket_timeout_returns_last_progress_without_false_completion(self):
  state={'now':0,'calls':0};seen=[]
  def call(req,timeout):
   seen.append(req);state['calls']+=1
   if state['calls']==1:state['now']=8;return {'status':'IN_PROGRESS'}
   state['now']=10;raise TimeoutError('observed edge timeout')
  result=wait_status('A1',10,call_fn=call,clock=lambda:state['now'],sleeper=lambda n:state.update(now=state['now']+n),poll_seconds=1)
  self.assertEqual(result,{'status':'IN_PROGRESS'});self.assertTrue(all(r['action']=='status' for r in seen))
 def test_real_completion_returns_immediately(self):
  self.assertEqual(wait_status('A1',420,call_fn=lambda req,timeout:{'status':'REAL_GPU_TRAINING_COMPLETE'})['status'],'REAL_GPU_TRAINING_COMPLETE')
 def test_backend_failure_is_not_swallowed_as_progress(self):
  def fail(req,timeout):raise RuntimeError('Backend failed')
  with self.assertRaises(RuntimeError):wait_status('A1',420,call_fn=fail)
if __name__=='__main__':unittest.main()
