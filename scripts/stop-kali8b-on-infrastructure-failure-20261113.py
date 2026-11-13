#!/usr/bin/env python3
"""One-shot fail-fast for this exact native attempt;never interrupt a scored arm.
The frozen study needs all four arms. If a real infrastructure/collection failure
makes one arm FAILED,stop the owning controller through its normal cleanup so
later work cannot consume a GPU for an uncompletable attempt. Scores of -1 are
COLLECTED,not failures,and never trigger this guard.
"""
import argparse,datetime,json,os,pathlib,shlex,signal,subprocess,time
R=pathlib.Path(__file__).resolve().parents[1];O=R/'docs/verification/kali8b-native-v64-20261112';S=R/'data/benchkit/kali-8b-verified64-study-2026-11-12';RUN=None;report=O/'infrastructure-failfast-private.json'
def save(status,**kw):report.write_text(json.dumps({'status':status,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'expected_run_id':RUN,**kw},indent=2)+'\n')
def main():
 global RUN
 parser=argparse.ArgumentParser();parser.add_argument('--expected-run-id',required=True);args=parser.parse_args();RUN=args.expected_run_id;assert len(RUN)==32 and all(c in '0123456789abcdef' for c in RUN)
 until=time.monotonic()+18*3600;save('WATCHING_INFRASTRUCTURE_ONLY')
 while time.monotonic()<until:
  try:
   h=json.loads((O/'host-private.json').read_text());j=json.loads((O/'journal-private.json').read_text())
   if j['run_id']!=RUN:save('SUPERSEDED_NO_SIGNAL');return
   if h['status'] in ['FAILED','COMPLETE_VERIFIED_NATIVE_8B_STUDY']:save('CONTROLLER_ENDED_NO_SIGNAL',controller_status=h['status']);return
   for cid in ['P13','P14']:
    p=S/cid/'run/host-private.json'
    if not p.exists():continue
    arm=json.loads(p.read_text())
    if arm['status']!='FAILED':continue
    pid=h['local_controller_pid'];args=shlex.split(subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True,check=True).stdout);assert len(args)>=2
    script=pathlib.Path(args[1])
    if not script.is_absolute():
     cwd=subprocess.run(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True,check=True).stdout;dirs=[pathlib.Path(v[1:]).resolve() for v in cwd.splitlines() if v.startswith('n')];assert dirs==[R.resolve()];script=dirs[0]/script
    assert script.resolve()==(R/'scripts/run-kali8b-native-study-20261112.py').resolve()
    save('SIGNALLED_INFRASTRUCTURE_FAILURE_NORMAL_CLEANUP',candidate_id=cid,error=arm.get('error'),controller_pid=pid);os.kill(pid,signal.SIGINT);return
  except (json.JSONDecodeError,FileNotFoundError):pass
  time.sleep(5)
 save('FINITE_GUARD_EXPIRED_NO_SIGNAL')
if __name__=='__main__':main()
