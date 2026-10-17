#!/usr/bin/env python3
"""Compare a held spot-check's NVD labels with pinned public CNA records."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
cache=ROOT/'.tools/cti-review/cna'
cache.mkdir(parents=True,exist_ok=True)
def fetch(url):
    return subprocess.check_output(['curl','--fail','--silent','--show-error','--location','--max-time','45',url],stderr=subprocess.PIPE)
commit=json.loads(fetch('https://api.github.com/repos/CVEProject/cvelistV5/commits/main'))['sha']
assert re.fullmatch(r'[a-f0-9]{40}',commit)
sample=json.loads((ROOT/'docs/verification/cti-hosted-check-2/result.json').read_text())
def audit(row):
    identifier=row['id']
    match=re.fullmatch(r'CVE-(2026)-(\d{4,})',identifier)
    assert match
    number=match[2]
    path=f'cves/2026/{number[:-3]}xxx/{identifier}.json'
    url=f'https://raw.githubusercontent.com/CVEProject/cvelistV5/{commit}/{path}'
    try:
        raw=fetch(url);data=json.loads(raw)
        assert data['cveMetadata']['cveId']==identifier
        (cache/f'{identifier}.json').write_bytes(raw)
        labels=sorted({d['cweId'].upper() for p in data.get('containers',{}).get('cna',{}).get('problemTypes',[])
                       for d in p.get('descriptions',[]) if re.fullmatch(r'CWE-\d+',d.get('cweId',''),re.I)})
        return {'id':identifier,'nvd_label':row['label'],'cna_cwe_labels':labels,
                'nvd_label_in_cna':row['label'] in labels,'source_url':url,
                'source_sha256':hashlib.sha256(raw).hexdigest(),'status':'FETCHED'}
    except (subprocess.CalledProcessError,ValueError,KeyError,AssertionError):
        return {'id':identifier,'status':'SOURCE_NOT_VERIFIED','source_url':url}
with ThreadPoolExecutor(4) as pool:
    results=list(pool.map(audit,sample['records']))
report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'SOURCE_LABEL_COMPARISON_ONLY_ALL_DATA_HELD','cvelist_revision':commit,
        'requested':len(results),'fetched':sum(r['status']=='FETCHED' for r in results),
        'with_numeric_cna_cwe':sum(bool(r.get('cna_cwe_labels')) for r in results),
        'nvd_label_in_cna':sum(r.get('nvd_label_in_cna',False) for r in results),
        'records':results,'training_approved':0,'official_test_rows':0,
        'limitations':['NVD and CNA labels can share the same original assertion; agreement is not independent semantic validation.',
                       'ADP labels are not substituted for missing CNA CWE labels.',
                       'Missing/mismatched source labels remain review items; no labels are silently rewritten.']}
(ROOT/'docs/verification/cti-cna-label-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','cvelist_revision','requested','fetched','with_numeric_cna_cwe','nvd_label_in_cna','training_approved']}))
