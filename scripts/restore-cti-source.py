#!/usr/bin/env python3
"""Restore the explicitly reviewed, hash-pinned metadata/code allowlist."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
records = json.loads((ROOT/'configs/cti-reviewed-files.lock.json').read_text())


def restore(item):
    name, info = item
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    assert urlparse(info['url']).hostname in {'raw.githubusercontent.com', 'huggingface.co'}
    target = ROOT/'.tools/cti-review'/relative
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == info['sha256']:
        return 'reused'
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = subprocess.check_output(['curl','--fail','--silent','--show-error','--location',
                                   '--max-time','45',info['url']])
    assert len(raw) == info['bytes'] and hashlib.sha256(raw).hexdigest() == info['sha256'], name
    target.write_bytes(raw)
    return 'restored'


with ThreadPoolExecutor(4) as pool:
    results = list(pool.map(restore, records.items()))
print(json.dumps({'status':'PASSED','files':len(results),'restored':results.count('restored'),
                  'official_test_rows':0}))
