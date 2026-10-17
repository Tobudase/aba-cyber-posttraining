#!/usr/bin/env python3
"""Use pinned, unchanged FAITH RCM extraction and aggregation on local records."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'.tools/cti-review/faith'


def verified_source():
    manifest = json.loads((ROOT/'configs/cti-reviewed-files.lock.json').read_text())
    for name, record in manifest.items():
        if name.startswith('faith/'):
            path = ROOT/'.tools/cti-review'/name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], name
    sys.path.insert(0, str(SOURCE/'src'))


def final_answer(text, reasoning_prefilled=True):
    """Do not grade reasoning tokens when the prompt prefills <think>."""
    if '</think>' in text:
        return text.rsplit('</think>', 1)[1].strip()
    if reasoning_prefilled or '<think>' in text:
        return ''
    return text.strip()


def grade(rows):
    verified_source()
    from faith.benchmark.config import load_config_from_path
    from faith.benchmark.grading.common_graders import ChatCompletionLogGrader
    from faith.benchmark.qa.short_answer import SAMetricsAggregator
    from faith._types.record.sample import SampleRecord, Metadata
    from faith._types.record.prompt import PromptRecord
    from faith._types.record.model import ModelRecord
    from faith._types.record.model_response import ChatResponse
    config = load_config_from_path(SOURCE/'src/faith/__benchmarks__/ctibench-rcm')
    records = []
    for index, row in enumerate(rows):
        text = row.get('answer_text', '')
        prompt = PromptRecord(index, row['id'], None, None, None,
                              row.get('description', ''), None, row['label'],
                              row.get('description', ''), row['label'],
                              row.get('description', ''))
        response = ChatResponse(output_text=text, answer_text=text,
                                num_output_tokens=row.get('output_tokens', 0),
                                max_token_halt=row.get('truncated', False))
        records.append(SampleRecord(Metadata('cti-engineering-v1'), prompt,
                                   ModelRecord('', {}, chat_comp=response)))
    graded = list(ChatCompletionLogGrader(config.output_processing, None)(records))
    metrics = SAMetricsAggregator(config.output_processing, config.saqa_config.type)([r.stats for r in graded])
    details = []
    for row, record in zip(rows, graded):
        stats = record.stats
        details.append({'id': row['id'], 'label': row['label'],
                        'prediction': stats.prediction,
                        'answer_format': str(stats.answer_format),
                        'strict_correct': stats.prediction == row['label'] and str(stats.answer_format) == 'proper'})
    # Native accuracy, plus an explicit attempted-record denominator.
    metrics['attempted_record_accuracy'] = sum(x['strict_correct'] for x in details)/len(rows)
    return metrics, details


def json_default(value):
    if hasattr(value, 'item'):
        return value.item()
    raise TypeError(type(value).__name__)


def self_check():
    cases = [
        ('canonical', 'CWE-89', 'CWE-89', True, False),
        ('unicode', 'cwe‑89', 'CWE-89', True, False),
        ('improper', 'cwe: 89', 'CWE-89', False, False),
        ('ambiguous', 'Consider CWE-20.\nCWE-89', 'CWE-89', False, False),
        ('repeated', 'CWE-89 is applicable.\nCWE-89', 'CWE-89', True, False),
        ('prefix_collision', 'CWE-125', 'CWE-12', False, False),
        ('refusal', 'I cannot determine it.', 'CWE-89', False, False),
        ('suffix_collision', 'CWE-89A', 'CWE-89', False, False),
        ('leading_zero', 'CWE-089', 'CWE-89', False, False),
        ('completed_reasoning', 'Consider CWE-20.</think>\nCWE-89', 'CWE-89', True, True),
        ('unclosed_reasoning', 'I think the answer may be CWE-89', 'CWE-89', False, True),
        ('multiple_final', 'CWE-89, CWE-20', 'CWE-89', False, False),
    ]
    rows = [{'id': name, 'label': label,
             'answer_text': final_answer(text, reasoning) if reasoning else text}
            for name, text, label, expected, reasoning in cases]
    metrics, details = grade(rows)
    for case, detail in zip(cases, details):
        assert detail['strict_correct'] == case[3], (case, detail)
    assert abs(float(metrics['accuracy'])-4/12) < 1e-12
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'PASSED', 'checks': len(cases),
              'faith_revision': json.loads((ROOT/'configs/cti-candidates.lock.json').read_text())['repositories']['faith']['revision'],
              'upstream_modified': False, 'official_records_used': 0,
              'native_metrics': metrics, 'cases': details,
              'current_rcm_config_drops_duplicate_rows': [243,453,531,600,602,681,689,691,776,788],
              'current_config_expected_rows': 990,
              'paper_denominator_equivalence_verified': False}
    path = ROOT/'docs/verification/cti-native-scorer-check.json'
    path.write_text(json.dumps(report, indent=2, default=json_default)+'\n')
    print(json.dumps({'status': report['status'], 'checks': len(cases), 'report': str(path)}))


if __name__ == '__main__':
    self_check()
