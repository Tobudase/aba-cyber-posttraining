#!/usr/bin/env python3
"""Explicit CPU-only model prefetch; never download weights inside an idle GPU job."""
import argparse
import json
import shutil
from pathlib import Path

from benchkit import verify_sources

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['cisco', 'redsage'], required=True)
    p.add_argument('--cache-dir', type=Path, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args(); lock = verify_sources()['models'][a.model]
    if not a.execute:
        print(json.dumps({'status': 'PREFETCH_PLAN_ONLY', 'model': lock['id'], 'revision': lock['revision'],
                          'estimated_bf16_weight_bytes': 17_000_000_000, 'gpu_requested': 0}))
        return
    import os
    # Caller schedules this on CPU; refuse accidental visible-GPU prefetch.
    import torch
    if torch.cuda.is_available(): p.error('Run prefetch in CPU-only job before GPU allocation')
    a.cache_dir.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(a.cache_dir).free < 24_000_000_000: p.error('Require at least24GB free for one pinned8B snapshot')
    from huggingface_hub import snapshot_download
    path = snapshot_download(lock['id'], revision=lock['revision'], cache_dir=str(a.cache_dir),
        allow_patterns=['*.safetensors', '*.json', '*.jinja', '*.md', 'LICENSE*', 'NOTICE*'], max_workers=2)
    print(json.dumps({'status': 'PREFETCH_COMPLETE', 'model': lock['id'], 'revision': lock['revision'], 'path': path, 'gpu_requested': 0}))

if __name__ == '__main__': main()
