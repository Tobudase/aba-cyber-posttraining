#!/usr/bin/env python3
"""Fetch hash-pinned official RedSage weights, then locally quantize for MLX.

No test data, cloud GPUs or remote model code. Each stage is explicit.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import time

from benchkit import ROOT, sha, verify_sources, write_json


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['download', 'convert'], required=True)
    p.add_argument('--execute', action='store_true')
    args = p.parse_args()
    lock = verify_sources()['models']['redsage']
    metadata = json.loads((ROOT / 'docs/verification/kali-model-access-2026-10-22/RISys-Lab.json').read_text())
    if metadata['id'] != lock['id'] or metadata['sha'] != lock['revision'] or metadata.get('gated') or metadata.get('private'):
        raise ValueError('Public pinned metadata mismatch')
    weights = [f for f in metadata['siblings'] if f['rfilename'].endswith('.safetensors')]
    expected_bytes = sum(f['size'] for f in weights)
    if expected_bytes > 18_000_000_000: raise ValueError('8B weight budget exceeded')
    base = ROOT / '.tools/kali-models'
    base.mkdir(exist_ok=True)
    if not args.execute:
        print(json.dumps({'stage': args.stage, 'official_model': lock['id'], 'revision': lock['revision'],
            'weight_bytes': expected_bytes, 'planned_local_quantization': 'MLX affine4 group64', 'executed': False}))
        return
    before = time.monotonic()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Bounded preparation deadline')))
    signal.alarm(2400 if args.stage == 'download' else 600)
    if args.stage == 'download':
        if shutil.disk_usage(base).free < 32_000_000_000: raise ValueError('Require32GB free before download')
        os.environ['SSL_CERT_FILE'] = '/etc/ssl/cert.pem'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['HF_HUB_DISABLE_XET'] = '1'
        from huggingface_hub import snapshot_download
        directory = Path(snapshot_download(lock['id'], revision=lock['revision'], cache_dir=base / 'hf-cache',
            allow_patterns=['*.safetensors', '*.json', '*.jinja', 'README.md', 'LICENSE*', 'NOTICE*'],
            max_workers=2, token=False))
        checks = {}
        for f in weights:
            path = directory / f['rfilename']
            actual = digest(path)
            if path.stat().st_size != f['size'] or actual != f['lfs']['sha256']:
                raise ValueError('Official weight size/hash mismatch')
            checks[f['rfilename']] = actual
        for entry in verify_sources()['files']:
            if entry['path'].startswith('.tools/benchkit/models/redsage/'):
                path = directory / Path(entry['path']).name
                if sha(path.read_bytes()) != entry['sha256']:
                    raise ValueError('Model/tokenizer metadata differs from previous pin')
        report = {'status': 'OFFICIAL_PINNED_WEIGHTS_HASH_VERIFIED', 'model_id': lock['id'],
            'revision': lock['revision'], 'directory': str(directory), 'weight_sha256': checks,
            'weight_bytes': expected_bytes, 'gpu_requested': 0, 'official_test_rows': 0,
            'usage': 'Local research; no redistribution rights inferred from public access.'}
    else:
        prior = json.loads((ROOT / 'docs/verification/kali-mlx-download.json').read_text())
        if prior['revision'] != lock['revision']: raise ValueError('Download receipt revision mismatch')
        directory = Path(prior['directory'])
        for name, checksum in prior['weight_sha256'].items():
            if digest(directory / name) != checksum: raise ValueError('Source weights changed')
        import mlx.core as mx
        from mlx_lm.convert import convert
        # Conversion is lazy and CPU streamed; avoid loading BF168B on Metal.
        mx.set_default_device(mx.cpu)
        mx.set_memory_limit(9 * 1024**3)
        mx.set_cache_limit(256 * 1024**2)
        destination = base / ('redsage-' + lock['revision'][:12] + '-mlx-affine4-g64')
        convert(str(directory), str(destination), quantize=True, q_bits=4,
                q_group_size=64, q_mode='affine', trust_remote_code=False)
        config = json.loads((destination / 'config.json').read_text())
        if config['quantization']['bits'] != 4: raise ValueError('Wrong converted precision')
        report = {'status': 'OFFICIAL_WEIGHTS_LOCALLY_QUANTIZED', 'model_id': lock['id'],
            'revision': lock['revision'], 'directory': str(destination),
            'source_weight_sha256': prior['weight_sha256'], 'quantization': 'MLX affine4 group64',
            'files': {x.name: digest(x) for x in destination.iterdir() if x.is_file()},
            'conversion_device': 'CPU', 'mlx': importlib.metadata.version('mlx'),
            'mlx_lm': importlib.metadata.version('mlx-lm'), 'official_test_rows': 0,
            'not_BF16_leaderboard_reproduction': True}
    report.update(checked_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic() - before)
    write_json(ROOT / f'docs/verification/kali-mlx-{args.stage}.json', report)
    signal.alarm(0)
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
