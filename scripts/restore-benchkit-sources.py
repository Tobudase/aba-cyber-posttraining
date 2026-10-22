#!/usr/bin/env python3
"""Restore exact published source receipts; never download tests or weights.

Default is verification only. --execute permits bounded, hash-checked downloads.
Downloaded third-party files remain ignored and retain their original terms.
"""
import argparse
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    ctx = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').is_file() else ssl.create_default_context()
    receipt = json.loads((ROOT / 'docs/verification/benchkit-source-preparation.json').read_text())
    prior = json.loads((ROOT / 'docs/verification/athenabench-2026-10-18/source-manifest.json').read_text())
    tasks = [(f, ROOT / f['path'], ROOT / '.tools/benchkit') for f in receipt['files']]
    source = ROOT / 'docs/verification/athenabench-2026-10-18/source'
    tasks += [(f, source / f['path'], source) for f in prior['files']]
    checked = fetched = 0
    for entry, destination, allowed_root in tasks:
        if not destination.resolve().is_relative_to(allowed_root.resolve()):
            raise ValueError('Manifest path escapes restoration directory')
        url = entry['url']
        if not url.startswith('https://') or 'test_5000' in url or destination.suffix == '.safetensors':
            raise ValueError('Restoration allowlist violated')
        raw = destination.read_bytes() if destination.is_file() else None
        if raw is None:
            if not args.execute:
                raise FileNotFoundError('Missing pinned source; review notices then use --execute: ' + entry['path'])
            with urllib.request.urlopen(url, context=ctx, timeout=45) as response:
                raw = response.read(32_000_001)
            fetched += 1
        if len(raw) > 32_000_000 or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Pinned content mismatch; refusing replacement: ' + entry['path'])
        if not destination.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        checked += 1
    print(json.dumps({'verified_files': checked, 'downloaded_files': fetched,
                      'official_test_files': 0, 'model_weight_tensors': 0}))


if __name__ == '__main__':
    main()
