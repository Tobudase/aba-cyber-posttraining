import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from kali_two_model_sft_worker_20261115 import prepare_output_directory


class StartupTests(unittest.TestCase):
    def test_fresh_volume_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'new-study' / 'attempt'
            self.assertEqual(prepare_output_directory(target), target)
            marker = target / 'protected-result'
            marker.write_text('preserve')
            with self.assertRaises(FileExistsError):
                prepare_output_directory(target)
            self.assertEqual(marker.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
