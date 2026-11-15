import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from kali_hardlink_oracle_v6_20261115 import preview_ok, partition_ok, shadow_argv


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.before = {f'files/{name}': dict(inode=i, links=1, mode=384,
            mtime_ns=1, uid=1, gid=1, size=64, sha256=digest)
            for name, i, digest in [('a', 1, 'x'), ('b', 2, 'x'), ('c', 3, 'z')]}
        self.out = 'Mode:           dry-run\nLinked:         1 files\n'

    def test_correct_summary(self):
        self.assertTrue(preview_ok(self.before, self.before, self.out, 'files'))

    def test_noop_and_filtered_all_rejected(self):
        self.assertFalse(preview_ok(self.before, self.before, '', 'files'))
        self.assertFalse(preview_ok(self.before, self.before, self.out.replace('1 files', '0 files'), 'files'))

    def test_mutation_and_wrong_mode_rejected(self):
        changed = copy.deepcopy(self.before)
        changed['files/b']['inode'] = 1
        self.assertFalse(preview_ok(self.before, changed, self.out, 'files'))
        self.assertFalse(preview_ok(self.before, self.before, self.out.replace('dry-run', 'real'), 'files'))

    def test_shadow_preserves_wrong_options(self):
        args = ['hardlink', '--dry-run', '--exclude', '.*', 'files']
        self.assertEqual(shadow_argv(args), ['hardlink', '--exclude', '.*', 'files'])
        with self.assertRaises(ValueError):
            shadow_argv(['hardlink', 'files'])

    def test_shadow_requires_exact_partition(self):
        good = copy.deepcopy(self.before)
        good['files/b']['inode'] = 1
        self.assertTrue(partition_ok(self.before, good, 'files'))
        self.assertFalse(partition_ok(self.before, self.before, 'files'))
        wrong = copy.deepcopy(self.before)
        wrong['files/c']['inode'] = 1
        self.assertFalse(partition_ok(self.before, wrong, 'files'))


if __name__ == '__main__':
    unittest.main()
