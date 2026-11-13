"""A valid queued Job must retain its declared execution+collection budget."""
import gzip,importlib.util,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import kali8b_native_bridge as bridge
class BudgetTest(unittest.TestCase):
 def test_late_queue_and_copy_do_not_exhaust_shorter_host_watch(self):
  # The real failed case:135min queue+25min copy+~30min compute >180min.
  full=135*60+25*60+30*60;watch=bridge.backend_watch_seconds({'queue_deadline_seconds':21600})
  self.assertGreater(full,3*3600);self.assertGreater(watch,full);self.assertGreaterEqual(watch,21600+600)
 def test_real_broker_uses_job_budget(self):
  import types
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);(root/'task').mkdir();(root/'task/training_manifest.json').write_text('{}');run=root/'P13/run';run.mkdir(parents=True);(run/'host-private.json').write_text(json.dumps({'status':'QUEUED','job_uid':'owned','cleanup_errors':[]}))
   with patch.object(bridge,'S',root),patch.object(bridge.jobs,'S',root),patch.object(bridge,'freeze_baseline',return_value={'candidate_id':'E0'}),patch.object(bridge.jobs,'submit'),patch.object(bridge.jobs,'protocol',return_value={'queue_deadline_seconds':21600}),patch.object(bridge.jobs,'watch',side_effect=TimeoutError('test timeout')) as watch,patch.object(bridge.jobs,'k',return_value=types.SimpleNamespace(returncode=1,stdout='',stderr='NotFound')):
    b=bridge.Broker(types.SimpleNamespace(OUT=root));b.train('P13');self.assertEqual(watch.call_args.kwargs['seconds'],22200)
 def test_real_builder_role_and_root_budgets_cover_actual_jobs(self):
  p=R/'scripts/build-kali8b-native-study.py';s=importlib.util.spec_from_file_location('real_builder_budget_test',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as tmp:
   # Only generated dummy records are needed to exercise the actual builder.
   # The public regression test must not depend on private study data or keys.
   fixture=pathlib.Path(tmp)/'fixture';fixture.mkdir();(fixture/'scripts').symlink_to(R/'scripts',target_is_directory=True)
   study=fixture/'study';study.mkdir();output=fixture/'out';output.mkdir()
   for cid in ['P13','P14']:
    arm=study/cid;arm.mkdir();(arm/'protocol-private.json').write_text(json.dumps({'optimizer':{'lr':1e-5}}))
   (study/'P13/payload-private.json.gz').write_bytes(gzip.compress(json.dumps({'train_rows':[{'id':'dummy','input_ids':[1,2]}]}).encode()))
   (study/'protocol-freeze-private.json').write_text(json.dumps({'protocol_sha256':{c:'test' for c in ['P11','P12','P13','P14']}}))
   data=fixture/'data/benchkit/kali-fixture-train-v2-2026-11-12';data.mkdir(parents=True)
   rows=[{'id':f'kali-fixture-{tool}-{i}','group_id':'dummy','messages':[{'role':'user','content':'dummy'}],'target':'dummy','quality':'test_fixture_only'} for tool in ['hardlink','virtualenv','dnstwist','pyi-makespec'] for i in range(2)]
   (data/'train.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   baseline={'pointer':{'model_id':'dummy','model_revision':'dummy','optimizer_steps':0}}
   with patch.object(m,'ROOT',fixture),patch.object(m,'S',study),patch.object(m,'freeze_baseline',return_value=baseline):c=m.build(output)
   budgets={x['name']:x['budget'].get('minutes') for x in c['work_units']}
   self.assertGreaterEqual(budgets['worker'],375);self.assertGreaterEqual(budgets['training'],370)
   overhead=budgets['setup']+budgets['setup_review']+budgets['designer']+budgets['designer_review']+2*budgets['worker_review']+3*budgets['score_program']+budgets['finalizer']
   self.assertGreaterEqual(c['run']['budget']['wall_clock_minutes'],2*budgets['worker']+overhead)
   supervisor=(R/'scripts/kali8b_native_supervisor.py').read_text();self.assertIn('timeout=61200',supervisor);self.assertLess(c['run']['budget']['wall_clock_minutes']*60+1800,61200)
if __name__=='__main__':unittest.main()
