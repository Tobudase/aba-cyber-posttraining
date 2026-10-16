#!/usr/bin/env python3
"""Resolve public GitHub repository identities; leave other alias claims unconfirmed."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').exists() else ssl.create_default_context()


def main():
    source = json.loads((ROOT / 'docs/verification/arvo-fix-group-audit.json').read_text())
    counts = Counter((r['project_name'], r['index_repository'], r['metadata_repository'])
                     for r in source['repository_aliases'])
    cache = ROOT / '.tools/repository-identity'
    cache.mkdir(parents=True, exist_ok=True)
    pairs = sorted({repo.removeprefix('github.com/') for _, a, b in counts
                    if a.startswith('github.com/') and b.startswith('github.com/') for repo in [a, b]})

    def resolve(repo):
        path = cache / (repo.replace('/', '__') + '.json')
        if path.is_file():
            return repo, json.loads(path.read_text())
        request = urllib.request.Request('https://api.github.com/repos/' + repo,
            headers={'User-Agent': 'UCSD-repository-identity-review/1.0', 'Accept': 'application/vnd.github+json'})
        try:
            with urllib.request.urlopen(request, timeout=25, context=CONTEXT) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise RuntimeError('Repository metadata size bound exceeded')
                obj = json.loads(raw)
                result = {'ok': True, 'id': obj['id'], 'full_name': obj['full_name'],
                          'api_final_url': response.url, 'fork': obj['fork'],
                          'parent_id': obj.get('parent', {}).get('id'),
                          'source_id': obj.get('source', {}).get('id')}
        except urllib.error.HTTPError as error:
            result = {'ok': False, 'http_status': error.code}
        path.write_text(json.dumps(result, indent=2) + '\n')
        return repo, result

    with ThreadPoolExecutor(max_workers=2) as pool:
        resolved = dict(pool.map(resolve, pairs))
    reviews = []
    for (project, index, meta), count in sorted(counts.items()):
        row = {'project': project, 'index_repository': index, 'metadata_repository': meta, 'tasks': count}
        if index.startswith('github.com/') and meta.startswith('github.com/'):
            a, b = resolved[index.removeprefix('github.com/')], resolved[meta.removeprefix('github.com/')]
            row['github_index'], row['github_metadata'] = a, b
            row['status'] = 'UNRESOLVED_API_ERROR'
            if a['ok'] and b['ok']:
                row['status'] = 'CONFIRMED_SAME_GITHUB_REPOSITORY_ID' if a['id'] == b['id'] else 'DISTINCT_GITHUB_REPOSITORY_IDS_REVIEW_REQUIRED'
        else:
            row['status'] = 'CROSS_HOST_RELATIONSHIP_NOT_VERIFIED'
        if project == 'spirv-tools':
            row['priority'] = 'HIGH'
            row['note'] = 'Metadata repo_addr points to Tint rather than the indexed SPIRV-Tools repository. Could reflect a dependency build; task label must be checked before use.'
        reviews.append(row)
    counts_by_status = Counter(x['status'] for x in reviews)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'alias_groups': len(reviews),
              'affected_task_records': sum(x['tasks'] for x in reviews),
              'groups_by_status': dict(counts_by_status),
              'task_records_by_status': dict(Counter({status: sum(x['tasks'] for x in reviews if x['status'] == status)
                                                      for status in counts_by_status})),
              'reviews': reviews, 'split_frozen': False,
              'limitations': ['GitHub repository identity verifies rename/transfer only; it does not verify vulnerability or fix semantics.',
                             'Cross-host mirrors and dependency relationships require additional evidence.',
                             'No task solution, patch or input content inspected.']}
    dest = ROOT / 'docs/verification/repository-alias-review.json'
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['alias_groups', 'affected_task_records', 'groups_by_status', 'task_records_by_status']}, indent=2))


if __name__ == '__main__':
    main()
