"""Recount case-level and paired results from the published CPU replay records."""
import json
from pathlib import Path


def recount(summary):
    seeds = summary['seeds']
    cases = summary['cases']
    assert len(cases) == 4 and len(set(seeds)) == len(seeds) == 3
    totals = {arm: {'behavior': 0, 'joint': 0, 'stable_cases': 0} for arm in ('blind', 'manual')}
    paired = {'both': 0, 'manual_only': 0, 'blind_only': 0, 'neither': 0}
    for case in cases.values():
        assert case['split'] == 'train' and case['prior_parameter_errors'] >= 2
        for arm, counts in totals.items():
            control = case[arm]['controls']
            assert [v['pass'] for v in control] == [True, False]
            assert control[0]['fixtures'] == [True, True]
            draws = case[arm]['draws']
            assert set(draws) == set(map(str, seeds))
            joint = 0
            for d in draws.values():
                if d['behavior']:
                    assert d['executed'] and d['fixtures'] == [True, True] and d['rc'] == [0, 0]
                assert len(d['response_sha256']) == 64
                assert d['joint'] == (d['fact'] and d['behavior'])
                counts['behavior'] += d['behavior']
                joint += d['joint']
            counts['joint'] += joint
            counts['stable_cases'] += joint >= 2
        for s in map(str, seeds):
            b = case['blind']['draws'][s]['joint']
            m = case['manual']['draws'][s]['joint']
            key = ('both' if m else 'blind_only') if b else ('manual_only' if m else 'neither')
            paired[key] += 1
    return {'totals': totals, 'paired_joint': paired}


if __name__ == '__main__':
    result = json.loads(Path(__file__).with_name('summary.json').read_text())
    actual = recount(result)
    assert actual == result['recount']
    assert actual['totals']['blind']['stable_cases'] == result['new_student_retest_items'] == 0
    print(json.dumps(actual, indent=2))
