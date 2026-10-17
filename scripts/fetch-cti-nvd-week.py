#!/usr/bin/env python3
"""Fetch a bounded publication-week intake from the public NVD 2.0 API."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
cache=ROOT/'.tools/cti-review'
pages=[]
start=time.monotonic()
for offset in (0,2000):
    query=urlencode({'pubStartDate':'2026-10-01T00:00:00.000',
                     'pubEndDate':'2026-10-08T00:00:00.000',
                     'resultsPerPage':2000,'startIndex':offset})
    url='https://services.nvd.nist.gov/rest/json/cves/2.0?'+query
    target=cache/f'nvd-week-page-{offset}.json'
    if pages: time.sleep(6)
    subprocess.run(['curl','--fail','--silent','--show-error','--connect-timeout','20',
                    '--max-time','120','--max-filesize','16000000','--output',str(target),url],check=True)
    data=json.loads(target.read_text())
    assert data['startIndex']==offset and data['totalResults']<=4000
    pages.append({'source_url':url,'raw_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                  'data':data})
    print(json.dumps({'offset':offset,'records':len(data['vulnerabilities']),
                      'total':data['totalResults']}),flush=True)
    if offset+len(data['vulnerabilities'])>=data['totalResults']: break
records=[r for p in pages for r in p['data']['vulnerabilities']]
ids=[r['cve']['id'] for r in records]
assert len(ids)==len(set(ids)), 'Pagination changed; inspect raw pages, do not silently deduplicate'
assert len(records)==pages[0]['data']['totalResults']==pages[-1]['data']['totalResults']
raw=cache/'nvd-week-raw.json'
raw.write_text(json.dumps({'vulnerabilities':records,'totalResults':len(records)}))
report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'FETCHED',
        'source_url':'https://services.nvd.nist.gov/rest/json/cves/2.0',
        'publication_window':['2026-10-01T00:00:00.000','2026-10-08T00:00:00.000'],
        'pages':[{k:p[k] for k in ['source_url','raw_sha256']} for p in pages],
        'records':len(records),'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
        'elapsed_seconds':time.monotonic()-start,'official_test_rows':0,
        'training_approved':0,'snapshot_atomic':False,
        'attribution':'This product uses data from the NVD API but is not endorsed or certified by the NVD.'}
(ROOT/'docs/verification/cti-nvd-week-fetch.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'FETCHED','records':len(records)}))
