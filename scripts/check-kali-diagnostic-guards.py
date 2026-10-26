#!/usr/bin/env python3
"""Portable regression checks with invented inputs; no model/data/network access."""
import importlib.util
import itertools
import json
import shlex
from pathlib import Path
from kali_command_contract import canonical_command, UnsupportedCommand
from kali_structural_completion import encode_structural_completion


def main():
    checks = 0
    def pair(a, b, family, equal):
        nonlocal checks
        try:
            actual = canonical_command(a, family) == canonical_command(b, family)
        except UnsupportedCommand:
            actual = False
        assert actual == equal, (a, b, family)
        checks += 1
    gold = 'openssl x509 -in "example cert.pem" -noout -serial'
    for parts in itertools.permutations([['-in', 'example cert.pem'], ['-noout'], ['-serial']]):
        pair(gold, shlex.join(['openssl', 'x509'] + sum(parts, [])), 'openssl_serial', True)
    for bad in ['openssl x509 -in "example cert.pem" -serial',
                'openssl x509 -in wrong.pem -serial -noout',
                'openssl x509 -in "example cert.pem" -serial -noout -text']:
        pair(gold, bad, 'openssl_serial', False)
    cases = [
        ('wc -l "a file.txt"', 'wc --lines "a file.txt"', 'wc_lines', True),
        ('wc -l a.txt', 'wc -w a.txt', 'wc_lines', False),
        ('head -n -3 a.txt', 'head --lines=-3 a.txt', 'head_exclude', True),
        ('head -n -3 a.txt', 'head -n 3 a.txt', 'head_exclude', False),
        ('tail -n +4 a.txt', 'tail -n 4 a.txt', 'tail_lines', False),
        ('grep -F ERROR a.txt', 'grep ERROR a.txt', 'grep_fixed', True),
        ('grep -F "a.b" a.txt', 'grep "a.b" a.txt', 'grep_fixed', False),
        ("jq '.records | length' a.json", "jq -r '.records|length' a.json", 'jq_length', True),
        ("jq '.records | length' a.json", "jq 'length' a.json", 'jq_length', False),
        ("jq -r '.incident.kind' a.json", "jq '.incident.kind' a.json", 'jq_field', False),
        ('tshark -n -r a.pcap -T fields -e ip.src -e ip.dst',
         'tshark -n -r a.pcap -T fields -e ip.dst -e ip.src', 'tshark_sources', False),
        ('tcpdump -n -r a.pcap udp', 'tcpdump -r a.pcap -nn udp', 'tcpdump_udp', True),
        ('tcpdump -n -r a.pcap udp', 'tcpdump -n -r a.pcap', 'tcpdump_udp', False),
        ('tcpdump -n -r a.pcap udp', 'tcpdump -n -i eth0 udp', 'tcpdump_udp', False),
    ]
    for args in cases:
        pair(*args)
    class Tokenizer:
        eos_token_id = 999999
        eos_token = '<eos>'
        def apply_chat_template(self, messages, **kw):
            return 'USER:' + messages[-1]['content'] + '\nASSISTANT:<think>'
        def encode(self, text, **kw):
            return [ord(c) for c in text]
        def decode(self, ids, **kw):
            return ''.join(self.eos_token if i == self.eos_token_id else chr(i) for i in ids)
    tok = Tokenizer()
    row = {'split': 'train', 'training_eligible': True, 'official_test': False,
           'TRAIN_fixture_execution_verified': True, 'TRAIN_explicit_constraints_verified': True}
    messages = [{'role': 'user', 'content': 'Invented boundary check.'}]
    output = '<output>\nwc -l example.txt\n</output>'
    encoded = encode_structural_completion(tok, row, messages, output)
    assert all(i == -100 for i in encoded['labels'][:encoded['prompt_tokens']])
    assert encoded['labels'][-1] == tok.eos_token_id
    assert tok.decode(encoded['input_ids'][encoded['prompt_tokens']:-1]) == '\n</think>\n\n' + output
    checks += 3
    bad = [({**row, 'split': 'dev'}, messages, output, 2048),
           ({**row, 'training_eligible': False}, messages, output, 2048),
           ({**row, 'official_test': True}, messages, output, 2048),
           ({**row, 'TRAIN_fixture_execution_verified': False}, messages, output, 2048),
           ({**row, 'TRAIN_explicit_constraints_verified': False}, messages, output, 2048),
           (row, messages + [{'role': 'assistant', 'content': 'leak'}], output, 2048),
           (row, messages, output + 'extra', 2048),
           (row, messages, output + output, 2048),
           (row, messages, output, 1)]
    for args in bad:
        try:
            encode_structural_completion(tok, *args)
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Invalid training input accepted')
    path = Path(__file__).with_name('score-kali-reviewed-dev.py')
    spec = importlib.util.spec_from_file_location('reviewed_dev', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    devrow = {'id': 'invented', 'split': 'dev', 'training_eligible': False,
              'official_test': False, 'intent_family': 'openssl_serial', 'gold_command': gold}
    prediction = {'id': 'invented', 'response': gold}
    for rows, predictions in [([devrow], [prediction]), ([devrow], [{**prediction, 'truncated': True}])]:
        scored = mod.score_rows(rows, predictions, lambda s: s)
        assert scored['correct'] == (0 if predictions[0].get('truncated') else 1)
        checks += 1
    for rows, predictions in [([devrow], []), ([devrow], [prediction, prediction]),
                              ([{**devrow, 'split': 'test'}], [prediction]),
                              ([{**devrow, 'training_eligible': True}], [prediction]),
                              ([{k: v for k, v in devrow.items() if k != 'training_eligible'}], [prediction]),
                              ([{k: v for k, v in devrow.items() if k != 'official_test'}], [prediction])]:
        try:
            mod.score_rows(rows, predictions, lambda s: s)
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Invalid DEV inputs accepted')
    print(json.dumps({'status': 'PASS_PORTABLE_DIAGNOSTIC_GUARDS', 'checks': checks,
                      'model_or_network_calls': 0, 'private_data_rows_read': 0}))


if __name__ == '__main__':
    main()
