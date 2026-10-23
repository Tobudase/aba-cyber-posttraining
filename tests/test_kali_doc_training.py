import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
s = importlib.util.spec_from_file_location('doc_training', ROOT / 'scripts/prepare-kali-doc-training.py')
mod = importlib.util.module_from_spec(s); s.loader.exec_module(mod)


class NewTrainingBoundaryTests(unittest.TestCase):
    def test_changing_only_values_and_filenames_does_not_evade_boundary(self):
        blocked = {mod.operation_signature('pedis', {'--rva|-r': '0x2400', '-i': '12'}, ['old.exe'])}
        task = {'tool': 'pedis', 'package': 'readpe', 'optional_args': {'-i': '99', '-r|--rva': '0x9000'}, 'positional_args': ['renamed.exe']}
        with self.assertRaisesRegex(ValueError, 'repeats a protected'):
            mod.check_boundary(task, blocked)

    def test_confirmation_package_cannot_enter_training(self):
        task = {'tool': 'llvm-dis', 'package': 'llvm-defaults', 'optional_args': {'--version': None}, 'positional_args': []}
        with self.assertRaisesRegex(ValueError, 'Reserved confirmation'):
            mod.check_boundary(task, set())

    def test_distinct_operation_can_pass_without_claiming_semantic_independence(self):
        blocked = {mod.operation_signature('readpe', {'--imports|-i': None}, ['old.exe'])}
        task = {'tool': 'readpe', 'package': 'readpe', 'optional_args': {'--exports|-e': None}, 'positional_args': ['new.exe']}
        mod.check_boundary(task, blocked)


if __name__ == '__main__': unittest.main()
