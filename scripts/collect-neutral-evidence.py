#!/usr/bin/env python3
"""Retrieve only the fixed neutral run evidence; never read remote credentials."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    local = json.loads(args.report.read_text())
    run_id = local.get('run_id', '')
    if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{8}', run_id):
        parser.error('Invalid neutral run ID')
    source = '''import base64, hashlib, json, pathlib, sqlite3, subprocess
run_id = RUN_ID_LITERAL
root = pathlib.Path.home() / 'cybergym-project/agent-neutral-runs' / run_id
files = {}
for name in ['report.json','server.log','neutral-submit-result.json','neutral-input.bin']:
    p = root / name
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 2*1024*1024:
        raise RuntimeError('Missing or oversized expected evidence file')
    files[name] = base64.b64encode(p.read_bytes()).decode()
container_ids = subprocess.check_output(['docker','ps','-aq'],timeout=15).decode().split()
owned = []
for cid in container_ids:
    info = json.loads(subprocess.check_output(['docker','inspect',cid],timeout=15))[0]
    if any(str(m.get('Source','')).startswith(str(root)+'/') for m in info.get('Mounts',[])):
        owned.append({'id':cid,'state':info.get('State',{}).get('Status')})
processes = subprocess.check_output(['ps','-eo','pid,args'],timeout=10).decode().splitlines()
active_servers = sum('-m cybergym.server' in p and str(root) in p for p in processes)
report = json.loads((root/'report.json').read_text())
db = sqlite3.connect((root/'server/poc.db').as_uri()+'?mode=ro',uri=True)
db.row_factory = sqlite3.Row
rows = [dict(r) for r in db.execute('SELECT agent_id,task_id,poc_id,poc_hash,poc_length,vul_exit_code,fix_exit_code FROM poc_records WHERE agent_id=? AND poc_hash=?', (report['agent_id'],hashlib.sha256(bytes((0,1,2,3))).hexdigest()))]
db.close()
print(json.dumps({'files':files,'raw_database_records':rows,'cleanup':{'owned_containers':owned,'active_run_servers':active_servers}}))
'''.replace('RUN_ID_LITERAL', repr(run_id))
    response = subprocess.run([str(ROOT/'scripts/vm-ssh.sh'),'--command','python3 -'],
                              input=source.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=60, check=True)
    result = json.loads(response.stdout)
    dest = ROOT / 'docs/verification' / ('neutral-run-' + run_id)
    dest.mkdir(exist_ok=True)
    hashes = {}
    expected = {'report.json','server.log','neutral-submit-result.json','neutral-input.bin'}
    if set(result['files']) != expected:
        raise RuntimeError('Evidence file allowlist mismatch')
    for name, value in result['files'].items():
        data = base64.b64decode(value, validate=True)
        if len(data) > 2*1024*1024:
            raise RuntimeError('Oversized returned evidence')
        (dest/name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    report = json.loads((dest/'report.json').read_text())
    if report['run_id'] != run_id or (dest/'neutral-input.bin').read_bytes() != bytes((0,1,2,3)):
        raise RuntimeError('Remote run or fixed input mismatch')
    summary = {'run_id':run_id,'files_sha256':hashes,'cleanup':result['cleanup'],
               'fixed_input_verified':True,'raw_database_records':result['raw_database_records'],
               'benchmark_evaluated':False,'training_eligible':False}
    (dest/'evidence-manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'directory':str(dest),'files_copied':len(hashes),'cleanup':result['cleanup'],
                      'fixed_input_verified':True},indent=2))


if __name__ == '__main__':
    main()
