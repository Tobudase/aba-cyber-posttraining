#!/usr/bin/env python3
"""Pair actual local E0/E1 predictions; distinguish native, value and XML checks."""
from collections import defaultdict
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from benchkit import ROOT, final_text, load_jsonl, load_manifest, score_predictions, sha, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, default=ROOT / 'docs/verification')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    directory = args.evidence_dir
    paths = {'E0': directory / 'kali-mlx-e0-2026-10-22',
             'E1': directory / 'kali-mlx-e1-dev-2026-10-22'}
    manifest = ROOT / 'data/benchkit/kali-external-dev/manifest.json'
    _, rows = load_manifest(manifest, 'dev_search')
    expected = {r['id']: r for r in rows}
    receipts, details, outputs, stats = {}, {}, {}, {}
    for phase, path in paths.items():
        receipt = json.loads((path / 'receipt.json').read_text())
        if receipt['status'] != 'COMPLETE' or receipt['actual_rows'] != 72 or receipt['dev_manifest_sha256'] != sha(manifest.read_bytes()):
            raise ValueError('Incomplete or mismatched full-search run')
        predictions = load_jsonl(path / 'predictions.jsonl')
        if sha((path / 'predictions.jsonl').read_bytes()) != receipt['predictions_sha256']:
            raise ValueError('Prediction bytes changed')
        score = score_predictions(rows, predictions, 'kali')
        if score['summary'] != receipt['metrics']: raise ValueError('Recomputed metrics differ')
        receipts[phase] = receipt
        details[phase] = {r['id']: r for r in score['details']}
        outputs[phase] = {r['id']: r for r in predictions}
        full_xml = {r['id']: bool(re.fullmatch(r'<output>\s*.+?\s*</output>', final_text(r['response']), re.S))
                    for r in predictions}
        families = defaultdict(list)
        for r in score['details']: families[expected[r['id']]['group_id']].append(r)
        stats[phase] = {'native_metrics': score['summary'],
            'option_diagnostic_correct_count': sum(r['strict_option_value_correct'] for r in score['details']),
            'complete_output_xml_rows': sum(full_xml.values()),
            'xml_and_option_diagnostic_correct_count': sum(full_xml[r['id']] and bool(r['strict_option_value_correct']) for r in score['details']),
            'output_tokens': sum(r['output_tokens'] for r in predictions),
            'truncated_rows': sum(r['truncated'] for r in predictions),
            'peak_metal_GB': receipt['peak_metal_memory_bytes'] / 1e9,
            'wall_seconds': receipt['wall_seconds'],
            'by_family': {k: {'rows': len(v), 'option_diagnostic_correct': sum(r['strict_option_value_correct'] for r in v)}
                          for k, v in families.items()}}
    for key in ['model_id', 'source_revision', 'conversion_receipt_sha256', 'dev_manifest_sha256',
                'max_output_tokens', 'temperature', 'seed', 'prompt_policy']:
        if receipts['E0'][key] != receipts['E1'][key]: raise ValueError('Paired inference settings differ: ' + key)
    training = json.loads((directory / 'kali-mlx-e1-train-2026-10-22/receipt.json').read_text())
    if training['status'] != 'COMPLETE' or training['optimizer_steps'] != 20 or training['adapter_reload_max_abs_logit_delta'] > 1e-5:
        raise ValueError('Real training not independently recorded')
    changed = []
    for identifier, row in expected.items():
        e0, e1 = details['E0'][identifier], details['E1'][identifier]
        if e0['strict_option_value_correct'] != e1['strict_option_value_correct']:
            changed.append({'id': identifier, 'family': row['group_id'],
                'E0_correct': bool(e0['strict_option_value_correct']), 'E1_correct': bool(e1['strict_option_value_correct']),
                'gold_command': row['native_label']['ground_truth_command'],
                'E0_command': e0['pred_cmd'], 'E1_command': e1['pred_cmd']})
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'LOCAL_REAL8B_CONTINUED_SFT_CYCLE_COMPLETE', 'rows_per_evaluation': 72,
        'search_template_families': 12, 'training_steps': 20,
        'comparison': stats, 'changed_diagnostic_outcomes': changed,
        'gain_rows': sum(r['E1_correct'] and not r['E0_correct'] for r in changed),
        'regression_rows': sum(r['E0_correct'] and not r['E1_correct'] for r in changed),
        'official_test_rows': 0, 'confirmation_rows_queried': 0, 'ABA_executed': False,
        'weights_redistributed': False, 'official_benchmark_result': False,
        'training_receipt_sha256': sha((directory / 'kali-mlx-e1-train-2026-10-22/receipt.json').read_bytes()),
        'limitations': [
            '72rows are correlated variants in12authored families; no independence assumption or generalization/significance claim.',
            'Native parser accepts a closing output tag without an opening tag; XML format diagnostic is separate.',
            'Option diagnostic inherits native structural matching; possibly equivalent pipelines can still fail canonical comparison.',
            '20steps continued TRAIN exposure with last4layers LoRA, not new-data adaptation or ABA.',
            'Quantized local pilot differs from official BF16/thinking/sampled5,000-case protocol.',
        ]}
    write_json(args.output or directory / 'kali-mlx-pilot-comparison-2026-10-22.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'changed_diagnostic_outcomes'}, indent=2))


if __name__ == '__main__': main()
