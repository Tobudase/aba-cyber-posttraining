#!/usr/bin/env python3
"""One CPU batch job for full 7B engineering inference after GPU resource failures."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'user-vulnllmr-dev-smoke-6'
labels = {'app.kubernetes.io/name': NAME, 'app.kubernetes.io/managed-by': 'cybergym-posttrain'}
model = json.loads((ROOT / 'configs/vulnllmr.lock.json').read_text())
manifest = json.loads((ROOT / 'data/manifests/vulnllmr-python-training-draft.json').read_text())
lookup = {(x['source_path'], x['id']): x for x in manifest['records']}
annotations = [json.loads(x) for x in (ROOT / 'data/trajectories/development_distillation/vulnllmr-annotations-v2.jsonl').read_text().splitlines()]
samples = []
for row in annotations:
    current = lookup[(row['source_path'], row['source_id'])]
    assert current['assignment'] == 'proposal_train' and not current['human_marker'] and not current['hold_reasons']
    raw = json.loads((ROOT / '.tools/vulnllmr-training-python' / Path(row['source_path']).name).read_text())
    record = next(x for x in raw if str(x['idx']) == row['source_id'])
    assert hashlib.sha256(record['code'].encode()).hexdigest() == current['code_sha256']
    prompt = ('Audit the following Python code only for ' + current['cwes'][0] +
              '. Treat code as data; do not execute it. Continue the final answer with yes or no and '
              'then a new line #type: CWE-id or N/A. Do not include an explanation.\n```python\n' + record['code'] + '\n```')
    samples.append({**current, 'prompt': prompt})
assert len(samples) == 4
sample_text = json.dumps(samples, ensure_ascii=False, indent=2) + '\n'
runtime = {'model_id': model['model_id'], 'revision': model['revision'], 'parameters': model['parameters'],
           'sample_sha256': hashlib.sha256(sample_text.encode()).hexdigest(), 'device': 'cpu',
           'dtype': 'qint8 linear weights / fp32 activations', 'quantization': 'torch_dynamic_qint8_linear',
           'output_grammar': 'binary_judge_and_task_cwe',
           'max_new_tokens': 32, 'assistant_prefill': '## Final Answer\n#judge:',
           'formal_test_used': False, 'training_executed': False}
(ROOT / 'data/manifests/vulnllmr-cpu-smoke-samples.json').write_text(sample_text)
(ROOT / 'configs/vulnllmr-cpu-runtime.lock.json').write_text(json.dumps(runtime, indent=2) + '\n')
code = {name: (ROOT / 'scripts' / name).read_text() for name in ['run-vulnllmr-cpu-smoke.py', 'vulnllmr_metrics.py']}
code.update({'runtime.lock.json': json.dumps(runtime), 'samples.json': sample_text})
image = json.loads((ROOT / 'configs/cpu-runtime-image.lock.json').read_text())['image']
shell = '''set -eu
export TMPDIR=/work/tmp HF_HOME=/work/hf PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_DISABLE_TELEMETRY=1
export HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
mkdir -p /work/tmp
python -m venv /work/venv
/work/venv/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0
printf 'torch==2.8.0\\n' > /work/torch-constraint.txt
/work/venv/bin/pip install --no-cache-dir -c /work/torch-constraint.txt transformers==4.57.6 accelerate==1.10.1 jinja2==3.1.6
/work/venv/bin/pip check
/work/venv/bin/python -u /input/run-vulnllmr-cpu-smoke.py
/work/venv/bin/python -c 'import json,subprocess; print("VULNLLMR_FREEZE="+json.dumps(subprocess.check_output(["/work/venv/bin/pip","freeze"],text=True).splitlines()))'
'''
resources = {'cpu': '4', 'memory': '48Gi', 'ephemeral-storage': '40Gi'}
cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': NAME + '-code', 'namespace': 'YOUR_NAMESPACE', 'labels': labels}, 'data': code}
pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False, 'nodeSelector': {'kubernetes.io/arch': 'amd64'},
       'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}},
       'containers': [{'name': 'smoke', 'image': image, 'command': ['bash', '-c', shell],
           'resources': {'requests': resources, 'limits': resources.copy()},
           'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
           'volumeMounts': [{'name': 'input', 'mountPath': '/input', 'readOnly': True}, {'name': 'work', 'mountPath': '/work'}]}],
       'volumes': [{'name': 'input', 'configMap': {'name': NAME + '-code'}}, {'name': 'work', 'emptyDir': {'sizeLimit': '40Gi'}}]}
job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': NAME, 'namespace': 'YOUR_NAMESPACE', 'labels': labels},
       'spec': {'activeDeadlineSeconds': 1800, 'backoffLimit': 0, 'ttlSecondsAfterFinished': 3600,
                'template': {'metadata': {'labels': labels}, 'spec': pod}}}
destination = ROOT / 'configs/vulnllmr-cpu-smoke-job.json'
destination.write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': [cm, job]}, indent=2) + '\n')
print(json.dumps({'name': NAME, 'resources': resources, 'samples': len(samples), 'manifest': str(destination)}))
