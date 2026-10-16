#!/usr/bin/env python3
"""Audit public task metadata and draft split manifests without task execution."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ('train', 'dev', 'test', 'infra_only')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    path = parsed.path.rstrip('/').removesuffix('.git')
    if host == 'github.com':
        path = path.lower()
    return host + path


def audit(root):
    source = root / 'data/manifests/tasks.json'
    folder = root / 'data/manifests/splits-draft'
    manifest = json.loads((folder / 'manifest.json').read_text())
    source_lock = json.loads((root / 'configs/sources.lock.json').read_text())
    tasks = json.loads(source.read_text())
    errors = []
    by_id = {t['task_id']: t for t in tasks}
    if len(by_id) != len(tasks):
        errors.append('Duplicate task IDs in source')
    if digest(source) != source_lock['task_index']['sha256'] or digest(source) != manifest['source_sha256']:
        errors.append('Source SHA256 mismatch')
    membership = defaultdict(list)
    stats = {}
    for split in SPLITS:
        path = folder / (split + '.json')
        if digest(path) != manifest['file_sha256'][split]:
            errors.append('Split SHA256 mismatch: ' + split)
        rows = json.loads(path.read_text())
        for row in rows:
            task_id = row['task_id']
            membership[task_id].append(split)
            original = by_id.get(task_id)
            if original is None:
                errors.append('Unknown task ID: ' + task_id)
            elif row['project_name'] != original['project_name'] or row['repository_group'] != canonical(original['project_main_repo']):
                errors.append('Row metadata mismatch: ' + task_id)
            if row['split'] != split:
                errors.append('Row split mismatch: ' + task_id)
        stats[split] = {'tasks': len(rows), 'projects': len({x['project_name'] for x in rows}),
                        'repository_groups': len({x['repository_group'] for x in rows})}
        if stats[split] != manifest['statistics'][split]:
            errors.append('Statistics mismatch: ' + split)
    if set(membership) != set(by_id):
        errors.append('Split coverage differs from source')
    if any(len(s) != 1 for s in membership.values()):
        errors.append('Duplicate task membership')

    def cross_groups(key):
        groups = defaultdict(list)
        for task in tasks:
            value = key(task)
            if value:
                groups[value].append(task['task_id'])
        return [{'fingerprint': hashlib.sha256(value.encode()).hexdigest(),
                 'task_ids': sorted(ids),
                 'projects': sorted({by_id[i]['project_name'] for i in ids}),
                 'splits': sorted({s for i in ids for s in membership.get(i, [])})}
                for value, ids in sorted(groups.items())
                if len({s for i in ids for s in membership.get(i, [])}) > 1]

    overlaps = {
        'project': cross_groups(lambda t: t['project_name']),
        'canonical_repository': cross_groups(lambda t: canonical(t['project_main_repo'])),
        'canonical_homepage': cross_groups(lambda t: canonical(t['project_homepage'])),
        'repository_basename_candidates': cross_groups(lambda t: canonical(t['project_main_repo']).split('/')[-1].lower()),
        'exact_description': cross_groups(lambda t: t['vulnerability_description']),
        'whitespace_normalized_description': cross_groups(lambda t: re.sub(r'\s+', ' ', t['vulnerability_description']).strip()),
        'explicit_cve_id': cross_groups(lambda t: '|'.join(sorted(set(re.findall(r'\bCVE-\d{4}-\d{4,}\b', t['vulnerability_description'], re.I))))),
    }
    for field in ['project', 'canonical_repository', 'canonical_homepage', 'exact_description', 'whitespace_normalized_description']:
        if overlaps[field]:
            errors.append('Cross-split matches requiring review: ' + field)
    smoke = json.loads((root / 'data/manifests/smoke-tasks.json').read_text())
    reserved = {t['project_name'] for t in smoke}
    reserved.update(t['project_name'] for t in tasks if t['task_id'] == 'arvo:10400')
    if any(membership[t['task_id']] != ['infra_only'] for t in tasks if t['project_name'] in reserved):
        errors.append('Smoke project quarantine violated')

    return {'checked_at': datetime.now(timezone.utc).isoformat(),
            'status': 'LOCAL_METADATA_CHECKS_FAILED' if errors else 'LOCAL_METADATA_CHECKS_PASSED_REVIEW_INCOMPLETE',
            'errors': errors, 'source_sha256': digest(source), 'task_count': len(tasks),
            'statistics': stats, 'cross_split_matches': overlaps,
            'cve_ids_present_in_descriptions': sum(bool(re.search(r'\bCVE-\d{4}-\d{4,}\b', t['vulnerability_description'], re.I)) for t in tasks),
            'split_frozen': False, 'leakage_absence_certified': False,
            'remaining_review': [
                'No fix commits, crash signatures or complete vulnerability IDs in task index; description equality cannot establish vulnerability identity.',
                'Repository URL, homepage and basename checks do not establish GitHub fork ancestry, renamed mirrors or shared source history.',
                'No task workspaces or test solutions inspected; no semantic or source-level duplicate audit performed.',
                'Full smoke-project quarantine is conservative; source-level overlap through shared dependencies remains unassessed.',
            ]}


def main():
    report = audit(ROOT)
    dest = ROOT / 'docs/verification/split-audit.json'
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(dest), 'status': report['status'], 'errors': report['errors'],
                      'cross_split_match_counts': {k: len(v) for k, v in report['cross_split_matches'].items()},
                      'split_frozen': False}, ensure_ascii=False, indent=2))
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
