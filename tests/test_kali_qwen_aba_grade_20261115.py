import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_qwen_aba_grade_20261115 import grade
class GradeTests(unittest.TestCase):
 def setUp(self):
  self.old=['old'+str(i) for i in range(64)];self.meta={'new46':{'new'+str(i):{'group':'g'+str(i//2)} for i in range(46)},'old64_ids':self.old,'historical_correct13':self.old[:13]}
  self.base={i:{'native':.6,'strict':i in self.old[:13],'truncated':False,'early_EOS':False} for i in self.old+list(self.meta['new46'])};self.beh={i:'unknown_unreviewed_command' for i in self.meta['new46']}
 def test_same_is_zero(self):self.assertAlmostEqual(grade(self.meta,self.base,self.beh,self.base,self.beh)['score'],0)
 def test_replacement_gains_do_not_hide_old_losses(self):
  candidate=copy.deepcopy(self.base)
  for i in self.old[:3]:candidate[i]['strict']=False
  for i in self.old[13:20]:candidate[i]['strict']=True
  out=grade(self.meta,candidate,self.beh,self.base,self.beh);self.assertGreater(out['strict_total'],13);self.assertFalse(out['eligible']);self.assertEqual(out['historical_lost'],3)
 def test_unknown_not_rewarded_as_pass(self):
  passed={i:'fixture_pass' for i in self.beh};self.assertEqual(grade(self.meta,self.base,passed,self.base,self.beh)['utility_points'],100);self.assertEqual(grade(self.meta,self.base,self.beh,self.base,self.beh)['unknown_count'],46)
 def test_truncation_and_mean_retention_floor(self):
  candidate=copy.deepcopy(self.base);candidate['new0']['truncated']=True;self.assertFalse(grade(self.meta,candidate,self.beh,self.base,self.beh)['eligible'])
  candidate=copy.deepcopy(self.base)
  for i in self.old:candidate[i]['native']=.57
  self.assertFalse(grade(self.meta,candidate,self.beh,self.base,self.beh)['eligible'])
 def test_family_macro_does_not_overweight_variants(self):
  behavior=dict(self.beh);behavior['new0']=behavior['new1']='fixture_pass';out=grade(self.meta,self.base,behavior,self.base,self.beh);self.assertAlmostEqual(out['utility_points'],100/23)
if __name__=='__main__':unittest.main()
