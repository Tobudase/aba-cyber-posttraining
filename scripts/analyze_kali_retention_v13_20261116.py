"""Audit the frozen replay-content comparison, including parser-only auxiliary fit."""
import collections
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze(name='miw113-kali-retention-v13-1116'):
    d = ROOT / 'data/benchkit/kali-execution-2026-11-14' / name
    read = lambda n: json.loads((d/n).read_text())
    r = read('receipt.json')
    cfg = json.loads(read('objects.json')[0]['data']['config.json'])
    assert read('export-audit.json')['all_weights_verified']
    assert r['optimizer_steps'] == {'R': 96, 'RK': 96}
    assert r['order_hashes']['R'] == r['order_hashes']['RK']
    assert r['anchor_unchanged'] and r['anchor_weights_sha256'] == cfg['anchor_weights_sha256']
    assert r['source_adapter_sha256'] == cfg['source_weights_sha256']
    assert not (d/'confirmation.json').exists() and r['official_TEST_queries'] == 0
    fit = read('behavior-finalfit-details.json')
    primary = read('behavior-primary-details.json')
    shifted = read('behavior-shifted-details.json')
    native = read('native-details.json')
    scores = read('summary.json')
    predictions = read('predictions.json')
    old = set(r['panels']['old64'])
    base = {i for i in old if native['E0'][i]['strict']}
    source = {i for i in old if native['W0'][i]['strict']}
    refs = json.loads((ROOT/cfg['data_directory']/'references-private.json').read_text())
    fixture_rows = [{'id': i, 'tool': refs[i]['tool_name']} for i in r['training_new_ids']]
    fixtures = {x['id']: x for x in fixture_rows}
    assert len(fixtures) == len(fixture_rows) == 384
    def count(dd, ids):
        c = collections.Counter(dd[i] for i in ids)
        unknown = sum(v for k, v in c.items() if k.startswith('unknown'))
        return {'n': len(ids), 'pass': c['fixture_pass'], 'fail': c['fixture_fail'],
                'unknown': unknown, 'lower': c['fixture_pass'], 'upper': c['fixture_pass']+unknown}
    # This module extracts argparse declarations only; it never runs the tools.
    spec = importlib.util.spec_from_file_location('old_contract_parsers', ROOT/'scripts/check_old_intent_contracts_20261116.py')
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    contracts = json.loads((ROOT/'data/benchkit/kali-old-intent-contracts-2026-11-16/draft-contracts.json').read_text())
    expected = {x['id']: x for x in contracts}
    auxiliary = {}
    for label, rows in r['auxiliary_predictions'].items():
        assert len(rows) == 48 and len({x['id'] for x in rows}) == 48
        checked = {}
        for pred in rows:
            if pred['id'] not in expected:
                continue
            ref = expected[pred['id']]
            parser = module.parsers[ref['tool']]
            m = re.findall(r'<output>(.*?)</output>', pred['response'], re.S)
            result = False
            if len(m) == 1 and not pred['truncated']:
                try:
                    argv = shlex.split(m[0])
                    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                        result = bool(argv) and argv[0] == ref['tool'] and vars(parser.parse_args(argv[1:])) == vars(parser.parse_args(ref['argv'][1:]))
                except (SystemExit, ValueError):
                    result = False
            checked[pred['id']] = result
        assert set(checked) == set(expected)
        auxiliary[label] = {'source_parser_contract_matches': sum(checked.values()), 'n': 24,
                            'per_id': {i: {'tool': expected[i]['tool'], 'parser_matches': verdict} for i, verdict in checked.items()},
                            'per_tool': {t: sum(checked[i] for i, x in expected.items() if x['tool'] == t)
                                         for t in ['smb2-quota', 'sprayhound']}}
    results = {}
    for label, content in [('R_step96', 'existing_intents'), ('RK_step96', 'missing_intents')]:
        arm = label.split('_')[0]
        assert len(r['traces'][arm]) == 96 and r['checkpoints'][label]['teacher_source_unchanged']
        assert [t['step'] for t in r['traces'][arm]] == list(range(1, 97))
        assert all(t['objective'] == 'command_CE' and math.isfinite(t['grad_norm_before_clip']) and t['grad_norm_before_clip'] > 0 for t in r['traces'][arm])
        assert len(r['auxiliary_training_ids'][arm]) == 24
        assert set(fit[label]) == set(fixtures) and len(fixtures) == 384
        correct = {i for i in old if native[label][i]['strict']}
        results[content] = {
            'label': label, 'train384': count(fit[label], list(fixtures)),
            'train_by_tool': {t: count(fit[label], [i for i, x in fixtures.items() if x['tool'] == t])
                              for t in sorted({x['tool'] for x in fixture_rows})},
            'legacy64': count(primary[label], r['panels']['legacy_new64']),
            'newDEV32': count(primary[label], r['panels']['new_dev32']),
            'shiftedDEV64': count(shifted[label], r['extra_panels']['shifted_dev64']),
            'old_base_retained': len(base & correct), 'old_base_correct': len(base),
            'old_lost_vs_base': sorted(base - correct), 'old_gained_vs_source': sorted(correct - source),
            'old_lost_vs_source': sorted(source - correct), 'old_strict': len(correct),
            'old_native_points': scores[label]['old64']['native_points'],
            'truncated_primary': sum(x['truncated'] for x in predictions[label]),
            'truncated_fullTRAIN': sum(x['truncated'] for x in r['full_train_predictions'][label]),
            'truncated_shifted': sum(x['truncated'] for x in r['shifted_dev_outputs'][label]),
            'weights_sha256': r['checkpoints'][label]['weights_sha256'],
        }
    files = ['receipt.json', 'export-audit.json', 'behavior-primary-details.json',
             'behavior-finalfit-details.json', 'behavior-shifted-details.json', 'native-details.json',
             'summary.json', 'primary-selection.json']
    result = {'status': 'REPLAY_CONTENT_COMPARISON_VERIFIED', 'results': results,
              'auxiliary24_training_fit_only': auxiliary, 'GPU': r['GPU'],
              'source_old_strict': len(source), 'base_old_strict': len(base),
              'optimizer_steps_each': 96, 'auxiliary_exposures_each': 384,
              'evidence_sha256': {n: hashlib.sha256((d/n).read_bytes()).hexdigest() for n in files},
              'source_parser_business_logic_executions': 0, 'official_TEST_queries': 0,
              'fresh_confirmation_queries': 0, 'promotion': False,
              'scope': 'One seed, adaptive exposed development diagnosis. Auxiliary24 checks TRAIN fit with an argument parser, not runtime behavior or independent generalization.'}
    (d/'replay-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    analyze()
