#!/usr/bin/env python3
"""Check the public posthoc aggregate against the unchanged confirmation release."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/kali-posthoc-audit-2026-10-27'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = read(OUT / 'manifest.json')
    for name, digest in manifest['file_sha256'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert sha(path) == digest, name
    parent = read(ROOT / 'results/kali-bf16-confirmation-2026-10-26/summary.json')
    audit = read(OUT / 'audit.json')
    assert audit['predeclared_summary_sha256'] == sha(
        ROOT / 'results/kali-bf16-confirmation-2026-10-26/summary.json')
    assert parent['confirmation_gate']['passes_confirmation_gate'] is False
    assert parent['candidate_promoted'] is False
    assert audit['gate_recomputed_or_changed'] is False
    assert audit['model_calls'] == audit['optimizer_steps'] == audit['official_test_calls'] == 0
    for arm in ('base', 'sft'):
        a = audit['arms'][arm]
        assert a['rows'] == 72 and a['reviewed'] + a['unsupported_not_executed'] == 72
        assert a['unsupported_not_executed'] == sum(audit['unsupported_by_tool'][arm].values())
        assert a['verified_correct'] == parent['CONFIRMATION'][arm]['correct']
    assert audit['arms']['base']['unsupported_not_executed'] == 47
    assert audit['arms']['sft']['unsupported_not_executed'] == 6
    assert sum(audit['base_unsupported_to_sft'].values()) == 47
    assert audit['private_commands_or_task_ids_released'] is False
    print(json.dumps({'status': 'PASS_POSTHOC_AGGREGATE_ONLY',
                      'parent_gate_passed': False,
                      'verified_files': len(manifest['file_sha256']),
                      'private_rows_reproduced': False}))


if __name__ == '__main__':
    main()
