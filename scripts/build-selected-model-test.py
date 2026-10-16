#!/usr/bin/env python3
"""Package only synthetic test code and public metadata into a bounded Job."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['cpu', 'gpu'], required=True)
    p.add_argument('--attempt', type=int, default=1)
    p.add_argument('--gpu-resource', default='nvidia.com/a40')
    args = p.parse_args()
    name = f'user-qwen27-test-{args.mode}-{args.attempt}'
    labels = {'app.kubernetes.io/name': name, 'app.kubernetes.io/managed-by': 'cybergym-posttrain'}
    cpu = args.mode == 'cpu'
    image = json.loads((ROOT / ('configs/cpu-runtime-image.lock.json' if cpu else 'configs/gpu-runtime-image.lock.json')).read_text())['image']
    shell = '''set -eu
export TMPDIR=/work/tmp HF_HOME=/work/hf-cache PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_DISABLE_TELEMETRY=1
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
mkdir -p /work/tmp
python -m venv ''' + ('' if cpu else '--system-site-packages ') + '''/work/venv
''' + ('''/work/venv/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0
''' if cpu else '') + '''printf 'torch==2.8.0\\n' > /work/torch-constraint.txt
/work/venv/bin/pip install --no-cache-dir -c /work/torch-constraint.txt transformers==5.20.0 peft==0.21.2 accelerate==1.15.0 ''' + ('' if cpu else 'bitsandbytes==0.50.2 ') + '''jinja2==3.1.6
/work/venv/bin/pip check
/work/venv/bin/python -u /input/test-selected-model.py --mode ''' + args.mode + '''
/work/venv/bin/python -c 'import json,subprocess; print("SELECTED_MODEL_FREEZE="+json.dumps(subprocess.check_output(["/work/venv/bin/pip","freeze"],text=True).splitlines()))'
'''
    resources = {'cpu': '2' if cpu else '4', 'memory': '6Gi' if cpu else '24Gi',
                 'ephemeral-storage': '8Gi' if cpu else '100Gi'}
    if not cpu:
        resources[args.gpu_resource] = '1'
    spec = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
            'nodeSelector': {'kubernetes.io/arch': 'amd64'},
            'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000,
                                'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': 'test', 'image': image, 'command': ['bash', '-c', shell],
                'resources': {'requests': resources, 'limits': resources.copy()},
                'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                    'capabilities': {'drop': ['ALL']}},
                'volumeMounts': [{'name': 'code', 'mountPath': '/input', 'readOnly': True},
                                {'name': 'work', 'mountPath': '/work'}]}],
            'volumes': [{'name': 'code', 'configMap': {'name': name + '-code'}},
                        {'name': 'work', 'emptyDir': {'sizeLimit': '8Gi' if cpu else '100Gi'}}]}
    if not cpu:
        spec['priorityClassName'] = 'opportunistic'
        spec['affinity'] = {'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {
            'nodeSelectorTerms': [{'matchExpressions': [{'key': 'nvidia.com/gpu.memory',
                'operator': 'Gt', 'values': ['39999']}]}]}}}
    configmap = {'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': name + '-code', 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
        'data': {'test-selected-model.py': (ROOT / 'scripts/test-selected-model.py').read_text(),
                 'selected-model.lock.json': (ROOT / 'configs/selected-model.lock.json').read_text()}}
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
        'metadata': {'name': name, 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
        'spec': {'activeDeadlineSeconds': 1200 if cpu else 1800, 'backoffLimit': 0,
                 'ttlSecondsAfterFinished': 3600, 'template': {'metadata': {'labels': labels}, 'spec': spec}}}
    dest = ROOT / f'configs/selected-model-test-{args.mode}.json'
    dest.write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': [configmap, job]}, indent=2) + '\n')
    print(json.dumps({'manifest': str(dest), 'name': name, 'resources': resources}))


if __name__ == '__main__':
    main()
