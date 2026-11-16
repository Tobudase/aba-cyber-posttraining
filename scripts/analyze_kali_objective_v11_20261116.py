"""Reconcile the paired objective experiment from saved, hash-checked evidence."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/benchkit/kali-execution-2026-11-14'


def analyze(name='miw113-kali-objective-v11-r2-1116'):
    d = OUT / name
    def read(n):
        return json.loads((d / n).read_text())
    cfg = json.loads(read('objects.json')[0]['data']['config.json'])
    receipt = read('receipt.json')
    export = read('export-audit.json')
    assert export['all_weights_verified']
    assert receipt['optimizer_steps'] == {'R': 192, 'RK': 192}
    assert receipt['order_hashes']['R'] == receipt['order_hashes']['RK']
    assert all(v['teacher_source_unchanged'] for v in receipt['checkpoints'].values())
    assert receipt['source_adapter_sha256'] == cfg['source_weights_sha256']
    assert receipt['worker_sha256'] == cfg['worker_sha256']
    assert receipt['official_TEST_queries'] == 0
    assert not (d / 'confirmation.json').exists()
    primary = read('behavior-primary-details.json')
    fit = read('behavior-finalfit-details.json')
    shifted = read('behavior-shifted-details.json')
    native = read('native-details.json')
    preds = read('predictions.json')
    finalfit = read('final-train-diagnostic-predictions.json')
    shifted_preds = read('shifted-dev-predictions.json')
    fixtures = json.loads((ROOT / cfg['data_directory'] / 'fixtures.json').read_text())['train']
    assert len(fixtures) == 384
    fx = {r['id']: r for r in fixtures}
    delta_ids = {r['id'] for r in json.loads((ROOT / 'data/benchkit/kali-counterfactual-v9-2026-11-16/new-delta144.json').read_text())}
    assert len(delta_ids) == 144 and delta_ids <= fx.keys()
    def counts(details, ids):
        assert set(ids) <= details.keys()
        c = collections.Counter(details[i] for i in ids)
        p = c['fixture_pass']
        u = sum(v for k, v in c.items() if k.startswith('unknown'))
        return {'n': len(ids), 'pass': p, 'fail': c['fixture_fail'],
                'unknown': u, 'counts': dict(c), 'lower': p, 'upper': p + u}
    old_ids = receipt['panels']['old64']
    old_base_correct = {i for i in old_ids if native['E0'][i]['strict']}
    results = {}
    aliases = {'R_step192': 'conditional_KL', 'RK_step192': 'direct_command_CE'}
    for label, objective in aliases.items():
        arm = label.split('_')[0]
        assert len(receipt['traces'][arm]) == 192
        assert [t['step'] for t in receipt['traces'][arm]] == list(range(1, 193))
        expected = 'conditional_KL' if arm == 'R' else 'command_CE'
        assert all(t['objective'] == expected for t in receipt['traces'][arm])
        assert set(fit[label]) == set(fx)
        assert len(finalfit[label]) == 384 and len(preds[label]) == 192 and len(shifted_preds[label]) == 64
        by_tool = {tool: counts(fit[label], [i for i, r in fx.items() if r['tool'] == tool])
                   for tool in sorted({r['tool'] for r in fixtures})}
        modes = {}
        for bundle in ['onefile', 'onedir']:
            for console in ['console', 'windowed']:
                ids = [i for i, r in fx.items() if i in delta_ids and r['tool'] == 'pyi-makespec'
                       and '--' + bundle in r['argv'] and '--' + console in r['argv']]
                assert len(ids) == 16
                modes[bundle + '_' + console] = counts(fit[label], ids)
        correct = {i for i in old_ids if native[label][i]['strict']}
        results[objective] = {
            'storage_label': label, 'train384': counts(fit[label], list(fx)),
            'train_by_tool': by_tool, 'new_delta_PyI64_modes': modes,
            'legacy64': counts(primary[label], receipt['panels']['legacy_new64']),
            'new_dev32': counts(primary[label], receipt['panels']['new_dev32']),
            'shifted_dev64': counts(shifted[label], receipt['extra_panels']['shifted_dev64']),
            'old_base_correct': len(old_base_correct),
            'old_retained': len(old_base_correct & correct),
            'old_lost_ids': sorted(old_base_correct - correct),
            'truncated': sum(r['truncated'] for r in preds[label] + finalfit[label] + shifted_preds[label]),
            'optimizer_steps': 192,
            'training_seconds': sum(t['window_wall_seconds'] for t in receipt['traces'][arm]),
            'weights_sha256': receipt['checkpoints'][label]['weights_sha256'],
        }
    # Paired transitions are descriptive: exposed, templated diagnostics are not independent tests.
    paired = {}
    for panel, lookup, ids in [('TRAIN384', fit, list(fx)),
                              ('legacy64', primary, receipt['panels']['legacy_new64']),
                              ('newDEV32', primary, receipt['panels']['new_dev32']),
                              ('shiftedDEV64', shifted, receipt['extra_panels']['shifted_dev64'])]:
        paired[panel] = dict(collections.Counter(
            str((lookup['R_step192'][i] == 'fixture_pass', lookup['RK_step192'][i] == 'fixture_pass'))
            for i in ids))
    files = ['receipt.json', 'export-audit.json', 'behavior-primary-details.json',
             'behavior-finalfit-details.json', 'behavior-shifted-details.json',
             'native-details.json', 'predictions.json', 'final-train-diagnostic-predictions.json',
             'shifted-dev-predictions.json', 'primary-selection.json']
    result = {'status': 'PAIRED_OBJECTIVE_VERIFIED', 'GPU': receipt['GPU'],
              'results': results, 'paired_pass_transitions_KL_then_CE': paired,
              'evidence_sha256': {n: hashlib.sha256((d/n).read_bytes()).hexdigest() for n in files},
              'same_initial_weights': True, 'same_order': True, 'same_steps': True,
              'teacher_unchanged': True, 'official_TEST_queries': 0, 'fresh_confirmation_queries': 0,
              'promotion': False,
              'scope': 'One seed, continued RedSage R120; TRAIN fit and already exposed development diagnostics. Not original Qwen, not independent benchmark generalization, not an ABA experiment.'}
    (d / 'objective-analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    analyze()
