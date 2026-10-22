#!/usr/bin/env python3
"""Explicit dataset auditing, tokenizer checks and score-only evaluation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from benchkit import (ROOT, ARTIFACT, encode_supervision, load_jsonl, load_manifest,
                      load_tokenizer, score_predictions, sha, verify_sources, write_json, write_jsonl)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('audit-data'); a.add_argument('--dataset', required=True)
    s = sub.add_parser('score'); s.add_argument('--dataset', required=True); s.add_argument('--split', required=True)
    s.add_argument('--predictions', required=True); s.add_argument('--output', required=True); s.add_argument('--six-tasks', action='store_true')
    t = sub.add_parser('tokenizers'); t.add_argument('--output', default=str(ROOT / 'docs/verification/benchkit-tokenizer-audit.json'))
    args = parser.parse_args()
    if args.command == 'audit-data':
        spec, pools = load_manifest(args.dataset)
        print(json.dumps({'benchmark': spec['benchmark'], 'counts': {k: len(v) for k, v in pools.items()},
            'manifest_sha256': sha(Path(args.dataset).read_bytes()), 'limitations': spec.get('limitations', [])}, indent=2))
    elif args.command == 'score':
        spec, rows = load_manifest(args.dataset, args.split)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=False)
        result = score_predictions(rows, load_jsonl(args.predictions), spec['benchmark'], args.six_tasks)
        result.update({'dataset_manifest_sha256': sha(Path(args.dataset).read_bytes()),
                       'predictions_sha256': sha(Path(args.predictions).read_bytes()),
                       'official_benchmark_score': False})
        write_json(out / 'metrics.json', result)
        print(json.dumps(result['summary'], indent=2))
    else:
        source = verify_sources()
        from transformers import AutoTokenizer
        results = {}
        for alias, benchmark, names in [('cisco', 'athena', ['athena-v3']), ('redsage', 'kali', ['kali-screened', 'kali-external-dev'])]:
            tokenizer = load_tokenizer(alias)
            pools = {}
            for name in names:
                spec, part = load_manifest(ROOT / 'data/benchkit' / name / 'manifest.json')
                for split, records in part.items():
                    pools[name + ':' + split] = records
            lengths, prompt_tokens, differences, rejected = [], [], 0, []
            for split, rows in pools.items():
                for r in rows:
                    try:
                        e = encode_supervision(tokenizer, r, 2048)
                        lengths.append(len(e['input_ids'])); prompt_tokens.append(e['prompt_tokens'])
                        differences += e['native_generation_prefix_differs']
                        if any(x != -100 for x in e['labels'][:e['prompt_tokens']]):
                            raise ValueError('Prompt label mask inconsistent')
                    except ValueError as exc:
                        rejected.append({'id': r['id'], 'split': split, 'error': str(exc)})
            ordered = sorted(lengths)
            results[alias] = {'model_id': source['models'][alias]['id'], 'tokenizer_vocab': len(tokenizer),
                'records': sum(len(x) for x in pools.values()), 'encoded': len(lengths), 'rejected': rejected,
                'length_min': min(lengths) if lengths else None, 'length_max': max(lengths) if lengths else None,
                'length_p95': ordered[int((len(ordered) - 1) * .95)] if lengths else None,
                'native_generation_prefix_differs_from_final_only_training': differences,
                'reasoning_template_requires_protocol_decision': differences > 0,
                'template_sha256': sha(tokenizer.chat_template.encode()),
                'supervision': 'Native final-only full-chat, offsets masked; generation normally opens <think>.'}
        report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'models': results,
                  'official_test_rows': 0, 'model_weights_loaded': False,
                  'status': 'TOKENIZATION_AUDITED_WITH_EXPLICIT_REJECTIONS'}
        write_json(args.output, report)
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
