"""Bounded successor for the active study; no native restart or automatic publish."""
import datetime,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/benchkit/kali-qwen-aba-validation-2026-11-15'
def record(status,**extra):
 p=DATA/'successor-status.json';p.write_text(json.dumps({'status':status,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),**extra},indent=2)+'\n')
def main():
 subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);record('WAITING_EXISTING_NATIVE_RUN_NO_RESTART');until=time.monotonic()+14400
 while time.monotonic()<until:
  h=json.loads((DATA/'native-controller/host-private.json').read_text())
  if h['status']=='FAILED':raise RuntimeError('Existing native run failed;preserve journal and real backend artifacts')
  if h.get('native_completed') and h.get('cleanup_pending') is False:break
  time.sleep(20)
 else:raise TimeoutError('Existing native run not complete in bounded successor wait')
 stages=[('EXPORT_VERIFIED_WEIGHTS','export_kali_qwen_aba_20261115.py',sys.executable),('SUPPLEMENTAL_V9_DEV_REVIEW','kali_qwen_supplement_cpu_20261115.py',sys.executable),('FROZEN_CONFIRM384','kali_qwen_confirmation_20261115.py',sys.executable),('VERIFY_PRIMARY_AND_PLOT','finalize_kali_qwen_aba_20261115.py',str(ROOT/'.tools/results-plot-venv/bin/python')),('ADD_CONFIRMATION_REPORT','add_kali_qwen_confirmation_report_20261115.py',str(ROOT/'.tools/results-plot-venv/bin/python'))]
 for status,name,python in stages:
  record(status);print('SUCCESSOR_STAGE '+status,flush=True);env=os.environ.copy();env['MPLCONFIGDIR']=str(ROOT/'.tools/matplotlib-cache');subprocess.run([python,str(ROOT/'scripts'/name)],check=True,env=env)
 record('LOCAL_REPORTS_VERIFIED_AWAIT_VISUAL_QA_AND_GITHUB');print('SUCCESSOR_LOCAL_REPORTS_READY',flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:record('FAILED_PRESERVED',error_type=type(e).__name__,error=str(e)[:300]);raise
