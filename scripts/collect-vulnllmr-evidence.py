#!/usr/bin/env python3
"""Collect this project's bounded development job only; optionally clean terminal jobs."""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ['kubectl', '--context', 'nautilus', '-n', 'YOUR_NAMESPACE']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleanup', action='store_true')
    parser.add_argument('--job', default='user-vulnllmr-dev-smoke-6')
    parser.add_argument('--report-kind', choices=['cpu', 'gpu'], default='cpu')
    args = parser.parse_args()
    if not re.fullmatch(r'user-vulnllmr-dev-smoke-[1-9]\d*', args.job):
        raise ValueError('Only this project development job name is allowed')
    NAME = args.job
    def get(*cmd):
        return json.loads(subprocess.check_output(BASE + list(cmd)))
    job = get('get', 'job', NAME, '-o', 'json')
    pods = get('get', 'pods', '-l', 'app.kubernetes.io/name=' + NAME, '-o', 'json')['items']
    report = {'collected_at': datetime.now(timezone.utc).isoformat(), 'job': NAME,
              'job_status': job.get('status', {}), 'pods': [], 'model_result': None, 'cleanup': False}
    combined = []
    for pod in pods:
        name, status = pod['metadata']['name'], pod.get('status', {})
        entry = {'name': name, 'status': status}
        events = get('get', 'events', '--field-selector', 'involvedObject.uid=' + pod['metadata']['uid'], '-o', 'json')
        entry['events'] = [{'reason': e.get('reason'), 'message': e.get('message'), 'count': e.get('count')} for e in events['items']]
        if status.get('phase') in {'Running', 'Succeeded', 'Failed'}:
            result = subprocess.run(BASE + ['logs', name, '--limit-bytes=1500000'], capture_output=True, text=True)
            if result.returncode == 0:
                combined.append(result.stdout)
        report['pods'].append(entry)
    log = '\n'.join(combined)
    for line in log.splitlines():
        if line.startswith('VULNLLMR_SMOKE_RESULT='):
            model_result = json.loads(line.split('=', 1)[1])
            lock = json.loads((ROOT / 'configs/vulnllmr.lock.json').read_text())
            assert model_result['revision'] == lock['revision'] and model_result['model_id'] == lock['model_id']
            assert model_result['formal_test_used'] is False and model_result['training_executed'] is False
            assert len(model_result['rows']) == 4
            report['model_result'] = model_result
        if line.startswith('VULNLLMR_FREEZE='):
            report['pip_freeze'] = json.loads(line.split('=', 1)[1])
    conditions = job.get('status', {}).get('conditions', [])
    terminal = any(x.get('type') in {'Complete', 'Failed'} and x.get('status') == 'True' for x in conditions)
    report['terminal'] = terminal
    report['inference_verified'] = report['model_result'] is not None
    if args.cleanup:
        if not terminal:
            raise RuntimeError('Refusing cleanup of an active job; collect without --cleanup to inspect')
        subprocess.check_call(BASE + ['delete', 'job', NAME, '--wait=true', '--timeout=60s'])
        subprocess.check_call(BASE + ['delete', 'configmap', NAME + '-code', '--wait=true', '--timeout=30s'])
        report['cleanup'] = True
    folder = ROOT / 'docs/verification'
    (folder / ('vulnllmr-' + args.report_kind + '-smoke.log')).write_text(log)
    (folder / ('vulnllmr-' + args.report_kind + '-smoke.json')).write_text(json.dumps(report, indent=2) + '\n')
    (folder / (NAME + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    (folder / (NAME + '.log')).write_text(log)
    print(json.dumps({k: report[k] for k in ['job', 'terminal', 'inference_verified', 'cleanup']}, indent=2))
    for pod in report['pods']:
        print(json.dumps({'pod': pod['name'], 'phase': pod['status'].get('phase'), 'events': pod['events'][-2:]}))


if __name__ == '__main__':
    main()
