"""Run authored replay fixtures only in fresh temporary directories, no shell."""
import json,os,platform,subprocess,tempfile
from pathlib import Path
ALLOWED={'basename','dirname','cut','paste','seq','expr','expand','fold','uniq','comm','join','sort','printf','factor'}
def verify(rows):
 results=[]
 for row in rows:
  spec=row['fixture'];argv=spec['argv']
  if argv[0] not in ALLOWED or row['split']!='train' or not row['self_authored']:raise ValueError('Unexpected fixture')
  with tempfile.TemporaryDirectory() as tmp:
   for name,text in spec['files'].items():
    if Path(name).name!=name:raise ValueError('Fixture path escapes directory')
    (Path(tmp)/name).write_text(text)
   if argv[0] not in {'basename','dirname'} and any(x.startswith('/') or '..' in x for x in argv[1:]):raise ValueError('Only fixture-relative paths')
   p=subprocess.run(argv,cwd=tmp,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'},capture_output=True,text=True,timeout=5)
   results.append({'id':row['id'],'passed':p.returncode==0 and p.stdout==spec['expected_stdout'],'returncode':p.returncode,'actual_stdout':p.stdout,'expected_stdout':spec['expected_stdout']})
 r={'status':'PASS' if all(x['passed'] for x in results) else 'FAILED','platform':platform.system(),'cases':len(results),'passed':sum(x['passed'] for x in results),'results':results,'scope':'Authored training fixtures only; no model/development command execution'}
 print('KALI_REPLAY_RESULT='+json.dumps(r),flush=True)
 if r['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
 import sys
 verify([json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines()])
