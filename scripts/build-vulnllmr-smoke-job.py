#!/usr/bin/env python3
"""Package reviewed code and public train-only examples into one bounded GPU job."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--attempt', type=int, default=2)
parser.add_argument('--gpu-resource', choices=['nvidia.com/gpu', 'nvidia.com/h100', 'nvidia.com/a100'], default='nvidia.com/h100')
args = parser.parse_args()
assert args.attempt > 0
NAME = f'user-vulnllmr-dev-smoke-{args.attempt}'
labels = {'app.kubernetes.io/name': NAME, 'app.kubernetes.io/managed-by': 'cybergym-posttrain'}
image = json.loads((ROOT / 'configs/gpu-runtime-image.lock.json').read_text())['image']
inputs = {name: (ROOT / 'scripts' / name).read_text() for name in ['run-vulnllmr-smoke.py', 'vulnllmr_metrics.py']}
inputs['vulnllmr.lock.json'] = (ROOT / 'configs/vulnllmr.lock.json').read_text()
inputs['vulnllmr-development-smoke.json'] = (ROOT / 'data/manifests/vulnllmr-development-smoke.json').read_text()
shell = '''set -eu
export TMPDIR=/work/tmp HF_HOME=/work/hf PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_DISABLE_TELEMETRY=1
export HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export PYTHONDONTWRITEBYTECODE=1 WANDB_MODE=disabled
mkdir -p /work/tmp
python -m venv --system-site-packages /work/venv
printf 'torch==2.8.0\\n' > /work/torch-constraint.txt
/work/venv/bin/pip install --no-cache-dir -c /work/torch-constraint.txt transformers==4.57.6 accelerate==1.10.1 jinja2==3.1.6
/work/venv/bin/pip check
/work/venv/bin/python -u /input/run-vulnllmr-smoke.py
/work/venv/bin/python -c 'import json,subprocess; print("VULNLLMR_FREEZE="+json.dumps(subprocess.check_output(["/work/venv/bin/pip","freeze"],text=True).splitlines()))'
'''
resources = {'cpu': '2', 'memory': '16Gi', 'ephemeral-storage': '40Gi', args.gpu_resource: '1'}
cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': NAME + '-code', 'namespace': 'YOUR_NAMESPACE', 'labels': labels}, 'data': inputs}
pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
       'nodeSelector': {'kubernetes.io/arch': 'amd64'},
       'affinity': {'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {'nodeSelectorTerms': [
           {'matchExpressions': [{'key': 'nvidia.com/gpu.memory', 'operator': 'Gt', 'values': ['22999']}]}]}}},
       'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}},
       'containers': [{'name': 'smoke', 'image': image, 'command': ['bash', '-c', shell],
                       'resources': {'requests': resources, 'limits': resources.copy()},
                       'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                           'capabilities': {'drop': ['ALL']}},
                       'volumeMounts': [{'name': 'input', 'mountPath': '/input', 'readOnly': True}, {'name': 'work', 'mountPath': '/work'}]}],
       'volumes': [{'name': 'input', 'configMap': {'name': NAME + '-code'}}, {'name': 'work', 'emptyDir': {'sizeLimit': '40Gi'}}]}
if args.gpu_resource != 'nvidia.com/gpu':
    pod['priorityClassName'] = 'opportunistic'
    pod.pop('affinity')
job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': NAME, 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
       'spec': {'activeDeadlineSeconds': 1800, 'backoffLimit': 0, 'ttlSecondsAfterFinished': 3600,
                'template': {'metadata': {'labels': labels}, 'spec': pod}}}
dest = ROOT / 'configs/vulnllmr-smoke-job.json'
dest.write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': [cm, job]}, indent=2) + '\n')
print(json.dumps({'manifest': str(dest), 'name': NAME, 'resources': resources, 'deadline_seconds': 1800,
                  'priority_class': pod.get('priorityClassName', 'default')}))
