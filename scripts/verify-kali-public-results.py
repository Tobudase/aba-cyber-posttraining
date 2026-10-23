#!/usr/bin/env python3
"""Replay published scores only; no model, command execution or tensor checks."""
import json
from benchkit import ROOT, load_jsonl, score_predictions, sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked(path, digest):
    raw = (ROOT / path).read_bytes()
    require(sha(raw) == digest, 'Hash mismatch: ' + str(path))
    return raw


def main():
    protocol_path = ROOT / 'configs/kali-doc-sft-v1.protocol.json'
    protocol = json.loads(protocol_path.read_text())
    root = ROOT / 'docs/verification/kali-doc-sft-v1-2026-10-22'
    train = json.loads((root / 'train/receipt.json').read_text())
    evaluation = json.loads((root / 'evaluation/receipt.json').read_text())
    comparison = json.loads((root / 'comparison.json').read_text())
    for record in (train, evaluation):
        require(record['status'] == 'COMPLETE', 'Incomplete run')
        require(record['protocol_sha256'] == sha(protocol_path.read_bytes()), 'Protocol mismatch')
        require(not any(record[k] for k in ('official_test_rows', 'confirmation_rows_queried', 'ABA_executed')), 'Scope mismatch')
    require(evaluation['training_receipt_sha256'] == sha((root / 'train/receipt.json').read_bytes()), 'Training receipt mismatch')
    manifest = json.loads(checked(protocol['train_manifest'], protocol['train_manifest_sha256']))
    part = manifest['splits']['train']
    train_path = str((ROOT / protocol['train_manifest']).parent.relative_to(ROOT) / part['file'])
    checked(train_path, part['sha256'])
    train_rows = load_jsonl(ROOT / train_path)
    require(len(train_rows) == len(set(train['train_ids'])) == 108, 'Training row count mismatch')
    require({r['id'] for r in train_rows} == set(train['train_ids']), 'Training IDs mismatch')
    outputs = {}
    for name, check in protocol['evaluation'].items():
        spec = json.loads(checked(check['manifest'], check['manifest_sha256']))
        part = spec['splits'][check['split']]
        path = str((ROOT / check['manifest']).parent.relative_to(ROOT) / part['file'])
        checked(path, part['sha256']); rows = load_jsonl(ROOT / path)
        base_dir = ROOT / check['baseline_directory']
        checked(str((base_dir / 'receipt.json').relative_to(ROOT)), check['baseline_receipt_sha256'])
        checked(str((base_dir / 'predictions.jsonl').relative_to(ROOT)), check['baseline_predictions_sha256'])
        post_path = root / 'evaluation' / name / 'predictions.jsonl'
        checked(str(post_path.relative_to(ROOT)), evaluation['evaluations'][name]['predictions_sha256'])
        before = load_jsonl(base_dir / 'predictions.jsonl'); after = load_jsonl(post_path)
        a = {p['id']: p for p in before}; b = {p['id']: p for p in after}
        require(len(a) == len(before) == len(b) == len(after) == check['rows'], 'Duplicate/count mismatch')
        require(set(a) == set(b) == {r['id'] for r in rows}, 'Evaluation ID mismatch')
        require(all(a[i]['prompt_sha256'] == b[i]['prompt_sha256'] for i in a), 'Prompt mismatch')
        counts = []
        for tag, predictions, key in [('baseline', before, 'baseline_native'), ('post', after, 'post_native')]:
            scores = score_predictions(rows, predictions, 'kali')
            require(scores['summary'] == evaluation['evaluations'][name][tag], 'Receipt score mismatch')
            require(scores['summary'] == comparison['comparisons'][name][key], 'Comparison score mismatch')
            count = sum(d['strict_option_value_correct'] for d in scores['details'])
            require(count == comparison['comparisons'][name][tag + '_correct'], 'Diagnostic mismatch')
            counts.append(count)
        outputs[name] = {'rows': len(rows), 'base_correct': counts[0], 'post_correct': counts[1]}
    d, r = comparison['comparisons']['domain'], comparison['comparisons']['retention']
    rules = {
        'domain_exact_strictly_improves': d['post_native']['exact_match'] > d['baseline_native']['exact_match'],
        'domain_option_diagnostic_strictly_improves': d['post_correct'] > d['baseline_correct'],
        'domain_total_not_decreased': d['post_native']['total_score'] >= d['baseline_native']['total_score'],
        'retention_not_decreased': r['post_correct'] >= r['baseline_correct'],
        'no_truncation_runtime_XML_failures': all(x['post_truncated'] == 0 and x['post_complete_XML'] == x['rows'] and x['post_native']['runtime_failed_rows'] == 0 for x in (d, r)),
    }
    require(rules == comparison['fixed_rule_checks'] and not all(rules.values()), 'Frozen rule mismatch')
    require(comparison['decision'] == 'KEEP_ORIGINAL_BASE_DO_NOT_PROMOTE_ADAPTER', 'Decision mismatch')
    controls = {}
    rows = load_jsonl(ROOT / 'data/benchkit/kali-domain-dev-v1/dev_search.jsonl')
    for name, directory in [('native', 'kali-domain-e0-native-resumed-2026-10-22'), ('aligned', 'kali-domain-e0-2026-10-22'), ('tool_help', 'kali-domain-e0-dochelp-2026-10-22')]:
        folder = ROOT / 'docs/verification' / directory
        receipt = json.loads((folder / 'receipt.json').read_text())
        require(receipt['status'] == 'COMPLETE' and receipt['completed_rows'] == 36, 'Incomplete control')
        checked(str((folder / 'predictions.jsonl').relative_to(ROOT)), receipt['predictions_sha256'])
        scores = score_predictions(rows, load_jsonl(folder / 'predictions.jsonl'), 'kali')
        require(scores['summary'] == receipt['native_metrics'], 'Control score mismatch')
        controls[name] = sum(d['strict_option_value_correct'] for d in scores['details'])
    print(json.dumps({'status': 'PASS_PUBLIC_SCORE_REPLAY', 'matched_sft': outputs, 'domain_controls': controls,
        'decision': comparison['decision'], 'new_model_calls': 0,
        'scope': 'Published data/hash/score replay; unpublished tensors, private confirmation bodies and training execution not reverified'}, indent=2))


if __name__ == '__main__':
    main()
