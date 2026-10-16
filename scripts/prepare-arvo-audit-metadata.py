#!/usr/bin/env python3
"""Restore only pinned ARVO metadata JSONs and license, not patches or PoCs."""
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/n132/ARVO-Meta.git'


def main():
    coverage = json.loads((ROOT / 'data/manifests/arvo-metadata-coverage.json').read_text())
    dest = ROOT / '.tools/arvo-metadata-audit'
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    base = ['git', '-c', 'credential.helper=', '-c', 'core.hooksPath=/dev/null']

    def git(args, **kwargs):
        return subprocess.run(base + ['-C', str(dest), *args], env=env,
                              capture_output=True, text=True, check=True, timeout=180, **kwargs)

    if dest.exists():
        if git(['rev-parse', 'HEAD']).stdout.strip() != coverage['revision']:
            raise RuntimeError('Existing audit cache has a different revision; inspect before changing it')
        print('Pinned audit cache already present; audit-arvo-fix-groups.py verifies blob hashes.')
        return
    dest.mkdir(parents=True)
    git(['init', '--quiet'])
    git(['remote', 'add', 'origin', URL])
    git(['config', 'remote.origin.promisor', 'true'])
    git(['config', 'remote.origin.partialclonefilter', 'blob:none'])
    git(['fetch', '--depth=1', '--filter=blob:none', 'origin', coverage['revision']])
    patterns = []
    for row in coverage['entries']:
        p = PurePosixPath(row['metadata_path'])
        if p.is_absolute() or '..' in p.parts or len(p.parts) != 3 or p.parts[:2] != ('archive_data', 'meta') or not p.stem.isdigit() or p.suffix != '.json':
            raise RuntimeError('Unexpected metadata path')
        patterns.append('/' + p.as_posix())
    git(['sparse-checkout', 'set', '--no-cone', '--stdin'], input='\n'.join(patterns + ['/LICENSE']) + '\n')
    git(['checkout', '--detach', coverage['revision']])
    print(json.dumps({'revision': coverage['revision'], 'metadata_files': len(patterns),
                      'raw_cache_excluded_from_training_and_handoff': True}))


if __name__ == '__main__':
    main()
