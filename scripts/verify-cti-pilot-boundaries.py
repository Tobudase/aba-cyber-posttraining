#!/usr/bin/env python3
"""Exercise leakage/provenance guards with deliberately invalid temporary copies."""
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
from cti_pilot_data import ROOT,load_pilot,sha

manifest,rows=load_pilot()
checks={'valid_frozen_pilot_loads':True}
def rejected_case(name,mutation,refresh_hash=True):
    with tempfile.TemporaryDirectory(prefix='cti-pilot-guard-') as d:
        root=Path(d);(root/'data/manifests').mkdir(parents=True)
        m=json.loads(json.dumps(manifest));local=json.loads(json.dumps(rows))
        mutation(m,local)
        for s in ['train','dev']:
            p=root/m['artifacts'][s]['path'];p.parent.mkdir(parents=True,exist_ok=True)
            b=''.join(json.dumps(r)+'\n' for r in local[s]).encode();p.write_bytes(b)
            if refresh_hash:
                m['artifacts'][s]['sha256']=sha(b);m['artifacts'][s]['rows']=len(local[s])
        (root/'data/manifests/cti-source-pilot-v1.json').write_text(json.dumps(m))
        try: load_pilot(root)
        except ValueError: checks[name]=True
        else: raise AssertionError('Guard did not reject: '+name)

rejected_case('changed_content_without_new_hash_rejected',lambda m,r:r['train'][0].update(description='tampered'),False)
rejected_case('official_benchmark_record_rejected',lambda m,r:r['train'][0].update(official_benchmark=True))
rejected_case('held_row_rejected',lambda m,r:r['train'][0].update(training_eligible=False))
rejected_case('shared_train_dev_group_rejected',lambda m,r:r['dev'][0].update(group_id=r['train'][0]['group_id']))
rejected_case('shared_train_dev_description_rejected',lambda m,r:r['dev'][0].update(description=r['train'][0]['description']))
report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASSED','checks':checks,
        'count':len(checks),'scope':'External pilot data boundaries only; not official-test execution'}
(ROOT/'docs/verification/cti-pilot-boundary-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
