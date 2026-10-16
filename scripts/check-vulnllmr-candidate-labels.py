#!/usr/bin/env python3
"""Check assistant-only SFT labels on draft candidates without loading model weights."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--curated', action='store_true')
    args = parser.parse_args()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(ROOT / '.tools/model-tokenizer/vulnllmr-7b-8cd13d7a35f1',
                                              local_files_only=True, trust_remote_code=False)
    path = ROOT / ('data/trajectories/development_distillation/' +
                   ('vulnllmr-agent-reviewed-pilot.jsonl' if args.curated else 'vulnllmr-reviewed-candidates.jsonl'))
    candidates = [json.loads(x) for x in path.read_text().splitlines() if x]
    results = []
    for row in candidates:
        assert row['training_eligible'] is False and row['formal_test_used'] is False
        messages = row['messages']
        assert len(messages) == 2 and [x['role'] for x in messages] == ['user', 'assistant']
        assert 'Return exactly one JSON object' not in messages[0]['content']
        assert '## Final Answer' in messages[0]['content'] and '## Final Answer' in messages[1]['content']
        prefix = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
        assert full[:len(prefix)] == prefix, 'Prompt/completion token boundary mismatch'
        labels = [-100] * len(prefix) + full[len(prefix):]
        assert any(x != -100 for x in labels) and all(x == -100 for x in labels[:len(prefix)])
        assert tokenizer.eos_token_id in labels[len(prefix):]
        assert len(full) < 2048
        results.append({'id': row['source_id'], 'prompt_tokens_masked': len(prefix),
                        'assistant_tokens_supervised': len(full) - len(prefix), 'total_tokens': len(full)})
    if not results:
        raise RuntimeError('No draft candidates passed current automatic gates')
    report = {'status': 'PASSED_TOKEN_LABEL_CHECK', 'records': results, 'weights_loaded': False,
              'training_executed': False, 'formal_split_frozen': False, 'training_ready_records': 0,
              'scope': 'Actual Qwen2 tokenizer; user/system tokens masked, assistant completion and EOS supervised. No optimizer step.'}
    name = 'vulnllmr-curated-label-check.json' if args.curated else 'vulnllmr-candidate-label-check.json'
    (ROOT / 'docs/verification' / name).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
