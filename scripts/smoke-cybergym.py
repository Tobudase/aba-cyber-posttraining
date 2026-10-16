"""Finite, local infrastructure test; no model calls or exploit generation."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

import requests

ROOT = Path.home() / 'cybergym-project'
SRC = ROOT / 'src/cybergym'
LOG = ROOT / 'logs'
REVISION = 'bde190ded494e52bc684b66073b436c9d992c7c6'
TASK_ID = 'arvo:10400'
LOG.mkdir(parents=True, exist_ok=True)
report = {'kind': 'infrastructure_smoke_only', 'task_id': TASK_ID, 'dataset_revision': REVISION,
          'started_at': datetime.now(timezone.utc).isoformat(),
          'difficulty': 'level1', 'model_called': False, 'checks': {}, 'files': {}, 'images': {}}
report_path = LOG / 'smoke-report.json'

def save():
    report_path.write_text(json.dumps(report, indent=2) + '\n')

try:
    data = ROOT / 'data/arvo/10400'
    data.mkdir(parents=True, exist_ok=True)
    for name in ['repo-vul.tar.gz', 'description.txt']:
        url = f'https://huggingface.co/datasets/sunblaze-ucb/cybergym/resolve/{REVISION}/data/arvo/10400/{name}'
        dest = data / name
        if not dest.exists():
            tmp = dest.with_suffix(dest.suffix + '.partial')
            with urllib.request.urlopen(url, timeout=90) as response, tmp.open('wb') as out:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 300 * 1024**2:
                        raise RuntimeError('Single task file exceeded 300 MiB guard')
                    out.write(chunk)
            tmp.rename(dest)
        report['files'][name] = {'bytes': dest.stat().st_size, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
    from cybergym.task.gen_task import generate_task
    from cybergym.task.types import TaskConfig, TaskDifficulty
    out = ROOT / 'tasks/arvo-10400-smoke'
    out.mkdir(parents=True, exist_ok=True)
    task = generate_task(TaskConfig(task_id=TASK_ID, agent_id='user-infra-smoke-' + secrets.token_hex(4),
        out_dir=out, data_dir=ROOT / 'data', server='http://127.0.0.1:8666',
        difficulty=TaskDifficulty.level1, salt='CyberGym', mask_map_path=SRC / 'mask_map.json'))
    assert all((out / f).is_file() for f in ['repo-vul.tar.gz', 'description.txt', 'README.md', 'submit.sh'])
    assert not any((out / f).exists() for f in ['repo-fix.tar.gz', 'patch.diff', 'poc'])
    report['checks']['task_generation'] = 'passed'
    save()
    for mode in ['vul', 'fix']:
        image = f'n132/arvo:10400-{mode}'
        manifest = json.loads(subprocess.check_output(['docker', 'manifest', 'inspect', image], timeout=90))
        size = sum(layer.get('size', 0) for layer in manifest.get('layers', []))
        if not manifest.get('layers') or size > 8 * 1024**3:
            raise RuntimeError(f'Image size requires manual review: {image}')
        if shutil.disk_usage(ROOT).free < max(20 * 1024**3, 3 * size):
            raise RuntimeError('Insufficient disk headroom')
        with (LOG / f'pull-{mode}.log').open('w') as log:
            subprocess.run(['docker', 'pull', image], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], timeout=30))[0]
        report['images'][image] = {'id': info['Id'], 'repo_digests': info.get('RepoDigests', []), 'compressed_bytes': size}
        save()
    server_logs = ROOT / 'server-smoke'
    server_logs.mkdir(exist_ok=True)
    env = dict(os.environ)
    env['CYBERGYM_API_KEY'] = secrets.token_urlsafe(32)
    with (LOG / 'server-smoke.log').open('w') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'cybergym.server', '--host', '127.0.0.1',
            '--port', '8666', '--mask_map_path', str(SRC / 'mask_map.json'),
            '--log_dir', str(server_logs), '--db_path', str(server_logs / 'poc.db')],
            cwd=SRC, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(60):
                if proc.poll() is not None:
                    raise RuntimeError('Server exited; see server-smoke.log')
                try:
                    r = requests.get('http://127.0.0.1:8666/openapi.json', timeout=2)
                    if r.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)
            else:
                raise TimeoutError('Server readiness timeout')
            report['checks']['server_ready'] = 'passed'
            # A four-byte neutral input is a plumbing test, NOT a successful PoC.
            from cybergym.task.mask import mask_task_id
            metadata = {'task_id': mask_task_id(TASK_ID), 'agent_id': task.agent_id,
                        'checksum': task.checksum, 'require_flag': False}
            r = requests.post('http://127.0.0.1:8666/submit-vul', data={'metadata': json.dumps(metadata)},
                files={'file': ('neutral-input.bin', b'\x00\x01\x02\x03', 'application/octet-stream')}, timeout=90)
            r.raise_for_status()
            response = r.json()
            (LOG / 'neutral-submit-result.json').write_text(json.dumps(response, indent=2) + '\n')
            assert 'poc_id' in response and 'exit_code' in response
            report['checks']['neutral_input_submission'] = 'passed'
            # Exercise the patched image explicitly: verify-agent-pocs skips
            # inputs which do not crash the vulnerable image.
            r = requests.post('http://127.0.0.1:8666/submit-fix', data={'metadata': json.dumps(metadata)},
                files={'file': ('neutral-input.bin', b'\x00\x01\x02\x03', 'application/octet-stream')},
                headers={'X-API-Key': env['CYBERGYM_API_KEY']}, timeout=90)
            r.raise_for_status()
            fix_response = r.json()
            assert 'poc_id' in fix_response and 'exit_code' in fix_response
            (LOG / 'neutral-fix-result.json').write_text(json.dumps(fix_response, indent=2) + '\n')
            report['checks']['patched_image_execution'] = 'passed'
            report['neutral_input_fix_exit_code'] = fix_response['exit_code']
            r = requests.post('http://127.0.0.1:8666/verify-agent-pocs', json={'agent_id': task.agent_id},
                headers={'X-API-Key': env['CYBERGYM_API_KEY']}, timeout=180)
            r.raise_for_status()
            verification = r.json()
            (LOG / 'neutral-verification-result.json').write_text(json.dumps(verification, indent=2) + '\n')
            report['checks']['verification_endpoint'] = 'passed'
            report['neutral_input_exit_code'] = response['exit_code']
            report['note'] = 'Infrastructure only. Not a model evaluation, successful exploit, or training trajectory.'
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    save()
    print(json.dumps(report, indent=2))
except Exception as exc:
    report['error'] = f'{type(exc).__name__}: {exc}'
    save()
    raise
