#!/usr/bin/env python3
"""Separate upstream gold/scorer inconsistencies without editing source records."""
import json

from benchkit import ROOT, artifact_spec, load_manifest, write_json, write_jsonl


def main():
    audit = json.loads((ROOT / 'docs/verification/benchkit-scorer-audit.json').read_text())
    held = {r['id'] for r in audit['kali_train_gold_echo_failures']}
    spec, rows = load_manifest(ROOT / 'data/benchkit/kali/manifest.json', 'train')
    included = [r for r in rows if r['id'] not in held]
    excluded = [dict(r, training_eligible=False, hold_reason='NATIVE_GOLD_ECHO_NOT_PERFECT_REQUIRES_SOURCE_SCORER_RECONCILIATION') for r in rows if r['id'] in held]
    directory = ROOT / 'data/benchkit/kali-screened'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'train.jsonl'; write_jsonl(path, included)
    write_jsonl(directory / 'hold.jsonl', excluded)
    write_json(directory / 'manifest.json', {'schema': 'benchkit.dataset.v1', 'benchmark': 'kali',
        'official_test': False, 'splits': {'train': artifact_spec(path, included)},
        'limitations': spec['limitations'] + ['128 train rows held due to nonperfect GT/scorer roundtrip; not proven all are wrong labels.',
                                            'Native scorer still ignores some option values; screening is not full semantic validation.']})
    report = {'status': 'TRAIN_SCREENED_WITH_HOLDS', 'original_train': len(rows),
              'screened_train': len(included), 'held': len(excluded),
              'source_records_edited': False, 'official_test_files_downloaded': 0}
    write_json(ROOT / 'docs/verification/kali-train-screening.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
