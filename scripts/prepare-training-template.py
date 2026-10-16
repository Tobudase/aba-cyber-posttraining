#!/usr/bin/env python3
"""Restore the two locked Qwen3 templates and TRL license from a verified wheel."""
import hashlib
import io
import json
from pathlib import Path
import ssl
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'configs/training-template.lock.json'
    lock = json.loads(path.read_text())
    context = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').is_file() else ssl.create_default_context()
    with urllib.request.urlopen(lock['wheel_url'], timeout=30, context=context) as response:
        raw = response.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != lock['wheel_sha256']:
        raise RuntimeError('TRL wheel size/checksum mismatch')
    dest = ROOT / 'configs/templates'
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name, info in lock['templates'].items():
            if name not in {'qwen3.jinja', 'qwen3_training.jinja'}:
                raise RuntimeError('Unexpected template in allowlist')
            data = archive.read(info['wheel_path'])
            if hashlib.sha256(data).hexdigest() != info['sha256']:
                raise RuntimeError('Template checksum mismatch')
            (dest / name).write_bytes(data)
        licenses = [n for n in archive.namelist() if '.dist-info/' in n and n.rsplit('/', 1)[-1].upper() in {'LICENSE', 'LICENSE.TXT'}]
        if len(licenses) != 1:
            raise RuntimeError('Expected one upstream license')
        data = archive.read(licenses[0])
        (dest / 'TRL-LICENSE.txt').write_bytes(data)
        lock['license_file'] = {'local_path': 'configs/templates/TRL-LICENSE.txt',
                                'wheel_path': licenses[0], 'sha256': hashlib.sha256(data).hexdigest()}
    path.write_text(json.dumps(lock, indent=2) + '\n')
    print(json.dumps({'restored_templates': sorted(lock['templates']), 'license_saved': True,
                      'package_installed': False}, indent=2))


if __name__ == '__main__':
    main()
