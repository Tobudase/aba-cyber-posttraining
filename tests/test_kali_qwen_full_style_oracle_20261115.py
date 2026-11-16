import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_qwen_full_style_oracle_20261115 import counterexamples,style_config,equal_dump
class Style(unittest.TestCase):
 def test_base_and_unrequested_setting_are_distinct_controls(self):
  ref=['clang-format','--style={"BasedOnStyle":"Google","IndentWidth":4}','--dump-config'];base,extra=counterexamples(ref)
  self.assertEqual(style_config(base)['BasedOnStyle'],'LLVM');self.assertEqual(style_config(extra)['BasedOnStyle'],'Google');self.assertEqual(style_config(extra)['IndentWidth'],4);self.assertIn('ColumnLimit',style_config(extra))
 def test_full_dump_not_requested_key_subset(self):
  good=b'IndentWidth: 4\nColumnLimit: 80\n';bad=b'IndentWidth: 4\nColumnLimit: 100\n'
  self.assertFalse(equal_dump(good,0,bad));self.assertFalse(equal_dump(good,1,good));self.assertTrue(equal_dump(good,0,good));self.assertTrue(equal_dump(good,0,b'# BasedOnStyle: Google\n'+good))
if __name__=='__main__':unittest.main()
