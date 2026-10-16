#!/usr/bin/env python3
"""Copy only explicitly allowed, non-credential CyberGym verification logs."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
names = ['requirements-resolved.txt', 'task-help.txt', 'server-help.txt',
         'smoke-report.json', 'neutral-submit-result.json', 'neutral-fix-result.json',
         'neutral-verification-result.json', 'server-smoke.log', 'pull-vul.log', 'pull-fix.log']
remote = '''import json
from pathlib import Path
root = Path.home() / 'cybergym-project/logs'
names = NAMES_PLACEHOLDER
result = {}
for name in names:
    path = root / name
    if path.is_file():
        if path.stat().st_size > 10 * 1024**2:
            raise RuntimeError('Log exceeds copy limit')
        result[name] = path.read_text()
print(json.dumps(result))
'''.replace('NAMES_PLACEHOLDER', repr(names))
result = subprocess.run([str(ROOT / 'scripts/vm-ssh.sh'), '--command', 'python3 -'],
                        input=remote, text=True, capture_output=True, check=True, timeout=90)
logs = json.loads(result.stdout)
dest = ROOT / 'docs/verification'
dest.mkdir(parents=True, exist_ok=True)
for name in names:
    if name in logs:
        (dest / name).write_text(logs[name])
print('Copied allowed logs: ' + ', '.join(sorted(logs)))
