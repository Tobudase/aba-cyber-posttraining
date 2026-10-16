#!/usr/bin/env python3
"""Check immutable inputs, token budgets, and metric edge cases without loading weights."""
import hashlib
import json
from pathlib import Path

from vulnllmr_metrics import parse_answer, score


def main():
    from transformers import AutoConfig, AutoTokenizer
    root = Path(__file__).resolve().parents[1]
    cache = root / '.tools/model-tokenizer/vulnllmr-7b-8cd13d7a35f1'
    lock = json.loads((root / 'configs/vulnllmr.lock.json').read_text())
    for name, meta in lock['metadata_artifacts'].items():
        assert hashlib.sha256((cache / name).read_bytes()).hexdigest() == meta['sha256'], name
    data = (root / lock['sample_manifest']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == lock['sample_manifest_sha256']
    samples = json.loads(data)['samples']
    tok = AutoTokenizer.from_pretrained(cache, local_files_only=True, trust_remote_code=False)
    cfg = AutoConfig.from_pretrained(cache, local_files_only=True, trust_remote_code=False)
    assert cfg.model_type == 'qwen2'
    assert len(samples) == 4 and sum(x['target'] for x in samples) == 2
    assert len({x['code_sha256'] for x in samples}) == 4
    rows = []
    for x in samples:
        assert x['training_eligible'] is False and x['role'] == 'development_smoke_only'
        text = tok.apply_chat_template([{'role': 'user', 'content': x['prompt']}], tokenize=False, add_generation_prompt=True)
        ids = tok(text, add_special_tokens=False)['input_ids']
        assert len(ids) < lock['inference']['max_input_tokens']
        rows.append({'id': x['id'], 'input_tokens': len(ids), 'target': x['target'], 'code_sha256': x['code_sha256']})
    fixtures = [('#judge: yes\n#type: CWE-327', True), ('#judge: no\n#type: N/A', True),
                ('#judge: yes\n#type: CWE-12,CWE-125', False), ('#judge: yes\n#type: N/A', False),
                ('#judge: no\n#type: CWE-327', False), ('#judge: yes\n#judge: no\n#type: N/A', False),
                ('unstructured', False)]
    for text, valid in fixtures:
        assert parse_answer(text)['valid'] == valid
    result = score([{'output': '#judge: yes\n#type: CWE-12', 'target': 1, 'gold_cwes': ['CWE-125']},
                    {'output': 'invalid', 'target': 0, 'gold_cwes': ['CWE-327']},
                    {'output': '#judge: no\n#type: N/A', 'target': 0, 'gold_cwes': ['CWE-327']}])
    assert result['typed_exact'] == 1 and result['invalid'] == 1 and result['tp'] == 1 and result['tn'] == 1
    report = {'status': 'PASSED', 'architecture': cfg.architectures, 'tokenizer_class': type(tok).__name__,
              'formal_test_used': False, 'weights_loaded': False, 'parser_edge_cases': len(fixtures), 'rows': rows}
    (root / 'docs/verification/vulnllmr-tokenizer-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
