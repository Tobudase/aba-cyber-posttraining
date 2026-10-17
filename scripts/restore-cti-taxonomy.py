#!/usr/bin/env python3
"""Restore the pinned MITRE CWE taxonomy used for held-data review."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'configs/cti-taxonomy.lock.json').read_text())
target=ROOT/'.tools/cti-review/cwec_latest.xml.zip'
target.parent.mkdir(parents=True,exist_ok=True)
if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=lock['zip_sha256']:
    temporary=target.with_suffix('.download')
    subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time','60',
                    '--max-filesize','4000000','--output',str(temporary),lock['url']],check=True)
    assert hashlib.sha256(temporary.read_bytes()).hexdigest()==lock['zip_sha256']
    temporary.replace(target)
with zipfile.ZipFile(target) as z:
    member=next(n for n in z.namelist() if n.endswith('.xml'))
    assert hashlib.sha256(z.read(member)).hexdigest()==lock['xml_sha256']
print(json.dumps({'status':'PASSED','version':lock['version'],'terms_url':lock['terms_url']}))
