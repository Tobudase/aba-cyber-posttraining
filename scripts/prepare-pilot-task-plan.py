#!/usr/bin/env python3
"""Deterministic, review-gated pilot task sampling using metadata only."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 'user-cybergym-pilot-v1'


def main():
    policy_path = ROOT / 'configs/evaluation-policy.json'
    if policy_path.is_file() and json.loads(policy_path.read_text()).get('official_tasks_are_evaluation_only'):
        raise SystemExit('Cancelled by Han instruction: this pilot samples official CyberGym evaluation tasks. Use an external training/validation pool; do not regenerate this plan.')
    def read(name):
        return json.loads((ROOT / name).read_text())

    alias = read('docs/verification/repository-alias-review.json')
    arvo = read('docs/verification/arvo-fix-group-audit.json')
    inventory = read('docs/verification/oss-fuzz-inventory-audit.json')
    membership = {x['task_id']: x for split in ['train', 'dev', 'test', 'infra_only']
                  for x in read(f'data/manifests/splits-draft/{split}.json')}
    parent = {task_id: task_id for task_id in membership}

    def find(task_id):
        while parent[task_id] != task_id:
            parent[task_id] = parent[parent[task_id]]
            task_id = parent[task_id]
        return task_id

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    # Same patch/description is a conservative sampling group, not proof that the
    # vulnerabilities are identical. No original task IDs are deleted or moved.
    for match in inventory['duplicate_artifact_groups']:
        if match['artifact_name'] not in ['patch.diff', 'description.txt']:
            continue
        for task_id in match['task_ids'][1:]:
            union(match['task_ids'][0], task_id)
    groups = defaultdict(list)
    for task_id in membership:
        groups[find(task_id)].append(task_id)
    if any(len({membership[i]['split'] for i in ids}) > 1 for ids in groups.values()):
        raise RuntimeError('Conservative sampling group crosses splits')

    alias_status = {(x['project'], x['index_repository'], x['metadata_repository']): x['status']
                    for x in alias['reviews']}
    holds = {}
    for row in arvo['repository_aliases']:
        status = alias_status[(row['project_name'], row['index_repository'], row['metadata_repository'])]
        if status != 'CONFIRMED_SAME_GITHUB_REPOSITORY_ID':
            holds[row['task_id']] = status
    # This particular repo_addr could describe a dependency instead of the task.
    if 'arvo:42275' in holds:
        holds['arvo:42275'] = 'HIGH_PRIORITY_SPIRV_TOOLS_VS_TINT_METADATA_REVIEW'

    def rank(value):
        return hashlib.sha256((SEED + '\0' + value).encode()).hexdigest()

    selected = {}
    eligibility = {}
    for split, size in [('train', 32), ('dev', 12)]:
        by_project = defaultdict(list)
        for ids in groups.values():
            valid = [i for i in ids if membership[i]['split'] == split and i not in holds]
            if not valid:
                continue
            task_id = min(valid, key=rank)
            by_project[membership[task_id]['project_name']].append(task_id)
        projects = sorted(by_project, key=rank)
        if len(projects) < size:
            raise RuntimeError('Insufficient eligible projects for pilot')
        selected[split] = [dict(membership[min(by_project[p], key=rank)],
                                sampling_group_sha256=hashlib.sha256('\0'.join(sorted(groups[find(min(by_project[p], key=rank))])).encode()).hexdigest())
                           for p in projects[:size]]
        eligibility[split] = {'original_tasks': sum(x['split'] == split for x in membership.values()),
                              'tasks_pending_repository_review': sum(membership[i]['split'] == split for i in holds),
                              'eligible_sampling_groups': sum(bool([i for i in ids if membership[i]['split'] == split and i not in holds]) for ids in groups.values()),
                              'eligible_projects': len(projects), 'pilot_tasks': size}
    if {x['project_name'] for x in selected['train']} & {x['project_name'] for x in selected['dev']}:
        raise RuntimeError('Pilot train/dev project overlap')
    files = ['data/manifests/splits-draft/manifest.json', 'docs/verification/repository-alias-review.json',
             'docs/verification/arvo-fix-group-audit.json', 'docs/verification/oss-fuzz-inventory-audit.json']
    report = {'status': 'DRAFT_REVIEW_GATED_NO_TASK_EXECUTION', 'seed': SEED,
              'purpose': 'First data-collection and baseline cost pilot; not an official benchmark result',
              'input_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
              'selection': 'One task per project; conservative identical-artifact groups; unresolved repository metadata excluded',
              'eligibility': eligibility, 'train_data_collection_tasks': selected['train'],
              'dev_baseline_tasks': selected['dev'], 'test_tasks_selected_for_tuning': [],
              'review_holds': [{'task_id': i, 'split': membership[i]['split'], 'reason': reason} for i, reason in sorted(holds.items())],
              'duplicate_sampling_groups': [{'task_ids': sorted(ids), 'split': membership[ids[0]]['split']}
                                             for ids in groups.values() if len(ids) > 1],
              'execution_budget': {'provisional': True, 'attempts_per_task': 1,
                                   'wall_clock_seconds_per_task': 600,
                                   'model_requests_per_task_max': 40,
                                   'generated_tokens_per_task_max': 16384,
                                   'parallel_tasks_initial': 1,
                                   'entire_pilot_max_wall_clock_hours_at_sequential_budget': round(44 * 600 / 3600, 3),
                                   'note': 'Budgets must be enforced by a real task runner and fixed for pre/post comparison; none executed here.'},
              'preconditions': ['Finalize research split and audit limitations before formal domain collection',
                                'Working permitted task executor; fixed neutral bridge does not satisfy this',
                                'Exact student-model deployment and actual teacher model identity verified',
                                'Server raw evidence and final selected artifact validation ready'],
              'task_contents_downloaded': False, 'training_data_created': False,
              'notes': ['Hold flags change sampling eligibility only; original task split manifests are untouched.',
                        'Exclusion is conservative and may reduce representativeness; disclose it in pilot reporting.',
                        'A matching patch can fix multiple distinct bugs. Do not silently relabel tasks as duplicate bugs.',
                        'Dev 12-task pilot is exploratory; it cannot provide a precise final benchmark estimate.']}
    path = ROOT / 'data/manifests/pilot-task-plan.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'plan': str(path), 'status': report['status'], 'eligibility': eligibility,
                      'review_holds_all_splits': len(holds),
                      'conservative_duplicate_sampling_groups': len(report['duplicate_sampling_groups'])}, indent=2))


if __name__ == '__main__':
    main()
