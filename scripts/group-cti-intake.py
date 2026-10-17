#!/usr/bin/env python3
"""Conservative leakage-group hints and CWE validity checks, without approving data."""
from collections import Counter, defaultdict
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--week',action='store_true')
args=parser.parse_args()
cohort='cti-nvd-week' if args.week else 'cti-nvd'
source = ROOT/f'data/raw/{cohort}/candidates.jsonl'
rows = [json.loads(x) for x in source.read_text().splitlines()]
taxonomy = ROOT/'.tools/cti-review/cwec_latest.xml.zip'
with zipfile.ZipFile(taxonomy) as archive:
    members = [x for x in archive.infolist() if x.filename.endswith('.xml')]
    assert len(members)==1 and members[0].file_size < 30_000_000
    content = archive.read(members[0])
assert b'<!DOCTYPE' not in content and b'<!ENTITY' not in content
xml = ET.fromstring(content)
ns = {'c':'http://cwe.mitre.org/cwe-7'}
weaknesses = {f'CWE-{x.attrib["ID"]}':x for x in xml.findall('c:Weaknesses/c:Weakness',ns)}
other_entries = {f'CWE-{x.attrib["ID"]}':(kind,x) for kind,path in
                 [('Category','c:Categories/c:Category'),('View','c:Views/c:View')]
                 for x in xml.findall(path,ns)}
labels = {}
for label in sorted({r['label'] for r in rows}):
    element = weaknesses.get(label)
    if element is None:
        other=other_entries.get(label)
        labels[label]={'exists':other is not None,'entry_kind':other[0] if other else None,
                       'valid_weakness_target':False,
                       'status':other[1].get('Status') if other else None}
        continue
    mapping = element.find('c:Mapping_Notes/c:Usage',ns)
    labels[label]={'exists':True, 'entry_kind':'Weakness', 'valid_weakness_target':True,
                   'status':element.get('Status'),
                   'abstraction':element.get('Abstraction'),
                   'mapping_usage':mapping.text if mapping is not None else None}

parent = list(range(len(rows)))
def root(i):
    while parent[i]!=i:
        parent[i]=parent[parent[i]]
        i=parent[i]
    return i
def union(i,j):
    parent[root(j)]=root(i)
def normalize(url):
    part=urlsplit(url)
    # Query parameters may identify a distinct advisory (e.g. HPE docId).
    # Preserve them rather than collapsing unrelated advisories onto one path.
    return urlunsplit((part.scheme.lower(),part.netloc.lower(),part.path.rstrip('/'),part.query,''))
def keys(row):
    result=set()
    for url in row['reference_urls']:
        clean=normalize(url)
        part=urlsplit(clean)
        segments=[x for x in part.path.split('/') if x]
        if len(segments)>=2:
            result.add('reference:'+clean)
        if part.netloc in {'github.com','www.github.com'} and len(segments)>=2:
            result.add('repository:'+('/'.join(segments[:2])).lower())
        if part.netloc=='plugins.trac.wordpress.org' and len(segments)>=2 and segments[0]=='browser':
            result.add('wordpress-plugin:'+segments[1].lower())
        for alias in re.findall(r'(?i)GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}',url):
            result.add('advisory:'+alias.upper())
    return result
record_keys=[keys(r) for r in rows]
def shingles(text):
    tokens=re.findall(r'[a-z]+',text.lower())
    return {tuple(tokens[i:i+5]) for i in range(max(0,len(tokens)-4))}
grams=[shingles(r['description']) for r in rows]
edges=[]
for i,j in itertools.combinations(range(len(rows)),2):
    shared=sorted(record_keys[i]&record_keys[j])
    common=grams[i]&grams[j]
    overlap=len(common)/max(1,min(len(grams[i]),len(grams[j])))
    if shared or (len(common)>=12 and overlap>=0.65):
        union(i,j)
        edges.append({'a':rows[i]['id'],'b':rows[j]['id'],
                      'shared_keys':shared,'text_shingle_overlap':round(overlap,4)})
clusters=defaultdict(list)
for i,row in enumerate(rows): clusters[root(i)].append(row)
groups=[]
for members in sorted(clusters.values(),key=lambda g:sorted(r['id'] for r in g)):
    identifiers=sorted(r['id'] for r in members)
    groups.append({'group_id':'cti-'+hashlib.sha256('\n'.join(identifiers).encode()).hexdigest()[:12],
                   'ids':identifiers,'labels':dict(Counter(r['label'] for r in members)),
                   'training_eligible':False})
report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'GROUPING_HINTS_ONLY_ALL_DATA_HELD',
        'records':len(rows),'groups':len(groups),
        'non_singleton_groups':sum(len(g['ids'])>1 for g in groups),
        'largest_group':max(map(lambda g:len(g['ids']),groups),default=0),
        'candidate_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'taxonomy':{'source_url':'https://cwe.mitre.org/data/xml/cwec_latest.xml.zip',
                    'version':xml.get('Version'),'date':xml.get('Date'),
                    'zip_sha256':hashlib.sha256(taxonomy.read_bytes()).hexdigest(),
                    'terms_url':'https://cwe.mitre.org/about/termsofuse.html'},
        'label_validity':labels,'group_members':groups,'merge_edges':edges,
        'training_approved':0,'split_frozen':False,'official_test_rows':0,
        'limitations':['Shared repositories can merge unrelated vulnerabilities conservatively.',
                       'Near-duplicate text is a heuristic, not a proven common vulnerability.',
                       'Missing aliases, project identities and patch equivalences need independent review.',
                       'Valid CWE identifiers do not establish correct labels for descriptions.',
                       'No training/dev split should separate members of a reviewed group.']}
dest=ROOT/('docs/verification/cti-week-intake-groups.json' if args.week else 'docs/verification/cti-intake-groups.json')
dest.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','records','groups','non_singleton_groups','largest_group','taxonomy','training_approved']},indent=2))
