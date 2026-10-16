#!/usr/bin/env python3
"""Audit public author-designated Python training files, never official test files."""
import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import warnings

ROOT = Path(__file__).resolve().parents[1]
REV = '5357371a2271df1048666220415a3bc937af5f9d'
CWES = [120, 179, 200, 295, 327, 352, 367, 400, 502, 611, 74, 78, 79, 862, 863, 89, 915, 918, 94, 95]
warnings.filterwarnings('ignore', category=SyntaxWarning)


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def download(cwe):
    relative = f'datasets/train/function_level/python/CWE-{cwe}.json'
    cached = ROOT / f'.tools/vulnllmr-training-python/CWE-{cwe}.json'
    previous = ROOT / 'docs/verification/vulnllmr-python-training-audit.json'
    if cached.exists() and previous.exists():
        old = json.loads(previous.read_text())
        meta = next((x for x in old['source_files'] if x['path'] == relative), None)
        if old['source_commit'] == REV and meta:
            raw = cached.read_bytes()
            if digest(raw) != meta['sha256'] or len(raw) != meta['bytes']:
                raise ValueError('Previously audited training cache changed')
            return meta, json.loads(raw)
    url = f'https://raw.githubusercontent.com/ucsb-mlsec/VulnLLM-R/{REV}/{relative}'
    def fetch(address):
        return subprocess.check_output(['curl', '--fail', '--silent', '--show-error', '--location',
                                        '--max-time', '45', '--max-filesize', '5000000', address])
    raw = fetch(url)
    lfs = raw.startswith(b'version https://git-lfs')
    if lfs:
        pointer = raw.decode()
        expected = re.search(r'oid sha256:([0-9a-f]{64})', pointer).group(1)
        size = int(re.search(r'^size (\d+)$', pointer, re.M).group(1))
        if size > 5000000:
            raise ValueError('Source file exceeds bounded download size')
        raw = fetch(f'https://media.githubusercontent.com/media/ucsb-mlsec/VulnLLM-R/{REV}/{relative}')
        if digest(raw) != expected or len(raw) != size:
            raise ValueError('LFS integrity mismatch')
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError('Unexpected dataset format')
    dest = ROOT / f'.tools/vulnllmr-training-python/CWE-{cwe}.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return {'path': relative, 'sha256': digest(raw), 'bytes': len(raw), 'records': len(records),
            'lfs_verified': lfs}, records


def main():
    artifacts, records = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for artifact, source in pool.map(download, CWES):
            artifacts.append(artifact)
            for item in source:
                if not isinstance(item.get('code'), str) or item.get('target') not in (0, 1):
                    raise ValueError('Unexpected training record schema')
                records.append({**item, 'source_path': artifact['path']})
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i, j):
        parent[find(i)] = find(j)
    owners = {}
    features = []
    adjacent_pair_edges = 0
    class NormalizeNames(ast.NodeTransformer):
        def __init__(self):
            self.names = {}
        def rename(self, name):
            if name not in self.names:
                self.names[name] = 'id_' + str(len(self.names))
            return self.names[name]
        def visit_Name(self, node):
            node.id = self.rename(node.id)
            return node
        def visit_arg(self, node):
            node.arg = self.rename(node.arg)
            return self.generic_visit(node)
        def visit_FunctionDef(self, node):
            node.name = self.rename(node.name)
            return self.generic_visit(node)
        visit_AsyncFunctionDef = visit_FunctionDef
    for i, row in enumerate(records):
        code = row['code']
        keys = ['exact:' + digest(code), 'identity:' + str(row['dataset']) + ':' + str(row['idx'])]
        try:
            tree = ast.parse(code)
            keys.append('ast:' + digest(ast.dump(tree, include_attributes=False)))
            functions = sorted({n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))})
            if functions:
                # Conservative proxy only. No claim that function names recover every source seed.
                keys.append('function-proxy:' + str(row['dataset']) + ':' + ','.join(functions))
            normalized = NormalizeNames().visit(ast.parse(code))
            keys.append('identifier-normalized-ast-proxy:' + digest(ast.dump(normalized, include_attributes=False)))
        except (SyntaxError, ValueError):
            functions = []
        for key in keys:
            if key in owners:
                union(i, owners[key])
            else:
                owners[key] = i
        features.append({'code_sha256': digest(code), 'functions': functions})
    # Producer appends vulnerable then patched forms, assigning consecutive idx values.
    # This is a conservative inferred pair edge, not recovery of original generation-seed IDs.
    by_id = {(r['dataset'], str(r['idx'])): i for i, r in enumerate(records)}
    for i, row in enumerate(records):
        if row['dataset'] == 'seccodeplt' and row['target'] == 1:
            j = by_id.get(('seccodeplt', str(int(row['idx']) + 1)))
            if j is not None and records[j]['target'] == 0 and row['CWE_ID'] == records[j]['CWE_ID']:
                union(i, j)
                adjacent_pair_edges += 1
    groups = defaultdict(list)
    for i in range(len(records)):
        groups[find(i)].append(i)
    smoke = json.loads((ROOT / 'data/manifests/vulnllmr-development-smoke.json').read_text())['samples']
    smoke_hashes = {x['code_sha256'] for x in smoke}
    smoke_ids = {(x['dataset'], str(x['id'])) for x in smoke}
    manifest = []
    for indexes in groups.values():
        ids = sorted(f"{records[i]['source_path']}:{records[i]['idx']}:{features[i]['code_sha256']}" for i in indexes)
        group = digest('\n'.join(ids))
        reasons = []
        if any(records[i].get('human') for i in indexes):
            reasons.append('component_contains_human_test_marker')
        if any(features[i]['code_sha256'] in smoke_hashes or (records[i]['dataset'], str(records[i]['idx'])) in smoke_ids for i in indexes):
            reasons.append('component_contains_smoke_example')
        bucket = 'hold' if reasons else ('proposal_validation' if int(digest('vulnllmr-draft-v1:' + group)[:8], 16) % 5 == 0 else 'proposal_train')
        for i in indexes:
            row = records[i]
            manifest.append({'id': str(row['idx']), 'dataset': row['dataset'], 'source_path': row['source_path'],
                'code_sha256': features[i]['code_sha256'], 'group': group, 'assignment': bucket,
                'target': row['target'], 'cwes': row['CWE_ID'], 'human_marker': bool(row.get('human')),
                'hold_reasons': reasons, 'training_eligible': False})
    manifest.sort(key=lambda x: (x['source_path'], x['id']))
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'DRAFT_AUDIT_INCOMPLETE',
        'source_commit': REV, 'source_files': artifacts, 'records': len(records),
        'class_counts': dict(Counter(str(x['target']) for x in records)),
        'human_marked_records': sum(bool(x.get('human')) for x in records), 'proxy_components': len(groups),
        'assignments': dict(Counter(x['assignment'] for x in manifest)),
        'unique_code_hashes': len({x['code_sha256'] for x in manifest}),
        'inferred_adjacent_pair_edges': adjacent_pair_edges,
        'dataset_sources': dict(Counter(x['dataset'] for x in records)),
        'official_test_contents_accessed': False, 'original_gated_dataset_files_accessed': False,
        'grouping_limit': 'Exact code, AST, record identity, inferred adjacent vulnerable/patched pairs, conservative function-name and identifier-normalized AST proxies. Original generation-seed IDs unavailable; over-merging is possible and semantic independence is not proven.',
        'validation_limit': 'Draft validation comes from published training corpus, possibly seen by the pretrained checkpoint; not a novel held-out evaluation.',
        'formal_split_frozen': False}
    path = ROOT / 'data/manifests/vulnllmr-python-training-draft.json'
    path.write_text(json.dumps({'protocol': report, 'records': manifest}, ensure_ascii=False, indent=2) + '\n')
    report['manifest_sha256'] = digest(path.read_bytes())
    (ROOT / 'docs/verification/vulnllmr-python-training-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'records', 'class_counts', 'human_marked_records',
                                           'proxy_components', 'assignments', 'unique_code_hashes']}, indent=2))


if __name__ == '__main__':
    main()
