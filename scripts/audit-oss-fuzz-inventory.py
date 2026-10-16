#!/usr/bin/env python3
"""Audit pinned official file metadata only; do not download task materials."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').exists() else ssl.create_default_context()


def main():
    lock = json.loads((ROOT / 'configs/sources.lock.json').read_text())
    revision = lock['dataset_revision']
    tasks = json.loads((ROOT / 'data/manifests/tasks.json').read_text())
    splits = {x['task_id']: split for split in ['train', 'dev', 'test', 'infra_only']
              for x in json.loads((ROOT / f'data/manifests/splits-draft/{split}.json').read_text())}
    cache = ROOT / '.tools/oss-fuzz-inventory' / revision
    cache.mkdir(parents=True, exist_ok=True)

    def read(task):
        task_id = task['task_id']
        tid = task_id.split(':')[1]
        path = cache / (tid + '.json')
        if path.is_file():
            listing = json.loads(path.read_text())
        else:
            url = f'https://huggingface.co/api/datasets/sunblaze-ucb/cybergym/tree/{revision}/data/oss-fuzz/{tid}?limit=100'
            with urllib.request.urlopen(url, timeout=25, context=CONTEXT) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024 or response.headers.get('Link'):
                    raise RuntimeError('Unexpected pagination/size for task inventory')
            listing = json.loads(raw)
            path.write_text(json.dumps(listing))
        files = []
        for item in listing:
            if not item['path'].startswith(f'data/oss-fuzz/{tid}/'):
                raise RuntimeError('Unexpected inventory path')
            if item['type'] == 'file':
                files.append({'name': Path(item['path']).name, 'bytes': item['size'],
                              'git_blob_oid': item.get('oid'), 'lfs_sha256': item.get('lfs', {}).get('oid')})
        return {'task_id': task_id, 'project': task['project_name'], 'split': splits[task_id],
                'files': sorted(files, key=lambda x: x['name'])}

    selected = [t for t in tasks if t['task_id'].startswith('oss-fuzz:')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(read, selected))
    required = {'description.txt', 'repo-vul.tar.gz', 'repo-fix.tar.gz', 'patch.diff'}
    missing = [{'task_id': row['task_id'], 'missing': sorted(required - {f['name'] for f in row['files']})}
               for row in records if required - {f['name'] for f in row['files']}]
    groups = defaultdict(list)
    for row in records:
        for f in row['files']:
            identity = f['lfs_sha256'] or f['git_blob_oid']
            if f['bytes'] and identity:
                groups[(f['name'], identity)].append(row)
    matches = [{'artifact_name': name, 'object_id': oid,
                'task_ids': sorted(r['task_id'] for r in rows),
                'projects': sorted({r['project'] for r in rows}),
                'splits': sorted({r['split'] for r in rows})}
               for (name, oid), rows in sorted(groups.items()) if len(rows) > 1]
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'source_revision': revision,
              'status': 'INVENTORY_COMPLETE' if not missing else 'INVENTORY_MISSING_REQUIRED_FILES',
              'tasks_checked': len(records), 'missing_required_files': missing,
              'duplicate_artifact_groups': matches,
              'cross_split_duplicate_artifact_groups': [x for x in matches if len(x['splits']) > 1],
              'task_file_contents_downloaded': False, 'fix_commits_verified': False,
              'leakage_absence_certified': False, 'split_frozen': False,
              'limitations': ['File identity from official Git/LFS metadata detects byte-identical artifacts only.',
                             'Different snapshots or patches can represent the same vulnerability; no semantic identity proof.',
                             'Repeated vulnerable source archives do not by themselves prove repeated bugs.',
                             'Metadata-only audit did not inspect patch contents, reference inputs, crash reports or source archives.']}
    data = {'purpose': 'ADMINISTRATIVE_INVENTORY_ONLY_NOT_TRAINING_DATA',
            'dataset_revision': revision, 'records': records}
    path = ROOT / 'data/manifests/oss-fuzz-file-inventory.json'
    path.write_text(json.dumps(data, indent=2) + '\n')
    report['inventory_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT / 'docs/verification/oss-fuzz-inventory-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'tasks_checked', 'missing_required_files',
          'duplicate_artifact_groups', 'cross_split_duplicate_artifact_groups']}, indent=2))


if __name__ == '__main__':
    main()
