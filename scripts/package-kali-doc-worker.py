#!/usr/bin/env python3
"""Prepare a training-only Linux candidate package; never submit a GPU job."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from benchkit import ROOT, load_manifest, sha, verify_sources, write_json


def main():
    source = verify_sources(); spec, rows = load_manifest(ROOT / 'data/benchkit/kali-doc-train-v1/manifest.json', 'train')
    out = ROOT / 'artifacts/kali-doc-worker-v1'
    if out.exists(): raise FileExistsError('Preserve the prior package; version explicitly instead of overwrite')
    out.mkdir(parents=True)
    projected = copy.deepcopy(source)
    projected['files'] = [f for f in source['files'] if f['path'].startswith('.tools/benchkit/models/redsage/')]
    projected['models'] = {'redsage': source['models']['redsage']}
    projected['scope'] = 'Training worker: model metadata only, no external dev, docs corpus, test or credentials'
    paths = ['scripts/benchkit.py', 'scripts/train-benchkit.py', 'scripts/cache-benchkit-model.py',
             'configs/requirements-benchkit-gpu.candidate.txt', 'configs/gpu-runtime-image.lock.json',
             'docs/verification/athenabench-2026-10-18/source-manifest.json']
    paths += [f['path'] for f in projected['files']]
    old = json.loads((ROOT / 'docs/verification/athenabench-2026-10-18/source-manifest.json').read_text())
    paths += ['docs/verification/athenabench-2026-10-18/source/' + f['path'] for f in old['files']]
    for rel in paths:
        src = ROOT / rel; dest = out / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest)
    write_json(out / 'docs/verification/benchkit-source-preparation.json', projected)
    data = out / 'data/benchkit/train'; data.mkdir(parents=True)
    for name in ['train.jsonl', 'manifest.json']:
        shutil.copy2(ROOT / 'data/benchkit/kali-doc-train-v1' / name, data / name)
    contract = {'schema': 'kali.doc_worker.v1', 'status': 'PACKAGED_SELF_CHECKED_NOT_LINUX_GPU_OR_ABA_EXECUTED',
        'model': projected['models']['redsage'], 'training_rows': len(rows),
        'training_manifest_sha256': sha((data / 'manifest.json').read_bytes()),
        'worker_command': ['python', 'scripts/train-benchkit.py', '--model', 'redsage',
            '--dataset', 'data/benchkit/train/manifest.json', '--steps', '108', '--learning-rate', '0.00001',
            '--output', '/results/candidate-01', '--execute'],
        'model_prefetch_command': ['python', 'scripts/cache-benchkit-model.py', '--model', 'redsage',
            '--cache-dir', '/results/hf-cache', '--execute'],
        'private_evaluator': {'status': 'INTERFACE_CONTRACT_ONLY_NOT_INTEGRATED_WITH_ACTUAL_ABA',
            'input': {'candidate_id': 'string', 'adapter_directory': 'shared-result-path', 'training_receipt_sha256': 'sha256'},
            'output': ['candidate_id', 'status', 'domain_native_metrics', 'domain_option_diagnostic',
                       'retention_native_metrics', 'retention_option_diagnostic', 'coverage', 'gpu_hours', 'errors'],
            'official_test_feedback': False, 'dev_rows_returned_to_worker': False},
        'private_dev_files': 0, 'confirmation_files': 0, 'official_test_files': 0, 'credentials': 0,
        'search_enabled': False, 'gpu_jobs_submitted': 0,
        'runtime_difference': 'Existing CUDA runner uses NF4,PEFT rank16/all q-v layers; Mac frozen pilot uses MLX affine4,rank8/last4layers. Fresh matched GPU baseline/protocol required; do not claim cross-runtime reproduction.',
        'prerequisites': ['Namespace pod admission restored; do not bypass quotas',
            'CPU-only prefetch before GPU scheduling', 'Build and validate immutable Linux training image and CUDA stack',
            'Single finite GPU smoke, telemetry, private evaluator mounting and controlled submission',
            'Actual pinned ABA setup/worker/evaluator end-to-end validation before enabling search']}
    write_json(out / 'task-contract.json', contract)
    base = json.loads((ROOT / 'configs/gpu-runtime-image.lock.json').read_text())['image']
    (out / 'Dockerfile').write_text(f'''# Candidate only: not built or CUDA-validated.
FROM {base}
WORKDIR /opt/benchkit
COPY configs/requirements-benchkit-gpu.candidate.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt && python -m pip check
COPY . /opt/benchkit
CMD ["python", "scripts/train-benchkit.py", "--help"]
''')
    (out / '.dockerignore').write_text('**/__pycache__\n**/*.pyc\noutputs\n.secrets\n')
    hashes = {str(p.relative_to(out)): sha(p.read_bytes()) for p in out.rglob('*') if p.is_file()}
    if any(any(part in {'.secrets', '.git', '.kube'} for part in Path(n).parts) or
           n.endswith(('.safetensors', '.pt')) or '/dev' in n or '/test' in n for n in hashes):
        raise ValueError('Forbidden worker file')
    # Additional literal ID audit proves no authored development records leaked.
    forbidden_ids = ['kali-docdev-v1-', 'authored-doc-v1-']
    for path in out.rglob('*'):
        if path.is_file() and any(marker.encode() in path.read_bytes() for marker in forbidden_ids):
            raise ValueError('Development row identifier present in worker')
    check = subprocess.run([sys.executable, '-c',
        "import sys;sys.path.insert(0,'scripts');import benchkit;benchkit.verify_sources();s,p=benchkit.load_manifest('data/benchkit/train/manifest.json');assert set(p)=={'train'};assert len(p['train'])==108"],
        cwd=out, capture_output=True, text=True, timeout=30)
    if check.returncode: raise ValueError('Packaged tree selfcheck failed: ' + check.stderr[-800:])
    write_json(out / 'bundle-manifest.json', {'files': hashes, 'training_only_selfcheck': 'PASSED',
        'forbidden_authored_dev_ids_found': 0, 'dev_files': 0, 'official_test_files': 0, 'credentials': 0})
    archive = out.with_suffix('.tar.gz')
    with tarfile.open(archive, 'w:gz') as tar:
        for p in sorted(out.rglob('*')):
            if p.is_file(): tar.add(p, arcname=str(p.relative_to(out)), recursive=False)
    write_json(ROOT / 'configs/benchkit/kali-doc-worker-contract.v1.json', contract)
    report = {'status': contract['status'], 'rows': len(rows), 'files': len(hashes),
        'training_only_selfcheck': 'PASSED', 'archive': str(archive.relative_to(ROOT)),
        'bytes': archive.stat().st_size, 'sha256': sha(archive.read_bytes()), 'dev_files': 0,
        'official_test_files': 0, 'credentials': 0, 'model_weights': 0, 'gpu_jobs_created': 0,
        'actual_ABA_executed': False, 'runtime_difference': contract['runtime_difference']}
    write_json(ROOT / 'docs/verification/kali-doc-worker-package.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
