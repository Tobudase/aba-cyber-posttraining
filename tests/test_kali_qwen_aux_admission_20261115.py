import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_qwen_aux_admission_20261115 import admitted
class Admission(unittest.TestCase):
 def test_local_curl(self):
  self.assertIsNotNone(admitted('curl -sS -o copied.txt file:///workspace/task/evidence.txt','curl'))
  for s in ['curl https://example.com','curl -o /tmp/x file:///workspace/task/evidence.txt','curl file:///etc/passwd','curl --config evil']:
   self.assertIsNone(admitted(s,'curl'))
 def test_clang(self):
  self.assertIsNotNone(admitted("clang-format --style='{BasedOnStyle: LLVM, IndentWidth: 4}' --dump-config",'clang-format'))
  self.assertIsNone(admitted('clang-format --style=file --dump-config','clang-format'))
  self.assertIsNone(admitted("clang-format --style='{IncludeStyle: unsafe}' --dump-config",'clang-format'))
 def test_local_paths(self):
  for tool,s in [('ls','ls -1Ar items'),('column','column -t -s : records.txt'),('look','look -f ap words.txt')]:self.assertIsNotNone(admitted(s,tool))
  for s in ['ls -1 /','ls -1 ../items','ls -1 items; id','ls -1 $(id)']:self.assertIsNone(admitted(s,'ls'))
if __name__=='__main__':unittest.main()
