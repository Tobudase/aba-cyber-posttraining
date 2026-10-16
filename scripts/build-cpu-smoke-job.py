#!/usr/bin/env python3
"""Package an explicit non-secret allowlist into a bounded CPU-only Job."""
import base64
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['scripts/install-training-cpu.sh', 'scripts/smoke-lora-cpu.py',
         'scripts/prepare-model-tokenizer.py', 'configs/training-requirements.in',
         'configs/student-model.lock.json', 'configs/training-template.lock.json',
         'configs/templates/qwen3_training.jinja', 'configs/templates/TRL-LICENSE.txt']

BOOTSTRAP = r'''
import hashlib, json, os, pathlib, subprocess, sys, tarfile, traceback
root=pathlib.Path('/work')
root.mkdir(exist_ok=True)
(root/'tmp').mkdir(exist_ok=True)
os.chdir(root)
os.environ['TRAINING_ROOT']=str(root)
os.environ['TMPDIR']=str(root/'tmp')
os.environ['HF_HOME']=str(root/'hf-cache')
bundle=pathlib.Path('/input/bundle.tgz')
if hashlib.sha256(bundle.read_bytes()).hexdigest()!=os.environ['BUNDLE_SHA256']:
    raise RuntimeError('Bundle checksum mismatch')
with tarfile.open(bundle,'r:gz') as archive:
    for member in archive.getmembers():
        path=pathlib.PurePosixPath(member.name)
        if not member.isfile() or member.size>200000 or path.is_absolute() or '..' in path.parts:
            raise RuntimeError('Unsafe bundle entry')
        dest=root/member.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(archive.extractfile(member).read())
failure=0
try:
    subprocess.run(['bash','scripts/install-training-cpu.sh'],check=True,timeout=1250,stderr=subprocess.STDOUT)
    subprocess.run(['python','scripts/prepare-model-tokenizer.py'],check=True,timeout=240,stderr=subprocess.STDOUT)
    subprocess.run(['.venv/bin/python','-u','scripts/smoke-lora-cpu.py'],check=True,timeout=180,stderr=subprocess.STDOUT)
except Exception:
    traceback.print_exc(file=sys.stdout)
    failure=1
finally:
    for name in ['torch-install.log','runtime-install.log','pip-check.txt']:
        p=root/'logs'/name
        if p.is_file():
            print('LOG_TAIL '+name,flush=True)
            print(*p.read_text(errors='replace').splitlines()[-35:],sep=chr(10),flush=True)
    for marker,name in [('RUNTIME_IMPORTS','runtime-imports.json'),('LINUX_CPU_REQUIREMENTS','requirements-linux-cpu.lock.txt')]:
        p=root/'logs'/name
        if p.is_file():
            value=json.loads(p.read_text()) if name.endswith('.json') else p.read_text().splitlines()
            print(marker+'_RESULT='+json.dumps(value),flush=True)
raise SystemExit(failure)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, default=1, choices=range(1, 10))
    args = parser.parse_args()
    stream = io.BytesIO()
    manifest = {}
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name in FILES:
            data = (ROOT / name).read_bytes()
            manifest[name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    bundle = stream.getvalue()
    if len(bundle) > 256 * 1024:
        raise RuntimeError('Bundle unexpectedly large')
    image = json.loads((ROOT / 'configs/cpu-runtime-image.lock.json').read_text())['image']
    name = 'user-training-cpu-smoke' + (f'-retry{args.attempt - 1}' if args.attempt > 1 else '')
    labels = {'app.kubernetes.io/name': name, 'app.kubernetes.io/managed-by': 'cybergym-posttrain'}
    resources = {'cpu': '2', 'memory': '3Gi', 'ephemeral-storage': '6Gi'}
    configmap = {'apiVersion': 'v1', 'kind': 'ConfigMap',
                 'metadata': {'name': name + '-code', 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
                 'binaryData': {'bundle.tgz': base64.b64encode(bundle).decode()}}
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': name, 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
           'spec': {'activeDeadlineSeconds': 1500, 'backoffLimit': 0, 'ttlSecondsAfterFinished': 86400,
                    'template': {'metadata': {'labels': labels}, 'spec': {
                        'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                        'nodeSelector': {'kubernetes.io/arch': 'amd64'},
                        'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000,
                                            'seccompProfile': {'type': 'RuntimeDefault'}},
                        'containers': [{'name': 'validate', 'image': image,
                            'command': ['python', '-u', '-c', BOOTSTRAP],
                            'env': [{'name': 'BUNDLE_SHA256', 'value': hashlib.sha256(bundle).hexdigest()},
                                    {'name': 'PYTHONDONTWRITEBYTECODE', 'value': '1'}],
                            'resources': {'requests': resources, 'limits': resources.copy()},
                            'securityContext': {'allowPrivilegeEscalation': False,
                                                'readOnlyRootFilesystem': True,
                                                'capabilities': {'drop': ['ALL']}},
                            'volumeMounts': [{'name': 'code', 'mountPath': '/input', 'readOnly': True},
                                             {'name': 'work', 'mountPath': '/work'}]}],
                        'volumes': [{'name': 'code', 'configMap': {'name': name + '-code'}},
                                    {'name': 'work', 'emptyDir': {'sizeLimit': '6Gi'}}]}}}}
    dest = ROOT / 'configs/cpu-smoke-job.json'
    dest.write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': [configmap, job]}, indent=2) + '\n')
    report = {'bundle_sha256': hashlib.sha256(bundle).hexdigest(), 'source_sha256': manifest,
              'image': image, 'cpu': 2, 'memory': '3Gi', 'gpu_requested': 0,
              'deadline_seconds': 1500, 'job': name, 'namespace': 'YOUR_NAMESPACE'}
    (ROOT / 'docs/verification/cpu-smoke-source-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'manifest': str(dest), 'bundle_bytes': len(bundle), 'gpu_requested': 0}, indent=2))


if __name__ == '__main__':
    main()
