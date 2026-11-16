"""Publish completed evidence only; does not launch jobs, commit, or push."""
import collections
import hashlib
import json
import shutil
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/benchkit/kali-execution-2026-11-14'
PUBLIC = ROOT.parent/'github-publication/aba-cyber-posttraining'
DEST = PUBLIC/'results/kali-mode-repair-2026-11-16'


def write(n, value):
    (DEST/n).write_text(json.dumps(value, indent=2)+'\n')


def publish():
    reports = {}
    for version, name, analysis in [
        ('v11', 'miw113-kali-objective-v11-r2-1116', 'objective-analysis.json'),
        ('v13', 'miw113-kali-retention-v13-1116', 'replay-analysis.json'),
    ]:
        d = OUT/name
        if not (d/analysis).exists():
            continue
        assert json.loads((d/'host.json').read_text()).get('resources_cleaned')
        value = json.loads((d/analysis).read_text())
        reports[version] = value
        write(version+'-analysis.json', value)
        phases = {phase: json.loads((d/('behavior-'+phase+'-details.json')).read_text())
                  for phase in ['primary', 'finalfit', 'shifted']}
        write(version+'-functional-details.json', phases)
        write(version+'-native-details.json', json.loads((d/'native-details.json').read_text()))
        receipt = json.loads((d/'receipt.json').read_text())
        cfg = json.loads(json.loads((d/'objects.json').read_text())[0]['data']['config.json'])
        refs = json.loads((ROOT/cfg['data_directory']/'references-private.json').read_text())
        shifted_rows = json.loads((ROOT/cfg['data_directory']/'fixtures.json').read_text())['shifted_dev']
        fx = [{'id': i, 'tool': refs[i]['tool_name'], 'argv': shlex.split(refs[i]['ground_truth_command'])} for i in receipt['training_new_ids']]
        assert len(fx) == 384 and len({x['id'] for x in fx}) == 384
        delta = {r['id'] for r in json.loads((ROOT/'data/benchkit/kali-counterfactual-v9-2026-11-16/new-delta144.json').read_text())}
        panels = {'primary': receipt['panels'], 'shifted': receipt['extra_panels']['shifted_dev64'],
                  'shifted_by_tool':{t:[r['id'] for r in shifted_rows if r['tool']==t] for t in sorted({r['tool'] for r in shifted_rows})},
                  'train': [r['id'] for r in fx],
                  'train_by_tool': {t: [r['id'] for r in fx if r['tool'] == t] for t in sorted({r['tool'] for r in fx})},
                  'new_delta_PyI64_modes': {b+'_'+c: [r['id'] for r in fx if r['id'] in delta and r['tool']=='pyi-makespec' and '--'+b in r['argv'] and '--'+c in r['argv']]
                                           for b in ['onefile', 'onedir'] for c in ['console', 'windowed']}}
        write(version+'-panels.json', panels)
        write(version+'-training-audit.json', {k: receipt[k] for k in [
            'optimizer_steps', 'order_hashes', 'checkpoints', 'source_adapter_sha256', 'worker_sha256',
            'config_sha256', 'GPU', 'traces', 'official_TEST_queries']})
        write(version+'-selection.json', json.loads((d/'primary-selection.json').read_text()))
    p = OUT/'miw113-kali-path-v12-1116'
    if (p/'analysis.json').exists():
        a = json.loads((p/'analysis.json').read_text())
        assert a['optimizer_steps'] == 0
        # Do not publish model commands or private prompt/fixture bodies.
        cleaned = {**a, 'arms': {k: {kk: vv for kk, vv in v.items() if kk != 'normalized_commands'}
                                  for k, v in a['arms'].items()}}
        reports['v12'] = cleaned
        write('v12-analysis.json', cleaned)
        write('v12-functional-details.json', json.loads((p/'behavior-finalfit-details.json').read_text()))
    if not reports:
        print('NO_COMPLETED_NEW_RESULT')
        return
    resource = OUT/'remaining-experiments-resource-audit-20261116.json'
    if resource.exists():
        write('v13-batch-resource-audit.json',json.loads(resource.read_text()))
    files=list(DEST.glob('v1[123]-*.json'))
    files += [DEST/n for n in ['remaining-status.json','objective-comparison.png','path-invariance.png','replay-content-comparison.png'] if (DEST/n).exists()]
    manifest = {n.name: hashlib.sha256(n.read_bytes()).hexdigest() for n in sorted(files)}
    write('remaining-evidence-manifest.json', manifest)
    print(json.dumps({'published_completed': sorted(reports), 'evidence_files': len(manifest)}))
    return reports


if __name__ == '__main__':
    publish()
