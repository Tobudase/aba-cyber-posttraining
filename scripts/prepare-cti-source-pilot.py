#!/usr/bin/env python3
"""Fetch source records for an external, source-labelled CTI pilot; no approval implied."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CATEGORIES=['CWE-787','CWE-125','CWE-502','CWE-78','CWE-918','CWE-89','CWE-22','CWE-79']
REVISION=json.loads((ROOT/'docs/verification/cti-cna-label-audit.json').read_text())['cvelist_revision']
SOURCE=ROOT/'data/raw/cti-nvd-week/candidates.jsonl'
rows=[json.loads(s) for s in SOURCE.read_text().splitlines()]
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==json.loads((ROOT/'data/manifests/cti-nvd-week-intake.json').read_text())['candidate_sha256']
grouping=json.loads((ROOT/'docs/verification/cti-week-intake-groups.json').read_text())
groups={i:g['group_id'] for g in grouping['group_members'] for i in g['ids']}
exposed=set(json.loads((ROOT/'data/manifests/cti-development-exposure.json').read_text())['linked_ids_conservatively_exposed'])
selected=[];used_groups=set()
for label in CATEGORIES:
    candidates=[r for r in rows if r['label']==label and r['id'] not in exposed and 90<=len(r['description'])<=1600]
    candidates.sort(key=lambda r:hashlib.sha256(('cti-source-pilot-v1:'+r['id']).encode()).hexdigest())
    count=0
    for r in candidates:
        if groups[r['id']] in used_groups:continue
        selected.append(r);used_groups.add(groups[r['id']]);count+=1
        if count==16:break
    assert count>=8,(label,count)
cache=ROOT/'.tools/cti-source-pilot/cna'
cache.mkdir(parents=True,exist_ok=True)
def fetch(r):
    number=r['id'].rsplit('-',1)[1]
    url=f'https://raw.githubusercontent.com/CVEProject/cvelistV5/{REVISION}/cves/2026/{number[:-3]}xxx/{r["id"]}.json'
    p=cache/(r['id']+'.json')
    if not p.exists():
        out=subprocess.run(['curl','--fail','--silent','--show-error','--location','--connect-timeout','15','--max-time','45',url],capture_output=True)
        if out.returncode:return {'id':r['id'],'status':'SOURCE_UNAVAILABLE','source_url':url}
        assert len(out.stdout)<1_000_000
        data=json.loads(out.stdout);assert data['cveMetadata']['cveId']==r['id'];p.write_bytes(out.stdout)
    data=json.loads(p.read_text());cna=data['containers']['cna']
    labels=sorted({d['cweId'].upper() for t in cna.get('problemTypes',[]) for d in t.get('descriptions',[])
                   if re.fullmatch(r'CWE-\d+',d.get('cweId',''),re.I)})
    descriptions=[d['value'].strip() for d in cna.get('descriptions',[]) if d.get('lang','').lower().startswith('en')]
    description=descriptions[0] if len(descriptions)==1 else ''
    reasons=[]
    if labels!=[r['label']]:reasons.append('CNA_NVD_LABEL_NOT_UNIQUE_MATCH')
    if data['cveMetadata'].get('state')!='PUBLISHED':reasons.append('CNA_NOT_PUBLISHED')
    if not 80<=len(description)<=2000:reasons.append('CNA_DESCRIPTION_LENGTH_OR_MULTIPLE')
    if re.search(r'(?i)\bCWE[-‑ ]?\d+\b',description):reasons.append('CNA_DESCRIPTION_LABEL_LEAK')
    if '<' in description or '>' in description:reasons.append('HTML_OR_CODE_NEEDS_REVIEW')
    products=[{'vendor':p.get('vendor'),'product':p.get('product'),'packageName':p.get('packageName')}
              for p in cna.get('affected',[])]
    return {'id':r['id'],'label':r['label'],'group_id':groups[r['id']],
            'description':description,'nvd_description':r['description'],
            'source_cna_labels':labels,'source_url':url,
            'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'products':products,'references':sorted({x['url'] for x in cna.get('references',[]) if 'url' in x}),
            'structural_issues':reasons,'status':'HOLD_SEMANTIC_PILOT_REVIEW','training_eligible':False}
with ThreadPoolExecutor(4) as pool:records=list(pool.map(fetch,selected))
out=ROOT/'data/raw/cti-source-pilot';out.mkdir(parents=True,exist_ok=True)
text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records)
(out/'source-candidates.jsonl').write_text(text)
report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'SOURCE_STRUCTURAL_SCREEN_ONLY',
        'cvelist_revision':REVISION,'requested':len(records),'fetched':sum(r['status']!='SOURCE_UNAVAILABLE' for r in records),
        'structural_matches':sum(r.get('structural_issues')==[] for r in records),
        'selected_per_class':dict(Counter(r['label'] for r in selected)),
        'matched_per_class':dict(Counter(r['label'] for r in records if r.get('structural_issues')==[])),
        'excluded_prior_debug_group_records':len(exposed),'selection_rule':'Fixed hash order; at most16 per class, unique existing heuristic group, no prior debug-group exposure',
        'candidate_sha256':hashlib.sha256(text.encode()).hexdigest(),'official_test_rows':0,'training_approved':0,
        'limitations':['CNA/NVD agreement is source consistency, not independent expert gold.',
                       'Selected eight classes are a narrow pilot, not representative CTI-Bench data.',
                       'No split is frozen and no source record is training-approved by this fetch.']}
(ROOT/'docs/verification/cti-source-pilot-fetch.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
