import hashlib,json,tempfile,unittest
from pathlib import Path
from kali_native_scaffold import provision
class ScaffoldTests(unittest.TestCase):
 def fixture(self,r):
  task=r/'task';run=r/'run';task.mkdir();(run/'public').mkdir(parents=True);(run/'private').mkdir()
  files={'README.md':'user task\n','train_client.py':'print("fixed")\n','base_model.json':'{"run_id":"E0"}\n','evaluate.py':'def evaluate(p): return 0\n','train.jsonl':'{"split":"train"}\n'}
  for n,v in files.items():(task/n).write_text(v)
  hashes={n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()};(task/'manifest.json').write_text(json.dumps({'protocol_sha256':'fixed','files':hashes}))
  return run,task,{'protocol_sha256':'fixed','files':files}
 def test_exact_files_private_judge_link_and_zero_step_baseline(self):
  with tempfile.TemporaryDirectory() as d:
   run,task,p=self.fixture(Path(d));r=provision(run,task,p)
   self.assertEqual(set(x.name for x in (run/'public').iterdir()),{'README.md','train_client.py','base_model.json','train.jsonl'})
   self.assertTrue((run/'public/train.jsonl').is_symlink());self.assertEqual((run/'private/evaluate.py').read_bytes(),(task/'evaluate.py').read_bytes());self.assertEqual(json.loads((run/'private/baseline_attempt/train_metrics.json').read_text())['optimizer_steps'],0)
 def test_refuses_started_setup_or_existing_artifacts(self):
  for started in [True,False]:
   with tempfile.TemporaryDirectory() as d:
    run,task,p=self.fixture(Path(d))
    if started:(run/'workspace/search_1/setup_1').mkdir(parents=True)
    else:(run/'public/existing').write_text('keep')
    with self.assertRaises(ValueError):provision(run,task,p)
 def test_rejects_changed_task_and_payload(self):
  for changed in ['task','payload']:
   with tempfile.TemporaryDirectory() as d:
    run,task,p=self.fixture(Path(d))
    if changed=='task':(task/'evaluate.py').write_text('fake')
    else:p['files']['evaluate.py']='fake'
    with self.assertRaises(ValueError):provision(run,task,p)
if __name__=='__main__':unittest.main()
