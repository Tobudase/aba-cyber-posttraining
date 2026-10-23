import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from benchkit import load_tokenizer
from kali_prompt_policy import generation_prompt


class KaliPromptPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = load_tokenizer('redsage')

    def test_default_preserves_historical_native_prefix(self):
        messages = [{'role': 'user', 'content': 'Count lines in report.txt.'}]
        self.assertEqual(generation_prompt(self.tokenizer, messages),
            self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True))

    def test_alignment_does_not_rewrite_user_think_literal(self):
        messages = [{'role': 'user', 'content': 'Treat the literal <think> as text in report.txt.'}]
        native = generation_prompt(self.tokenizer, messages, 'native')
        aligned = generation_prompt(self.tokenizer, messages, 'sft-aligned')
        self.assertEqual(native, aligned + '<think>')
        self.assertIn('literal <think> as text', aligned)

    def test_unrecognized_template_refuses_silent_replacement(self):
        class OtherTemplate:
            def apply_chat_template(self, *args, **kwargs): return 'different assistant prefix'
        with self.assertRaises(ValueError): generation_prompt(OtherTemplate(), [], 'sft-aligned')

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError): generation_prompt(self.tokenizer, [], 'silently-change-everything')


if __name__ == '__main__': unittest.main()
