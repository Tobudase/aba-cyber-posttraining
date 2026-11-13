"""Timeouts must clean an owned Job;replacement UIDs must never be deleted."""
import json,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import kali8b_native_bridge as b
class CleanupTest(unittest.TestCase):
 def run_case(self,same_uid):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'task').mkdir();(root/'task/training_manifest.json').write_text('{}')
   run=root/'P13/run';run.mkdir(parents=True);host=run/'host-private.json';host.write_text(json.dumps({'status':'QUEUED','job_uid':'owned','cleanup_errors':[]}))
   driver=types.SimpleNamespace(OUT=root)
   with patch.object(b,'S',root),patch.object(b.jobs,'S',root),patch.object(b,'freeze_baseline',return_value={'candidate_id':'E0'}),patch.object(b.jobs,'submit'),patch.object(b.jobs,'protocol',return_value={'queue_deadline_seconds':21600}),patch.object(b.jobs,'watch',side_effect=TimeoutError('bounded watch expired')),patch.object(b.jobs,'k',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps({'metadata':{'uid':'owned' if same_uid else 'replaced'}}))),patch.object(b.jobs,'delete_training') as delete:
    broker=b.Broker(driver);broker.current='P13';broker.train('P13');result=json.loads(host.read_text())
    self.assertEqual(result['status'],'FAILED');self.assertIsNone(broker.current);self.assertEqual(broker.states['P13']['status'],'FAILED')
    self.assertEqual(delete.call_count,1 if same_uid else 0)
    self.assertEqual(bool(result['cleanup_errors']),not same_uid)
 def test_timeout_cleans_owned_job(self):self.run_case(True)
 def test_replaced_job_is_preserved(self):self.run_case(False)
if __name__=='__main__':unittest.main()
