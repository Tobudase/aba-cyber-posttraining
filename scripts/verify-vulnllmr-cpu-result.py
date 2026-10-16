#!/usr/bin/env python3
"""Independently verify collected full-checkpoint CPU output and development metrics."""
import hashlib
import json
from pathlib import Path
from vulnllmr_metrics import parse_answer, score

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'docs/verification/vulnllmr-cpu-smoke.json'
    evidence = json.loads(source.read_text())
    result = evidence.get('model_result')
    if result is None:
        raise RuntimeError('No full-checkpoint result collected; verification cannot pass')
    lock = json.loads((ROOT / 'configs/vulnllmr-cpu-runtime.lock.json').read_text())
    samples = json.loads((ROOT / 'data/manifests/vulnllmr-cpu-smoke-samples.json').read_text())
    expected = {s['id']: s for s in samples}
    checks = {}
    checks['model_and_revision'] = result['model_id'] == lock['model_id'] and result['revision'] == lock['revision']
    checks['complete_parameter_count'] = result['parameters'] == 7615616512
    checks['cpu_not_gpu'] = result['device'] == 'cpu' and result['gpu_verified'] is False
    checks['quantization_recorded'] = result.get('quantization') == lock.get('quantization')
    if lock.get('quantization'):
        checks['linear_layers_converted'] = result.get('quantized_linear_layers', 0) > 0
    checks['no_training_or_formal_test'] = result['training_executed'] is False and result['formal_test_used'] is False
    checks['exact_sample_set'] = len(result['rows']) == 4 and {r['id'] for r in result['rows']} == set(expected)
    checks['parsed_outputs_recomputed'] = all(row['parsed'] == parse_answer(row['output']) for row in result['rows'])
    checks['source_labels_unchanged'] = all(row['target'] == expected[row['id']]['target']
        and row['gold_cwes'] == expected[row['id']]['cwes'] for row in result['rows'])
    checks['generation_budget'] = all(0 < row['output_tokens'] <= 32 for row in result['rows'])
    checks['metrics_recomputed'] = result['metrics'] == score(result['rows'])
    checks['output_contract'] = result.get('output_grammar') == lock.get('output_grammar')
    if lock.get('output_grammar'):
        checks['all_outputs_parse'] = all(row['parsed']['valid'] for row in result['rows'])
    checks['job_completed'] = any(c.get('type') == 'Complete' and c.get('status') == 'True'
        for c in evidence['job_status'].get('conditions', []))
    report = {'status': 'PASSED' if all(checks.values()) else 'FAILED', 'checks': checks,
        'model': result['model_id'], 'revision': result['revision'], 'parameters': result['parameters'],
        'metrics': score(result['rows']), 'seconds': result['seconds'],
        'evidence_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'limitations': ['CPU dynamic INT8 only; no BF16 equivalence or GPU verification', 'Four train-source examples, no independent benchmark',
                       '32-token budget with final-answer prefill; final attempt uses a fixed task-level answer grammar',
                       'Grammar validity is imposed, not evidence of unconstrained instruction following', 'No post-training executed']}
    (ROOT / 'docs/verification/vulnllmr-cpu-result-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if report['status'] != 'PASSED':
        raise RuntimeError('Result consistency check failed')


if __name__ == '__main__':
    main()
