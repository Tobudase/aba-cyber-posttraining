#!/usr/bin/env python3
"""Verify persisted training and recompute matched E0/E1, no model generation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from benchkit import ROOT, final_text, load_jsonl, load_manifest, score_predictions, sha, write_json


def main():
    protocol_file = ROOT / 'configs/kali-doc-sft-v1.protocol.json'
    protocol = json.loads(protocol_file.read_text())
    root = ROOT / 'docs/verification/kali-doc-sft-v1-2026-10-22'
    training = json.loads((root / 'train/receipt.json').read_text())
    evaluation = json.loads((root / 'evaluation/receipt.json').read_text())
    for record in [training, evaluation]:
        if record['status'] != 'COMPLETE' or record['protocol_sha256'] != sha(protocol_file.read_bytes()):
            raise ValueError('Incomplete/mismatched frozen run')
        if record['official_test_rows'] or record['confirmation_rows_queried'] or record['ABA_executed']:
            raise ValueError('Experiment scope violated')
    if evaluation['training_receipt_sha256'] != sha((root / 'train/receipt.json').read_bytes()):
        raise ValueError('Evaluation used another training run')
    if training['optimizer_steps'] != 108 or training['changed_parameter_tensors'] != 16 or training['adapter_reload_max_abs_logit_delta'] > 1e-5:
        raise ValueError('Actual optimization/persistence check failed')
    _, train = load_manifest(ROOT / protocol['train_manifest'], 'train')
    if len(training['train_ids']) != len(set(training['train_ids'])) or set(training['train_ids']) != {r['id'] for r in train}:
        raise ValueError('Training was not one pass over the frozen108rows')
    for name, checksum in training['adapter_files'].items():
        if sha((root / 'train/adapter' / name).read_bytes()) != checksum: raise ValueError('Adapter changed')
    comparisons = {}; outcome_changes = {}
    for name, check in protocol['evaluation'].items():
        manifest = ROOT / check['manifest']
        if sha(manifest.read_bytes()) != check['manifest_sha256']: raise ValueError('Dev data changed')
        # Search-only loading; no confirmation body is needed by the analysis.
        spec = json.loads(manifest.read_text()); part = spec['splits'][check['split']]
        path = manifest.parent / part['file']
        if sha(path.read_bytes()) != part['sha256']: raise ValueError('Search bytes changed')
        rows = load_jsonl(path); indexed = {r['id']: r for r in rows}
        base_path = ROOT / check['baseline_directory'] / 'predictions.jsonl'
        if sha(base_path.read_bytes()) != check['baseline_predictions_sha256']: raise ValueError('Baseline outputs changed')
        before = load_jsonl(base_path); after_path = root / 'evaluation' / name / 'predictions.jsonl'
        after = load_jsonl(after_path)
        if sha(after_path.read_bytes()) != evaluation['evaluations'][name]['predictions_sha256']: raise ValueError('New outputs changed')
        a = {r['id']: r for r in before}; b = {r['id']: r for r in after}
        if set(a) != set(b) or set(a) != set(indexed): raise ValueError('Different evaluated rows')
        if any(a[i]['prompt_sha256'] != b[i]['prompt_sha256'] for i in a): raise ValueError('Different inference prompts')
        scores0 = score_predictions(rows, before, 'kali'); scores1 = score_predictions(rows, after, 'kali')
        if scores0['summary'] != evaluation['evaluations'][name]['baseline'] or scores1['summary'] != evaluation['evaluations'][name]['post']:
            raise ValueError('Independent recomputation differs from recorded metrics')
        detail0 = {d['id']: d for d in scores0['details']}; detail1 = {d['id']: d for d in scores1['details']}
        changes = []
        for i in indexed:
            if detail0[i]['strict_option_value_correct'] != detail1[i]['strict_option_value_correct']:
                changes.append({'id': i, 'base_correct': bool(detail0[i]['strict_option_value_correct']),
                    'post_correct': bool(detail1[i]['strict_option_value_correct']),
                    'reference_command': indexed[i]['native_label']['ground_truth_command'],
                    'baseline_command': detail0[i]['pred_cmd'], 'post_command': detail1[i]['pred_cmd'],
                    'semantic_equivalence_review': 'PENDING_NOT_ALL_CANONICAL_CHANGES_ARE_NEW_SKILLS'})
        comparisons[name] = {'rows': len(rows), 'baseline_correct': sum(d['strict_option_value_correct'] for d in scores0['details']),
            'post_correct': sum(d['strict_option_value_correct'] for d in scores1['details']),
            'baseline_native': scores0['summary'], 'post_native': scores1['summary'],
            'gains': sum(not r['base_correct'] and r['post_correct'] for r in changes),
            'regressions': sum(r['base_correct'] and not r['post_correct'] for r in changes),
            'post_complete_XML': evaluation['evaluations'][name]['complete_XML_rows'],
            'post_truncated': evaluation['evaluations'][name]['truncated_rows']}
        outcome_changes[name] = changes
    d, r = comparisons['domain'], comparisons['retention']
    rule = {'domain_exact_strictly_improves': d['post_native']['exact_match'] > d['baseline_native']['exact_match'],
        'domain_option_diagnostic_strictly_improves': d['post_correct'] > d['baseline_correct'],
        'domain_total_not_decreased': d['post_native']['total_score'] >= d['baseline_native']['total_score'],
        'retention_not_decreased': r['post_correct'] >= r['baseline_correct'],
        'no_truncation_runtime_XML_failures': all(x['post_truncated'] == 0 and x['post_complete_XML'] == x['rows'] and x['post_native']['runtime_failed_rows'] == 0 for x in comparisons.values())}
    passed = all(rule.values())
    probe0 = training['fixed_train_probe_loss_before']; probe1 = training['fixed_train_probe_loss_after']
    report = {'status': 'FIXED_LOCAL_DOC_SFT_CYCLE_COMPLETE', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'protocol_sha256': sha(protocol_file.read_bytes()), 'train_rows': 108, 'training_steps': 108,
        'training_source': 'AI_doc_reviewed_source_silver', 'independent_expert_review': False,
        'comparisons': comparisons, 'changed_outcomes': outcome_changes,
        'fixed_rule_checks': rule, 'fixed_rule_passed': passed,
        'decision': 'PRELIMINARY_LOCAL_CANDIDATE_ONLY_REQUIRES_INDEPENDENT_VALIDATION' if passed else 'KEEP_ORIGINAL_BASE_DO_NOT_PROMOTE_ADAPTER',
        'train_probe_mean_loss_before': sum(probe0) / len(probe0), 'train_probe_mean_loss_after': sum(probe1) / len(probe1),
        'train_probe_scope': 'Same8training records, not validation or evidence of generalization',
        'train_peak_metal_bytes': training['peak_metal_memory_bytes'], 'eval_peak_metal_bytes': evaluation['peak_metal_memory_bytes'],
        'train_wall_seconds': training['wall_seconds'], 'eval_wall_seconds': evaluation['wall_seconds'],
        'adapter_reload_logit_delta': training['adapter_reload_max_abs_logit_delta'],
        'training_receipt_sha256': sha((root / 'train/receipt.json').read_bytes()),
        'evaluation_receipt_sha256': sha((root / 'evaluation/receipt.json').read_bytes()),
        'official_test_rows': 0, 'confirmation_rows_queried': 0, 'actual_ABA_executed': False,
        'limitations': protocol['limitations'] + ['Changes in canonical matching need semantic review; do not equate every gain with new tool competence.',
            'This is one pre-frozen manualSFT candidate; no multiple-run tuning based on these outcomes.']}
    write_json(root / 'comparison.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'changed_outcomes'}, indent=2))


if __name__ == '__main__': main()
