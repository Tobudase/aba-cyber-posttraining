"""Offline reconciliation of released diagnostic counts; not a model rerun."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/'results/kali-mode-repair-2026-11-16'
read = lambda n: json.loads((ROOT/n).read_text())
manifest = read('remaining-evidence-manifest.json')
for name, digest in manifest.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name


def check(reported, details, ids):
    assert len(ids) == len(set(ids)) == reported['n']
    c = collections.Counter(details[i] for i in ids)
    unknown = sum(v for k, v in c.items() if k.startswith('unknown'))
    assert reported['pass'] == reported['lower'] == c['fixture_pass']
    assert reported['fail'] == c['fixture_fail'] and reported['unknown'] == unknown
    assert reported['upper'] == c['fixture_pass'] + unknown
    assert sum(c.values()) == reported['n']


verified = []
for version in ['v11', 'v13']:
    if not (ROOT/(version+'-analysis.json')).exists():
        continue
    a = read(version+'-analysis.json')
    panels = read(version+'-panels.json')
    detail = read(version+'-functional-details.json')
    native = read(version+'-native-details.json')
    training = read(version+'-training-audit.json')
    steps = 192 if version == 'v11' else 96
    assert training['optimizer_steps'] == {'R': steps, 'RK': steps}
    assert training['order_hashes']['R'] == training['order_hashes']['RK']
    for arm in ['R', 'RK']:
        assert [t['step'] for t in training['traces'][arm]] == list(range(1, steps+1))
    old_base = {i for i in panels['primary']['old64'] if native['E0'][i]['strict']}
    for value in a['results'].values():
        label = value['storage_label'] if version == 'v11' else value['label']
        check(value['train384'], detail['finalfit'][label], panels['train'])
        for tool, ids in panels['train_by_tool'].items():
            check(value['train_by_tool'][tool], detail['finalfit'][label], ids)
        check(value['legacy64'], detail['primary'][label], panels['primary']['legacy_new64'])
        check(value['new_dev32' if version == 'v11' else 'newDEV32'], detail['primary'][label], panels['primary']['new_dev32'])
        check(value['shifted_dev64' if version == 'v11' else 'shiftedDEV64'], detail['shifted'][label], panels['shifted'])
        if version == 'v11':
            for mode, ids in panels['new_delta_PyI64_modes'].items():
                assert len(ids) == 16
                check(value['new_delta_PyI64_modes'][mode], detail['finalfit'][label], ids)
        got = {i for i in panels['primary']['old64'] if native[label][i]['strict']}
        assert value['old_retained' if version == 'v11' else 'old_base_retained'] == len(old_base & got)
        assert value['old_base_correct'] == len(old_base)
    assert a['official_TEST_queries'] == a['fresh_confirmation_queries'] == 0 and not a['promotion']
    if version == 'v13':
        for label, value in a['auxiliary24_training_fit_only'].items():
            assert len(value['per_id']) == value['n'] == 24
            assert sum(x['parser_matches'] for x in value['per_id'].values()) == value['source_parser_contract_matches']
            for tool, n in value['per_tool'].items():
                assert sum(x['parser_matches'] for x in value['per_id'].values() if x['tool'] == tool) == n
    verified.append(version)
if (ROOT/'v12-analysis.json').exists():
    a = read('v12-analysis.json')
    details = read('v12-functional-details.json')
    assert a['optimizer_steps'] == a['official_TEST_queries'] == a['fresh_confirmation_queries'] == 0
    for arm, rows in details.items():
        assert len(rows) == 48 and dict(collections.Counter(rows.values())) == a['arms'][arm]['counts']
        assert len(a['arms'][arm]['pairs']) == 12
        for pair in a['arms'][arm]['pairs']:
            for variant, verdict in pair['verdicts'].items():
                assert rows['kpath12-'+str(pair['pair'])+'-'+variant] == verdict
    if (ROOT/'v12-interpretation-summary.json').exists():
        extra = read('v12-interpretation-summary.json')
        for arm, value in extra['arms'].items():
            for variant, counts in value['by_root'].items():
                assert dict(collections.Counter(row['verdicts'][variant] for row in a['arms'][arm]['pairs'])) == counts
            assert value['functional_verdicts_equal_to_batch1_cacheTrue'] == sum(v == details['batch1_cacheTrue'][i] for i, v in details[arm].items())
    verified.append('v12')
assert verified
print('PASS: public hashes, row-level verdict totals, paired old retention, and real update counts:', ', '.join(verified))
