import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from benchkit import load_jsonl,sha
class FrozenAblationTests(unittest.TestCase):
 def test_frozen_protocols_pin_executed_runner_and_equal_budgets(self):
  freeze=json.loads((ROOT/'docs/verification/kali-replay-v2-freeze.json').read_text())
  for arm,expected in freeze['protocol_sha256'].items():
   path=ROOT/f'configs/kali-replay-v2-{arm}.protocol.json';self.assertEqual(sha(path.read_bytes()),expected)
   p=json.loads(path.read_text());self.assertEqual(p['training']['steps'],128);self.assertFalse(p['official_test_enabled']);self.assertFalse(p['confirmation_inference'])
   self.assertEqual(p['runner_sha256'],sha((ROOT/'scripts/run-kali-replay-ablation-v2.py').read_bytes()))
 def test_same_domain_core_and_explicit_replay_replacement(self):
  a=load_jsonl(ROOT/'data/benchkit/kali-replay-ablation-v2/domain_control/train.jsonl')
  b=load_jsonl(ROOT/'data/benchkit/kali-replay-ablation-v2/domain_plus_replay/train.jsonl')
  self.assertEqual(len(a),128);self.assertEqual(len(b),128)
  self.assertEqual([(r['messages'],r['target']) for r in a[:96]],[(r['messages'],r['target']) for r in b[:96]])
  self.assertEqual(len({r['source_training_id'] for r in a}),96);self.assertEqual(len({r['source_training_id'] for r in b}),128)
  self.assertTrue(all(r['source_training_id'].startswith('kali-replay-v2-') for r in b[96:]))
 def test_replay_file_matches_linux_verified_bytes(self):
  r=json.loads((ROOT/'docs/verification/kali-replay-fixtures-2026-10-23.json').read_text())
  self.assertEqual(r['passed'],32);self.assertEqual(r['status'],'PASS')
  self.assertEqual(r['training_file_sha256'],sha((ROOT/'data/benchkit/kali-replay-v2/train.jsonl').read_bytes()))
 def test_replay_uses_different_tools_from_public_dev(self):
  dev=[r for name in ['kali-external-dev','kali-domain-dev-v1'] for r in load_jsonl(ROOT/f'data/benchkit/{name}/dev_search.jsonl')]
  train=load_jsonl(ROOT/'data/benchkit/kali-replay-v2/train.jsonl')
  self.assertFalse({r['native_label']['tool_name'] for r in train}&{r['native_label']['tool_name'] for r in dev})
 def test_selected_semantic_evidence_has_four_passes(self):
  r=json.loads((ROOT/'docs/verification/kali-linux-semantics-2026-10-23.json').read_text())
  self.assertEqual(r['platform'],'Linux');self.assertEqual(len(r['checks']),4);self.assertTrue(all(x['pass'] for x in r['checks'].values()))
if __name__=='__main__':unittest.main()
