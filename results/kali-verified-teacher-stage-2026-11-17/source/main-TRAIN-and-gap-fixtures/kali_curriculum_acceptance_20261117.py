"""Host-side command extraction and finite functional checking; raw data private."""
import argparse,base64,gzip,hashlib,json,re,time
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT as JOBS,submit,poll,cleanup
from prepare_kali_verified_curriculum_20261117 import OUT
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def command(record):
    if record.get('finish_reason')!='stop':return None
    m=record.get('message') or {};text=m.get('content',record.get('content',''))
    matches=re.findall(r'<output>\s*([\s\S]*?)\s*</output>',text)
    if len(matches)!=1 or text.count('<output>')!=1 or text.count('</output>')!=1 or not matches[0].strip():return None
    return matches[0].strip()
def collect_commands():
    commands={}
    for condition in ['U','H','H2']:
        for repeat in range(3):
            for f in (OUT/('teacher-'+condition+'-repeat'+str(repeat))).glob('*.json'):
                r=json.loads(f.read_text());cmd=command(r)
                if cmd:commands.setdefault(r['id'],{})['teacher_'+condition+'_'+str(repeat)]=cmd
    for mode in ['thinking','nonthinking']:
        f=OUT/('student-'+mode+'.json')
        if f.exists():
            for r in json.loads(f.read_text())['rows']:
                cmd=command(r)
                if cmd:commands.setdefault(r['id'],{})['student_'+mode]=cmd
    for mode in ['thinking','nonthinking']:
        for repeat in [1,2]:
            f=OUT/('repeated-'+mode+'-repeat'+str(repeat)+'.json')
            if f.exists():
                for r in json.loads(f.read_text())['rows']:
                    cmd=command(r)
                    if cmd:commands.setdefault(r['id'],{})['student_'+mode+'_r'+str(repeat)]=cmd
    allowed={r['id'] for r in json.loads((OUT/'candidates-r2-private.json').read_text())}
    return {k:v for k,v in commands.items() if k in allowed}
def launch(tag):
    worker=ROOT/'scripts/kali_verified_curriculum_worker_20261117.py';src=ROOT/'data/benchkit/kali-independent-teacher-2026-11-17/source-evidence/galleta.c';commands=json.dumps(collect_commands(),indent=2)+'\n';name='miw113-kali-curriculum-'+tag+'-1117'
    freeze={'tag':tag,'worker_sha256':sha(worker),'candidates_sha256':sha(OUT/'candidates-r2-private.json'),'commands_sha256':hashlib.sha256(commands.encode()).hexdigest(),'role_counts':{role:sum(role in rr for rr in json.loads(commands).values()) for role in sorted({k for rr in json.loads(commands).values() for k in rr})},'trained':False}
    (OUT/(tag+'-freeze.json')).write_text(json.dumps(freeze,indent=2)+'\n');(OUT/(tag+'-commands-private.json')).write_text(commands)
    return submit(name,{'worker.py':worker.read_text(),'candidates.json':(OUT/'candidates-r2-private.json').read_text(),'commands.json':commands,'galleta.c':src.read_text(),'galleta.sha256':sha(src)},{'cpu':'2','memory':'4Gi','ephemeral-storage':'8Gi'},runtime=2700)
def watch(tag):
    name='miw113-kali-curriculum-'+tag+'-1117';until=time.monotonic()+4900;previous=None
    while time.monotonic()<until:
        r=poll(name);r.pop('log_tail',None)
        if r!=previous:print(json.dumps(r),flush=True);previous=r
        if r['status'] in ['SUCCEEDED','FAILED']:
            log=(JOBS/name/'worker.log').read_text();packed=[s.split('=',1)[1] for s in log.splitlines() if s.startswith('VERIFIED_CURRICULUM_ARTIFACT=')]
            if packed:
                data=json.loads(gzip.decompress(base64.b64decode(packed[-1],validate=True)));assert data['commands_sha256']==json.loads((OUT/(tag+'-freeze.json')).read_text())['commands_sha256'];(OUT/(tag+'-private.json')).write_text(json.dumps(data,indent=2)+'\n')
                print('RESULT_COLLECTED '+str(len(data['results'])),flush=True)
            if r['status']=='SUCCEEDED':assert packed,'Cannot discard uncollected successful results'
            cleanup(name);print('RESOURCES_CLEANED',flush=True);return
        time.sleep(45)
    raise TimeoutError('Bounded CPU acceptance monitor deadline')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['submit','watch']);p.add_argument('tag');a=p.parse_args();assert re.fullmatch('[a-z0-9-]{1,16}',a.tag)
    if a.action=='submit':print(json.dumps(launch(a.tag)))
    else:watch(a.tag)
