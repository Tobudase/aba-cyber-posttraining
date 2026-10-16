#!/usr/bin/env python3
"""Create a short official opportunistic-tier single-A100 diagnostic Job."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
name = 'user-cuda-probe'
image = json.loads((ROOT / 'configs/gpu-runtime-image.lock.json').read_text())['image']
labels = {'app.kubernetes.io/name': name, 'app.kubernetes.io/managed-by': 'cybergym-posttrain'}
resources = {'cpu': '1', 'memory': '2Gi', 'ephemeral-storage': '2Gi', 'nvidia.com/a100': '1'}
configmap = {'apiVersion': 'v1', 'kind': 'ConfigMap',
    'metadata': {'name': name + '-code', 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
    'data': {'probe-cuda.py': (ROOT / 'scripts/probe-cuda.py').read_text()}}
job = {'apiVersion': 'batch/v1', 'kind': 'Job',
    'metadata': {'name': name, 'namespace': 'YOUR_NAMESPACE', 'labels': labels,
                 'annotations': {'policy-source': 'https://nrp.ai/documentation/userdocs/running/priority-classes/'}},
    'spec': {'activeDeadlineSeconds': 600, 'backoffLimit': 0, 'ttlSecondsAfterFinished': 3600,
        'template': {'metadata': {'labels': labels}, 'spec': {
            'priorityClassName': 'opportunistic', 'restartPolicy': 'Never',
            'automountServiceAccountToken': False,
            'nodeSelector': {'kubernetes.io/arch': 'amd64'},
            'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000,
                                'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': 'probe', 'image': image,
                'command': ['python', '-u', '/input/probe-cuda.py'],
                'env': [{'name': 'CUDA_CACHE_PATH', 'value': '/work/cuda-cache'},
                        {'name': 'PYTHONDONTWRITEBYTECODE', 'value': '1'}],
                'resources': {'requests': resources, 'limits': resources.copy()},
                'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                    'capabilities': {'drop': ['ALL']}},
                'volumeMounts': [{'name': 'code', 'mountPath': '/input', 'readOnly': True},
                                 {'name': 'work', 'mountPath': '/work'}]}],
            'volumes': [{'name': 'code', 'configMap': {'name': name + '-code'}},
                        {'name': 'work', 'emptyDir': {'sizeLimit': '2Gi'}}]}}}}
path = ROOT / 'configs/cuda-probe-job.json'
path.write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': [configmap, job]}, indent=2) + '\n')
print(json.dumps({'manifest': str(path), 'gpus': 1, 'priority_class': 'opportunistic', 'deadline_seconds': 600}))
