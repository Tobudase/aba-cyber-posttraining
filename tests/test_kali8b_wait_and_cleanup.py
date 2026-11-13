"""Regressions for the observed150-turn exhaustion and interrupted cleanup."""
import importlib.util,inspect,json,math,pathlib,sys,tempfile,threading,types,unittest
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import kali8b_native_client as client
class WaitTest(unittest.TestCase):
 def test_six_hour_job_fits_native150turn_limit(self):
  seconds=inspect.signature(client.wait_candidate).parameters['seconds'].default
  self.assertGreater(math.ceil(22200/55),150)
  self.assertLess(math.ceil(22200/seconds)+30,150)
 def test_python_wait_polls_without_returning_each_modelturn(self):
  clock=[0];calls=[]
  def request(req,timeout):calls.append(req);return {'status':'IN_PROGRESS','candidate_id':'P14'}
  with patch.object(client.time,'monotonic',side_effect=lambda:clock[0]),patch.object(client.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch.object(client,'call',side_effect=request):
   result=client.wait_candidate('P14')
  self.assertEqual(clock[0],420);self.assertEqual(result['status'],'IN_PROGRESS');self.assertTrue(all(x['action']=='status' for x in calls));self.assertGreater(len(calls),5)
 def test_ready_arm_returns_immediately(self):
  with patch.object(client,'call',return_value={'status':'REAL_GPU_TRAINING_COMPLETE'}),patch.object(client.time,'sleep') as sleep:
   self.assertEqual(client.wait_candidate('P13')['status'],'REAL_GPU_TRAINING_COMPLETE');sleep.assert_not_called()
 def test_delayed_broker_does_not_create_false_timeout_at_wait_deadline(self):
  clock=[0]
  def request(req,timeout):
   if timeout<3:clock[0]+=timeout;raise TimeoutError('Broker requires3seconds')
   clock[0]+=3;return {'status':'IN_PROGRESS','candidate_id':'P14'}
  with patch.object(client.time,'monotonic',side_effect=lambda:clock[0]),patch.object(client.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch.object(client,'call',side_effect=request):result=client.wait_candidate('P14')
  self.assertEqual(clock[0],420);self.assertEqual(result['status'],'IN_PROGRESS')
class CleanupTest(unittest.TestCase):
 def test_join_interrupt_still_cleans_owned_vm_and_saves_final_state(self):
  spec=importlib.util.spec_from_file_location('cleanup_test_driver',R/'scripts/run-kali8b-native-study-20261112.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as tmp:
   known=pathlib.Path(tmp)/'known';known.write_text('dummy');record={'status':'FAILED','cleanup_errors':[]};stop=threading.Event();thread=types.SimpleNamespace(join=lambda **kw:(_ for _ in ()).throw(KeyboardInterrupt()))
   with patch.object(m,'KNOWN',known),patch.object(m,'call',return_value=types.SimpleNamespace(returncode=0,stderr='')) as call,patch.object(m,'save') as save:
    with self.assertRaises(KeyboardInterrupt):m.cleanup(record,True,stop,thread)
    self.assertEqual(call.call_count,2);save.assert_called_once();self.assertFalse(record['cleanup_pending']);self.assertTrue(stop.is_set());self.assertFalse(known.exists())
 def test_failfast_does_not_interrupt_native_finally(self):
  spec=importlib.util.spec_from_file_location('failfast_test',R/'scripts/stop-kali8b-on-infrastructure-failure-20261113.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);o=root/'out';(o/'monitor-private').mkdir(parents=True);rid='a'*32
   (o/'host-private.json').write_text(json.dumps({'status':'NATIVE_RUNNING','native_unit_state':'inactive'}));(o/'monitor-private/journal-private.json').write_text(json.dumps({'run_id':rid,'head':{'result':'completed'}}))
   with patch.object(g,'O',o),patch.object(g,'report',o/'report.json'),patch.object(sys,'argv',['guard','--expected-run-id',rid]),patch.object(g.os,'kill') as kill:g.main();kill.assert_not_called()
   self.assertEqual(json.loads((o/'report.json').read_text())['status'],'NATIVE_ALREADY_ENDING_NO_SIGNAL')
if __name__=='__main__':unittest.main()
