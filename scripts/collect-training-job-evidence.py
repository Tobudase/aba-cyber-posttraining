#!/usr/bin/env python3
"""Collect only the two explicitly owned engineering jobs' logs and status."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'cpu': 'user-training-cpu-smoke', 'cuda': 'user-cuda-probe'}


def call(args):
    result = subprocess.run(['kubectl', '--context', 'nautilus', '-n', 'YOUR_NAMESPACE',
                             '--request-timeout=20s', *args],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr[-800:])
    if len(result.stdout.encode()) > 4 * 1024 * 1024:
        raise RuntimeError('Evidence output exceeds bound')
    return result.stdout


def block(text, marker):
    begin, end = marker + '_BEGIN', marker + '_END'
    if begin not in text or end not in text:
        return None
    return text.split(begin, 1)[1].split(end, 1)[0].strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=sorted(NAMES))
    parser.add_argument('--attempt', type=int, default=1, choices=range(1, 10))
    args = parser.parse_args()
    name = NAMES[args.kind] + (f'-retry{args.attempt - 1}' if args.kind == 'cpu' and args.attempt > 1 else '')
    job = json.loads(call(['get', 'job', name, '-o', 'json']))
    if job['metadata'].get('labels', {}).get('app.kubernetes.io/managed-by') != 'cybergym-posttrain':
        raise RuntimeError('Unexpected job ownership label')
    pods = json.loads(call(['get', 'pods', '-l', 'job-name=' + name, '-o', 'json']))
    started = any('running' in c.get('state', {}) or 'terminated' in c.get('state', {})
                  for p in pods.get('items', []) for c in p.get('status', {}).get('containerStatuses', []))
    log_error = None
    logs = ''
    if started:
        try:
            logs = call(['logs', 'job/' + name])
        except RuntimeError as error:
            log_error = str(error)
    dest = ROOT / 'docs/verification'
    (dest / (name + '.log')).write_text(logs)
    result = None
    marker = 'ENGINEERING_SMOKE_RESULT=' if args.kind == 'cpu' else 'CUDA_PROBE_RESULT='
    for line in logs.splitlines():
        if line.startswith(marker):
            result = json.loads(line[len(marker):])
    report = {'collected_at': datetime.now(timezone.utc).isoformat(), 'job': name,
              'job_uid': job['metadata']['uid'], 'namespace': 'YOUR_NAMESPACE',
              'job_status': job.get('status', {}),
              'container_started_observed': started, 'log_error': log_error,
              'pods': [{'name': p['metadata']['name'], 'phase': p.get('status', {}).get('phase'),
                        'node': p.get('spec', {}).get('nodeName'),
                        'conditions': p.get('status', {}).get('conditions', []),
                        'container_statuses': p.get('status', {}).get('containerStatuses', [])}
                       for p in pods.get('items', [])],
              'log_sha256': hashlib.sha256(logs.encode()).hexdigest(), 'result': result,
              'passed': result is not None and result.get('status') == 'PASSED'
                        and job.get('status', {}).get('succeeded') == 1}
    imports = block(logs, 'RUNTIME_IMPORTS')
    freeze = block(logs, 'LINUX_CPU_REQUIREMENTS')
    for line in logs.splitlines():
        if line.startswith('RUNTIME_IMPORTS_RESULT='):
            imports = line.split('=', 1)[1]
        elif line.startswith('LINUX_CPU_REQUIREMENTS_RESULT='):
            freeze = '\n'.join(json.loads(line.split('=', 1)[1]))
    if imports:
        (dest / 'linux-cpu-runtime-imports.json').write_text(json.dumps(json.loads(imports), indent=2) + '\n')
    if freeze:
        pins = [line.strip() for line in freeze.splitlines() if re.fullmatch(r'[A-Za-z0-9_.-]+==[^\s]+', line.strip())]
        if not pins or len(pins) != len(set(pins)):
            raise RuntimeError('Invalid dependency freeze output')
        (ROOT / 'configs/requirements-linux-cpu.lock.txt').write_text('\n'.join(pins) + '\n')
    (dest / (name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    if result:
        (dest / ('tiny-lora-smoke.json' if args.kind == 'cpu' else 'cuda-probe.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'job': name, 'passed': report['passed'], 'result': result,
                      'job_conditions': job.get('status', {}).get('conditions', [])}, indent=2))


if __name__ == '__main__':
    main()
