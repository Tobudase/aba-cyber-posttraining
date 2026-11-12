#!/usr/bin/env python3
import argparse,json
from kali8b_study_jobs import submit,watch
p=argparse.ArgumentParser();p.add_argument('arm',choices=['P11','P12','P13','P14']);p.add_argument('--dry-run',action='store_true');p.add_argument('--watch',action='store_true');a=p.parse_args()
print(json.dumps(submit(a.arm,dry=a.dry_run)),flush=True)
if a.watch and not a.dry_run:
 r=watch(a.arm);raise SystemExit(0 if r['status']=='COLLECTED' else 1)
