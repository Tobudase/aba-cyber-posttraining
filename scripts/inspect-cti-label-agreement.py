#!/usr/bin/env python3
"""Annotate held-intake disagreements using CWE ancestry, without rescoring."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
taxonomy=ROOT/'.tools/cti-review/cwec_latest.xml.zip'
with zipfile.ZipFile(taxonomy) as z:
    name=next(x for x in z.namelist() if x.endswith('.xml'))
    xml=ET.fromstring(z.read(name))
ns={'c':'http://cwe.mitre.org/cwe-7'}
parents={}
for weak in xml.findall('c:Weaknesses/c:Weakness',ns):
    parents['CWE-'+weak.get('ID')]={f'CWE-{r.get("CWE_ID")}' for r in weak.findall('c:Related_Weaknesses/c:Related_Weakness',ns)
                                   if r.get('Nature')=='ChildOf' and r.get('View_ID')=='1000'}
def ancestors(label):
    seen=set();queue=list(parents.get(label,set()))
    while queue:
        item=queue.pop()
        if item in seen:continue
        seen.add(item);queue.extend(parents.get(item,set()))
    return seen
source=ROOT/'docs/verification/cti-hosted-check-2/result.json'
report=json.loads(source.read_text())
annotations=[]
for row in report['grading']:
    if row['strict_correct']:continue
    predicted,gold=row['prediction'],row['label']
    relation=('prediction_is_ancestor_of_source_label' if predicted in ancestors(gold) else
              'prediction_is_descendant_of_source_label' if gold in ancestors(predicted) else
              'no_direct_ancestry_in_view1000')
    annotations.append(dict(row,ontology_relation=relation))
output={'purpose':'REVIEW_HINTS_NO_METRIC_OR_LABEL_CHANGES','taxonomy_version':xml.get('Version'),
        'taxonomy_zip_sha256':hashlib.sha256(taxonomy.read_bytes()).hexdigest(),
        'source_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_label_agreement':report['all_requested_record_accuracy'],
        'disagreements':annotations,'labels_changed':0,
        'limitations':['Ancestry does not prove either label is correct.',
                       'Exact-match agreement remains the reported diagnostic; no post-hoc relaxed score.']}
(ROOT/'docs/verification/cti-external-disagreement-review.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({'disagreements':len(annotations),'ancestry_related':sum(r['ontology_relation']!='no_direct_ancestry_in_view1000' for r in annotations),'labels_changed':0}))
