#!/usr/bin/env python3
"""Create reproducible, project-disjoint DRAFT splits from public metadata."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SEED = 'user-cybergym-draft-v1'


def canonical_repo(url):
    parsed = urlsplit(url)
    path = parsed.path.rstrip('/').removesuffix('.git')
    if parsed.hostname == 'github.com':
        path = path.lower()
    return (parsed.hostname or '').lower() + path


def main():
    policy_path = ROOT / 'configs/evaluation-policy.json'
    if policy_path.is_file() and json.loads(policy_path.read_text()).get('official_tasks_are_evaluation_only'):
        raise SystemExit('Disabled by Han instruction: official CyberGym tasks are evaluation-only. Split external training/validation data instead; old internal split is superseded.')
    source = ROOT / 'data/manifests/tasks.json'
    tasks = json.loads(source.read_text())
    smoke = json.loads((ROOT / 'data/manifests/smoke-tasks.json').read_text())
    # Conservatively quarantine entire projects represented by public smoke tasks.
    reserved_projects = {t['project_name'] for t in smoke}
    reserved_projects.update(t['project_name'] for t in tasks if t['task_id'] == 'arvo:10400')
    grouped = defaultdict(list)
    for task in tasks:
        grouped[canonical_repo(task['project_main_repo'])].append(task)
    reserved_repos = {repo for repo, rows in grouped.items() if any(t['project_name'] in reserved_projects for t in rows)}
    candidates = sorted(set(grouped) - reserved_repos,
                        key=lambda repo: hashlib.sha256((SEED + '\0' + repo).encode()).hexdigest())
    n = len(candidates)
    n_dev = max(1, round(n * 0.1))
    n_test = max(1, round(n * 0.1))
    assignment = {repo: 'infra_only' for repo in reserved_repos}
    for i, repo in enumerate(candidates):
        assignment[repo] = 'dev' if i < n_dev else 'test' if i < n_dev + n_test else 'train'
    rows = [{'task_id': t['task_id'], 'project_name': t['project_name'],
             'repository_group': canonical_repo(t['project_main_repo']),
             'split': assignment[canonical_repo(t['project_main_repo'])]} for t in tasks]
    assert len({r['task_id'] for r in rows}) == len(tasks)
    project_splits = defaultdict(set)
    for row in rows:
        project_splits[row['project_name']].add(row['split'])
    assert all(len(values) == 1 for values in project_splits.values()), 'Project crosses splits'
    dest = ROOT / 'data/manifests/splits-draft'
    dest.mkdir(parents=True, exist_ok=True)
    stats = {}
    hashes = {}
    for split in ['train', 'dev', 'test', 'infra_only']:
        subset = sorted((r for r in rows if r['split'] == split), key=lambda row: row['task_id'])
        raw = (json.dumps(subset, indent=2) + '\n').encode()
        (dest / f'{split}.json').write_bytes(raw)
        hashes[split] = hashlib.sha256(raw).hexdigest()
        stats[split] = {'tasks': len(subset), 'projects': len({r['project_name'] for r in subset}),
                        'repository_groups': len({r['repository_group'] for r in subset})}
    manifest = {'status': 'DRAFT_NOT_APPROVED_OR_FROZEN', 'seed': SEED,
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'method': 'Repository-group split; 80/10/10 by group count, not task count. Entire smoke projects quarantined.',
                'limitations': ['No claim of official benchmark split', 'Task counts may be imbalanced across groups',
                               'Repository forks and duplicate vulnerabilities require additional review',
                               'Confirm existing group split with Han before collecting training data'],
                'statistics': stats, 'file_sha256': hashes}
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
