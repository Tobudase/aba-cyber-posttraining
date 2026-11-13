"""Do not consume confirmation if a branch was only dispatched,not scored."""
import importlib.util,json,pathlib,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('confirmation_score_check',R/'scripts/run-kali8b-confirm-after-native-20261112.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class NativeScoreAuditTest(unittest.TestCase):
 def case(self,missing=None,bad_pointer=False):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s=root/'study';n=root/'native';s.mkdir();n.mkdir();(s/'native-selection-private.json').write_text(json.dumps({'native_run_id':'new'}));j={'run_id':'new','head':{'result':'completed'},'actions':[],'program_attempts':[],'scored_outputs':{}}
   for c in ['P13','P14']:
    run=s/c/'run';run.mkdir(parents=True);(run/'receipt-private.json').write_text(json.dumps({'adapter_sha256':c,'optimizer_steps':733,'nonzero_gradient_steps':733}));(run/'scores-private.json').write_text(json.dumps({'ABA_score':-1}))
    if c==missing:continue
    directory='/'+c;target='search_1/'+c+'/score_program_1';pointer={'candidate_id':c,'adapter_sha256':'incorrect' if bad_pointer else c};j['scored_outputs'][directory]={'final_model/model.json':{'text':json.dumps(pointer)}};j['actions'].append({'target':target,'output':{'failed':False,'score':-1,'output_dir':directory}});j['program_attempts'].append({'target':target,'return_code':0})
   (n/'journal-private.json').write_text(json.dumps(j));return m.verify_native_scores(s,n)
 def test_two_actual_native_scores_pass(self):self.assertEqual(self.case()['status'],'PASS_TWO_CURRENT_NATIVE_SCORE_PROGRAMS')
 def test_only_one_native_score_is_not_a_completed_two_candidate_study(self):
  with self.assertRaises(AssertionError):self.case(missing='P13')
 def test_wrong_checkpoint_pointer_is_rejected(self):
  with self.assertRaises(AssertionError):self.case(bad_pointer=True)
if __name__=='__main__':unittest.main()
