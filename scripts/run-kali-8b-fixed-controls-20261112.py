#!/usr/bin/env python3
"""Run the two preregistered fixed controls serially, with no idle GPU hold."""
import json,os,subprocess
from kali8b_study_jobs import S,submit,watch
awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for cid in ['P11','P12']:
 if not (S/cid/'run').exists():print(json.dumps(submit(cid)),flush=True)
 r=watch(cid)
 if r['status']!='COLLECTED':raise SystemExit('Control failed: '+cid+'; receipts preserved; no later arm submitted')
 print(json.dumps({'status':'FIXED_CONTROL_COMPLETE','arm':cid,'native_delta':r['native_delta'],'passes_all_gates':r['passes_all_gates']}),flush=True)
print('BOTH_FIXED_CONTROLS_COMPLETE',flush=True)
