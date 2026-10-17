#!/usr/bin/env python3
"""Grade external pilot predictions using the separately pinned FAITH runtime."""
import argparse
import json
from pathlib import Path
from cti_pilot_data import ROOT,load_pilot
from cti_native_metrics import final_answer,grade,json_default

p=argparse.ArgumentParser(description=__doc__);p.add_argument('result',type=Path);args=p.parse_args()
report=json.loads(args.result.read_text());manifest,data=load_pilot()
assert report['status']=='COMPLETED' and report['contract']['official_test_rows']==0
assert report['contract']['data']['dev']==manifest['artifacts']['dev']['sha256']
assert len(report['records'])==len(data['dev'])
expected={r['id']:r['label'] for r in data['dev']}
assert {r['id']:r['label'] for r in report['records']}==expected
assert len({r['id'] for r in report['records']})==len(data['dev'])
rows=[dict(r,answer_text=final_answer(r['output_text'],reasoning_prefilled=False)) for r in report['records']]
metrics,details=grade(rows)
output={'scope':'EXTERNAL_SOURCE_SILVER_DEV_LABEL_AGREEMENT_NOT_BENCHMARK_SCORE',
        'native_metrics':metrics,'records':details,'official_test_rows':0,
        'attempted':len(rows),'truncated':sum(r['truncated'] for r in rows)}
dest=args.result.with_name(args.result.stem+'-graded.json');dest.write_text(json.dumps(output,indent=2,default=json_default)+'\n')
print(json.dumps(output,indent=2,default=json_default))
