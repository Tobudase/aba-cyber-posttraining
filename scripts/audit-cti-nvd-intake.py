#!/usr/bin/env python3
"""Audit a small public NVD intake, keep all records in research-review hold."""
from collections import Counter
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--week',action='store_true')
args=parser.parse_args()
cohort='cti-nvd-week' if args.week else 'cti-nvd'
source = ROOT/('.tools/cti-review/nvd-week-raw.json' if args.week else '.tools/cti-review/nvd-recent-raw.json')
fetch = json.loads((ROOT/f'docs/verification/{cohort}-fetch.json').read_text())
assert fetch['status'] == 'FETCHED'
data = json.loads(source.read_text())
accepted, held = [], []
reasons = Counter()
seen = set()
for item in data['vulnerabilities']:
    cve = item['cve']
    identifier = cve['id']
    descriptions = [x['value'] for x in cve.get('descriptions', []) if x['lang']=='en']
    text = descriptions[0].strip() if descriptions else ''
    primary = {d['value'].upper() for w in cve.get('weaknesses', [])
               if w.get('type')=='Primary' for d in w.get('description', [])
               if re.fullmatch(r'CWE-[1-9]\d*', d['value'], re.I)}
    all_labels = {d['value'].upper() for w in cve.get('weaknesses', [])
                  for d in w.get('description', [])
                  if re.fullmatch(r'CWE-[1-9]\d*', d['value'], re.I)}
    labels = primary or all_labels
    issues = []
    if identifier in seen: issues.append('duplicate_cve')
    seen.add(identifier)
    if not identifier.startswith('CVE-2026-'): issues.append('identifier_year_not_2026')
    if not cve.get('published','').startswith('2026-10-'): issues.append('outside_selected_publication_month')
    if cve.get('vulnStatus')=='Rejected': issues.append('rejected_record')
    if len(text)<80: issues.append('short_or_missing_english_description')
    if re.search(r'\bCWE[-‑ ]?\d+\b', text, re.I): issues.append('explicit_cwe_label_in_description')
    if len(labels)!=1: issues.append('not_exactly_one_numeric_cwe')
    if primary and all_labels-primary: issues.append('conflicting_primary_secondary_labels')
    record = {'id': identifier, 'published': cve.get('published'),
              'last_modified': cve.get('lastModified'), 'description': text,
              'source_cwe_labels': sorted(labels), 'source_all_cwe_labels': sorted(all_labels),
              'label': next(iter(labels)) if len(labels)==1 else None,
              'label_provenance': 'NVD record Primary weakness when present, otherwise available numeric CWE',
              'source_url': f'https://nvd.nist.gov/vuln/detail/{identifier}',
              'reference_urls': sorted({x['url'] for x in cve.get('references', [])}),
              'status': 'HOLD_RESEARCH_REVIEW', 'training_eligible': False,
              'official_benchmark_record': False, 'synthetic_only': False,
              'issues': issues}
    if issues:
        held.append(record)
        reasons.update(issues)
    else:
        accepted.append(record)
output = ROOT/'data/raw'/cohort
output.mkdir(parents=True, exist_ok=True)
candidate_text = ''.join(json.dumps(r)+'\n' for r in accepted)
(output/'candidates.jsonl').write_text(candidate_text)
(output/'excluded.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in held))
manifest = {'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'status':'STRUCTURAL_AUDIT_ONLY_ZERO_TRAINING_APPROVED',
            'source_url':fetch['source_url'], 'fetched_records':len(data['vulnerabilities']),
            'source_total_matching_records':data.get('totalResults'),
            'sampling':'Complete fixed publication-week API intake, not necessarily representative' if args.week else 'First API page only; not random or representative',
            'structural_candidates':len(accepted), 'excluded':len(held),
            'exclusion_counts':dict(reasons), 'label_counts':dict(Counter(r['label'] for r in accepted)),
            'source_cache_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'candidate_sha256':hashlib.sha256(candidate_text.encode()).hexdigest(),
            'candidate_identifiers':[r['id'] for r in accepted],
            'description_char_lengths':{'min':min(map(lambda r:len(r['description']), accepted), default=0),
                                        'max':max(map(lambda r:len(r['description']), accepted), default=0)},
            'official_test_records_downloaded':0, 'training_approved':0,
            'temporal_evidence':{'candidate_id_year':2026,
                'official_ctibench_dataset_last_modified': '2024-08-17T00:58:57.000Z',
                'interpretation':'Later CVE identifiers support temporal separation; no official row-level comparison performed'},
            'remaining_checks':['Independent label/context validation',
                'CVE/GHSA aliases, repository, fix and vulnerability-family grouping',
                'Record exact NVD/source attribution and applicable data terms',
                'Freeze non-overlapping research train/dev before training'],
            'raw_descriptions_location':f'data/raw/{cohort} (excluded from handoff/publication)'}
destination = ROOT/f'data/manifests/{cohort}-intake.json'
destination.write_text(json.dumps(manifest,indent=2)+'\n')
(ROOT/f'docs/verification/{cohort}-intake-audit.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:manifest[k] for k in ['status','fetched_records','structural_candidates','excluded','exclusion_counts','label_counts','training_approved']},indent=2))
