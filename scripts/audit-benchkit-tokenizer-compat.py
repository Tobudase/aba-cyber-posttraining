#!/usr/bin/env python3
"""Compare pinned raw tokenizers with HF wrappers; run in each existing venv."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path

from benchkit import ARTIFACT, ROOT, load_tokenizer, sha, write_json

def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args = p.parse_args()
    from tokenizers import Tokenizer
    texts = ['head -n 5 notes.txt', '<think>\n</think>\nCWE-79', 'CVE-2026-104433',
             '1234567890 1.2345 -17', 'Unicode 中文 café Ω —', 'spaces\t  two\n\nlines',
             '<output>openssl x509 -in local.pem -noout -subject</output>', '',
             'sha256sum --check checksums.txt', 'jq -r ".event.type" events.json']
    models = {}
    for alias in ['cisco', 'redsage']:
        tok = load_tokenizer(alias)
        raw = Tokenizer.from_file(str(ARTIFACT / 'models' / alias / 'tokenizer.json'))
        hashes, mismatches = [], []
        for ix, text in enumerate(texts):
            a = tok.encode(text, add_special_tokens=False)
            b = raw.encode(text, add_special_tokens=False).ids
            if a != b: mismatches.append(ix)
            hashes.append(sha(json.dumps(a).encode()))
        if mismatches: raise ValueError('HF wrapper changes pinned raw tokenizer')
        models[alias] = {'text_cases': len(texts), 'raw_wrapper_mismatches': mismatches,
                         'token_id_hashes': hashes, 'fix_mistral_regex': False,
                         'reason': 'Preserve original Llama/Qwen tokenizer; do not apply unrelated Mistral patch.'}
    report = {'transformers': version('transformers'), 'tokenizers': version('tokenizers'),
              'models': models, 'pretrained_weights_loaded': False, 'official_test_rows': 0}
    write_json(args.output, report)
    print(json.dumps({'transformers': report['transformers'], 'models': {k: {'cases': v['text_cases'], 'mismatches': v['raw_wrapper_mismatches']} for k, v in models.items()}}, indent=2))

if __name__ == '__main__':main()
