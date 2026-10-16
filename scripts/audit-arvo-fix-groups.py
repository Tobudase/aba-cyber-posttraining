#!/usr/bin/env python3
"""Extract only repository/fix identifiers for split auditing, never solutions."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def canonical(url):
    parsed = urlsplit(url)
    path = parsed.path.rstrip('/').removesuffix('.git')
    host = (parsed.hostname or '').lower()
    if host == 'github.com':
        path = path.lower()
    return host + path if host and path else ''


def main():
    source = ROOT / '.tools/arvo-metadata-audit'
    coverage = json.loads((ROOT / 'data/manifests/arvo-metadata-coverage.json').read_text())
    head = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != coverage['revision']:
        raise RuntimeError('ARVO metadata revision mismatch')
    membership = {}
    for split in ['train', 'dev', 'test', 'infra_only']:
        for row in json.loads((ROOT / f'data/manifests/splits-draft/{split}.json').read_text()):
            membership[row['task_id']] = row
    records, excluded, aliases = [], [], []
    groups = defaultdict(list)
    upstream_groups = defaultdict(list)
    for item in coverage['entries']:
        raw = (source / item['metadata_path']).read_bytes()
        blob_sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\x00' + raw).hexdigest()
        if blob_sha != item['git_blob_sha']:
            raise RuntimeError('Public metadata blob checksum mismatch')
        obj = json.loads(raw)
        task_id = item['task_id']
        if str(obj.get('localId')) != task_id.split(':', 1)[1]:
            excluded.append({'task_id': task_id, 'reason': 'metadata identity mismatch'})
            continue
        value = obj.get('fix_commit', '')
        match = re.fullmatch(r'(?:https?://[^\s]+/(?:commit|commits)/)?([0-9a-fA-F]{40})', value.strip()) if isinstance(value, str) else None
        repo_value = obj.get('repo_addr', '')
        repo = canonical(repo_value) if isinstance(repo_value, str) else ''
        if not match or not repo:
            excluded.append({'task_id': task_id, 'reason': 'missing/unrecognized repository or full fix commit'})
            continue
        # Keep only an irreversible grouping key, not a test patch address.
        key = hashlib.sha256((repo + '\0' + match.group(1).lower()).encode()).hexdigest()
        row = membership[task_id]
        record = {'task_id': task_id, 'split': row['split'], 'project_name': row['project_name'],
                  'fix_group_sha256': key, 'metadata_blob_sha1': blob_sha}
        records.append(record)
        groups[key].append(record)
        upstream_groups[repo].append(record)
        if repo != row['repository_group']:
            aliases.append({'task_id': task_id, 'project_name': row['project_name'],
                            'index_repository': row['repository_group'], 'metadata_repository': repo})
    cross = [{'fix_group_sha256': key, 'task_ids': sorted(r['task_id'] for r in rows),
              'splits': sorted({r['split'] for r in rows}), 'projects': sorted({r['project_name'] for r in rows})}
             for key, rows in sorted(groups.items()) if len({r['split'] for r in rows}) > 1]
    matches = sum(len(rows) > 1 for rows in groups.values())
    cross_upstream = [{'repository': repo, 'projects': sorted({r['project_name'] for r in rows}),
                       'splits': sorted({r['split'] for r in rows})}
                      for repo, rows in sorted(upstream_groups.items()) if len({r['split'] for r in rows}) > 1]
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'status': 'CROSS_SPLIT_REVIEW_REQUIRED' if cross or cross_upstream else 'NO_CROSS_SPLIT_FIX_GROUP_MATCHES_IN_COVERED_RECORDS',
              'source': coverage['source'], 'source_revision': head,
              'metadata_files_verified': len(coverage['entries']), 'mapped_tasks': len(records),
              'excluded_records': excluded, 'unique_fix_groups': len(groups),
              'groups_with_multiple_tasks': matches, 'cross_split_fix_groups': cross,
              'cross_split_metadata_repositories': cross_upstream,
              'repository_alias_records': len(aliases), 'repository_aliases': aliases,
              'uncovered_task_source': '139 oss-fuzz tasks have not been checked through this ARVO archive',
              'limitations': ['One fix commit may address several distinct bugs; matches are review candidates, not automatic duplicates.',
                             'Archive metadata is not proof of final patch correctness or reproducibility.',
                             'repo_addr may refer to a dependency rather than the task main repository; alias differences require review.',
                             'Fork ancestry, shared dependencies and renamed mirrors remain unassessed.',
                             'No patches, reference inputs or report contents exported; derived grouping metadata must not enter SFT.'],
              'split_frozen': False, 'leakage_absence_certified': False}
    (ROOT / 'data/manifests/arvo-fix-groups.json').write_text(json.dumps({
        'purpose': 'ADMINISTRATIVE_DEDUP_ONLY_NOT_TRAINING_DATA', 'source_revision': head,
        'records': records}, indent=2) + '\n')
    dest = ROOT / 'docs/verification/arvo-fix-group-audit.json'
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'metadata_files_verified', 'mapped_tasks',
          'unique_fix_groups', 'groups_with_multiple_tasks', 'repository_alias_records']}, indent=2))
    print('Cross-split fix groups:', len(cross), 'cross-split upstream repos:', len(cross_upstream), 'excluded:', len(excluded))


if __name__ == '__main__':
    main()
