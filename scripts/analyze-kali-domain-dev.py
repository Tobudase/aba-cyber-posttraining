#!/usr/bin/env python3
"""Recompute three descriptive domain-dev controls, with zero model calls."""
import json
from pathlib import Path

from benchkit import ROOT, final_text, load_jsonl, load_manifest, score_predictions, sha, write_json
import re


def main():
    manifest = ROOT / 'data/benchkit/kali-domain-dev-v1/manifest.json'
    _, rows = load_manifest(manifest, 'dev_search'); expected = {r['id']: r for r in rows}
    root = ROOT / 'docs/verification'
    paths = {'aligned': root / 'kali-domain-e0-2026-10-22',
             'native': root / 'kali-domain-e0-native-resumed-2026-10-22',
             'tool_help': root / 'kali-domain-e0-dochelp-2026-10-22'}
    results = {}; reference = None; details = {}; preds = {}
    for name, path in paths.items():
        receipt = json.loads((path / 'receipt.json').read_text())
        if receipt['status'] != 'COMPLETE' or receipt['completed_rows'] != 36:
            raise ValueError('Do not score partial/failed control: ' + name)
        if receipt['dev_manifest_sha256'] != sha(manifest.read_bytes()): raise ValueError('Development data changed')
        predictions = load_jsonl(path / 'predictions.jsonl')
        if sha((path / 'predictions.jsonl').read_bytes()) != receipt['predictions_sha256']: raise ValueError('Predictions changed')
        matched = {k: receipt[k] for k in ['model_id', 'source_revision', 'conversion_receipt_sha256',
            'dev_manifest_sha256', 'row_ids', 'temperature', 'seed', 'max_output_tokens', 'quantization']}
        if reference is None: reference = matched
        elif reference != matched: raise ValueError('Base model/data/generation control mismatch')
        score = score_predictions(rows, predictions, 'kali')
        if score['summary'] != receipt['native_metrics']: raise ValueError('Independent score mismatch')
        details[name] = {d['id']: d for d in score['details']}; preds[name] = {p['id']: p for p in predictions}
        results[name] = {'rows': 36, 'native_metrics': score['summary'],
            'correct_option_diagnostic_rows': sum(d['strict_option_value_correct'] for d in score['details']),
            'complete_XML_rows': sum(bool(re.fullmatch(r'<output>\s*.+?\s*</output>', final_text(p['response']), re.S)) for p in predictions),
            'truncated_rows': sum(p['truncated'] for p in predictions),
            'generation_prefix': receipt['generation_prefix'], 'tool_help_context': receipt.get('tool_help_context', False),
            'stream_leading_space_differences': receipt.get('stream_leading_space_differences', 0),
            'receipt_sha256': sha((path / 'receipt.json').read_bytes()),
            'peak_metal_memory_bytes': receipt['peak_metal_memory_bytes'], 'wall_seconds_this_process': receipt['wall_seconds']}
    changes = {}
    for a, b in [('native', 'aligned'), ('aligned', 'tool_help')]:
        changes[a + '_to_' + b] = {'gain_rows': sum(details[b][i]['strict_option_value_correct'] > details[a][i]['strict_option_value_correct'] for i in expected),
            'regression_rows': sum(details[b][i]['strict_option_value_correct'] < details[a][i]['strict_option_value_correct'] for i in expected),
            'identical_response_texts': sum(preds[a][i]['response'] == preds[b][i]['response'] for i in expected)}
    remaining = [{'id': i, 'reference': expected[i]['native_label']['ground_truth_command'],
                  'predicted': details['tool_help'][i]['pred_cmd'], 'review_status': 'PENDING_SEMANTIC_REVIEW'}
                 for i in expected if not details['tool_help'][i]['strict_option_value_correct']]
    report = {'status': 'THREE_DOMAIN_DEV_INFERENCE_CONTROLS_COMPLETE', 'model': reference,
        'results': results, 'paired_changes': changes, 'remaining_dochelp_review_queue': remaining,
        'new_training_steps': 0, 'ABA_executed': False, 'official_test_rows': 0,
        'confirmation_rows_queried': 0, 'commands_executed': 0,
        'limitations': ['Authored source-silver, independent label review pending; not representative official performance.',
            'Tool-help context is supplied at inference; any gain is not learning or post-training improvement.',
            'Strict system messages and1024-token cap differ from official thinking-system/8192-token evaluation.',
            'Do not conclude quantization, model knowledge, or dataset quality as sole cause from these controls.',
            'Failed native attempt preserved; resumed24validated rows, generated remaining12 without rewriting old outputs.']}
    write_json(root / 'kali-domain-dev-comparison-2026-10-22.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in {'model', 'remaining_dochelp_review_queue'}}, indent=2))


if __name__ == '__main__': main()
