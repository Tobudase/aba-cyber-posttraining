import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from kali_decode_policy import audit_stream_text


class DecodingPolicyTests(unittest.TestCase):
    def test_exact_text(self):
        self.assertEqual(audit_stream_text('<output>cmd</output>', '<output>cmd</output>'), 'EXACT')

    def test_single_leading_space_is_recorded(self):
        self.assertEqual(audit_stream_text(' cmd', 'cmd'), 'MLX_STREAM_DROPPED_ONE_INITIAL_ASCII_SPACE')

    def test_command_change_is_rejected(self):
        for decoded, streamed in [('cmd --count 2', 'cmd --count 9'), ('\ncmd', 'cmd'), ('  cmd', 'cmd')]:
            with self.assertRaises(ValueError): audit_stream_text(decoded, streamed)


if __name__ == '__main__': unittest.main()
