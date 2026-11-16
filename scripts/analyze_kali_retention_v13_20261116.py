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
    prior = ROOT/'data/benchkit/kali-execution-2026-11-14/miw113-kali-objective-v11-r2-1116'
    pr = json.loads((prior/'receipt.json').read_text())
    assert r['source_adapter_sha256'] == pr['checkpoints']['RK_step192']['weights_sha256']
    assert r['anchor_weights_sha256'] == pr['source_adapter_sha256']
    pp = json.loads((prior/'predictions.json').read_text())
    replication = {}
    for current, previous in [('E0','E0'),('F22','F22'),('W0','RK_step192')]:
        left = {x['id']:x for x in pp[previous]}
        right = {x['id']:x for x in predictions[current]}
        assert left.keys() == right.keys() and len(left) == 192
        replication[current] = {'previous_label':previous,'n':192,
                                'identical_responses':sum(left[i]['response']==right[i]['response'] for i in left),
                                'identical_all_fields':sum(left[i]==right[i] for i in left)}
    left = {x['id']:x for x in pr['shifted_dev_outputs']['RK_step192']}
    right = {x['id']:x for x in r['shifted_dev_outputs']['W0']}
    assert left.keys() == right.keys() and len(left) == 64
    replication['W0_shifted'] = {'previous_label':'RK_step192','n':64,
                                 'identical_responses':sum(left[i]['response']==right[i]['response'] for i in left),
                                 'identical_all_fields':sum(left[i]==right[i] for i in left)}
    old = set(r['panels']['old64'])
    base = {i for i in old if native['E0'][i]['strict']}
    source = {i for i in old if native['W0'][i]['strict']}
    refs = json.loads((ROOT/cfg['data_directory']/'references-private.json').read_text())
    shifted_rows = json.loads((ROOT/cfg['data_directory']/'fixtures.json').read_text())['shifted_dev']
    shifted_meta = {x['id']:x for x in shifted_rows}
    assert set(shifted_meta) == set(shifted['W0'])
    shifted_predictions = {label:{x['id']:x for x in rows} for label, rows in r['shifted_dev_outputs'].items()}
    def output_options(response):
        output = re.findall(r'<output>(.*?)</output>',response,re.S)
        assert len(output) == 1
        return {x.split('=',1)[0] for x in shlex.split(output[0]) if x.startswith('--')}
    shifted_diagnosis = {}
    for label in ['R_step96','RK_step96']:
        gained = sorted(i for i in shifted[label] if shifted[label][i]=='fixture_pass' and shifted['W0'][i]!='fixture_pass')
        lost = sorted(i for i in shifted[label] if shifted['W0'][i]=='fixture_pass' and shifted[label][i]!='fixture_pass')
        shifted_diagnosis[label] = {'gained_PASS_vs_source':gained,'lost_PASS_vs_source':lost,
            'lost_case_option_changes':{i:{'tool':shifted_meta[i]['tool'],
                'added_option_names':sorted(output_options(shifted_predictions[label][i]['response']) - output_options(shifted_predictions['W0'][i]['response'])),
                'removed_option_names':sorted(output_options(shifted_predictions['W0'][i]['response']) - output_options(shifted_predictions[label][i]['response']))}
                for i in lost},
            'interpretation':'Observed output option differences only; not a separate counterfactual execution or a unique optimization-mechanism proof.'}
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
    old_case_parser = {}
    for case_id in ['sample_2933','sample_4867']:
        ref = refs[case_id]
        parser = module.parsers[ref['tool_name']]
        expected_args = vars(parser.parse_args(shlex.split(ref['ground_truth_command'])[1:]))
        old_case_parser[case_id] = {}
        for label in ['W0','R_step96','RK_step96']:
            row = next(x for x in predictions[label] if x['id'] == case_id)
            matches = re.findall(r'<output>(.*?)</output>',row['response'],re.S)
            argv = []
            accepted = correct = False
            try:
                if len(matches) == 1:
                    argv = shlex.split(matches[0])
                    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                        parsed = vars(parser.parse_args(argv[1:]))
                    accepted = bool(argv) and argv[0] == ref['tool_name']
                    correct = accepted and not row['truncated'] and parsed == expected_args
            except (SystemExit,ValueError):
                pass
            old_case_parser[case_id][label] = {'parser_accepts':accepted,'argument_values_match_reference':correct,
                'unsupported_option_names':sorted({a.split('=',1)[0] for a in argv if a.startswith('--') and a.split('=',1)[0] not in parser._option_string_actions})}
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
    from benchkit import native_kali, strict_option_values
    native_scorer = native_kali()
    trusted_fit = {}
    for label, rows in r['trusted_train_predictions'].items():
        assert len(rows) == 64 and {x['id'] for x in rows} == set(r['training_trusted_ids'])
        items = {}
        for row in rows:
            value = native_scorer.score_one(refs[row['id']],row['response'])
            items[row['id']] = {'native':value['total_score'],
                'strict':not row['truncated'] and bool(strict_option_values(refs[row['id']],row['response'],native_scorer)),
                'truncated':row['truncated']}
        trusted_fit[label] = {'n':64,'strict':sum(x['strict'] for x in items.values()),
                             'native_points':100*sum(x['native'] for x in items.values())/64,
                             'truncated':sum(x['truncated'] for x in items.values()),'per_id':items}
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
            'label': label,
            'training_seconds':sum(t['window_wall_seconds'] for t in r['traces'][arm]),
            'clipped_steps':sum(t['grad_norm_before_clip'] > 1 for t in r['traces'][arm]),
            'logged_loss_trends':{key:{'first16_mean':sum(t[key] for t in r['traces'][arm][:16])/16,'last16_mean':sum(t[key] for t in r['traces'][arm][-16:])/16} for key in ['auxiliary_replay_loss_example_mean','new_primary_objective_example_mean','old_source_KL_token_mean']},
            'train384': count(fit[label], list(fixtures)),
            'train_by_tool': {t: count(fit[label], [i for i, x in fixtures.items() if x['tool'] == t])
                              for t in sorted({x['tool'] for x in fixture_rows})},
            'legacy64': count(primary[label], r['panels']['legacy_new64']),
            'newDEV32': count(primary[label], r['panels']['new_dev32']),
            'shiftedDEV64': count(shifted[label], r['extra_panels']['shifted_dev64']),
            'shifted_by_tool':{tool:count(shifted[label],[i for i,x in shifted_meta.items() if x['tool']==tool])
                               for tool in sorted({x['tool'] for x in shifted_rows})},
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
              'auxiliary24_training_fit_only': auxiliary,
              'trusted64_training_fit_only':trusted_fit, 'GPU': r['GPU'],
              'cross_run_baseline_replication':replication,
              'source_is_frozen_v11_CE_endpoint':True,'old_anchor_is_original_R120':True,
              'source_old_strict': len(source), 'base_old_strict': len(base),
              'optimizer_steps_each': 96, 'auxiliary_exposures_each': 384,
              'evidence_sha256': {n: hashlib.sha256((d/n).read_bytes()).hexdigest() for n in files},
              'old_cases_source_parser':old_case_parser,
              'shifted_change_diagnosis':shifted_diagnosis,
              'source_parser_business_logic_executions': 0, 'official_TEST_queries': 0,
              'fresh_confirmation_queries': 0, 'promotion': False,
              'scope': 'One seed, adaptive exposed development diagnosis. Auxiliary24 checks TRAIN fit with an argument parser, not runtime behavior or independent generalization.'}
    (d/'replay-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    analyze()
