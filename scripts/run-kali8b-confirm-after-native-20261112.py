#!/usr/bin/env python3
"""Finite same-study continuation; no cluster resource while awaiting native ABA."""
import datetime,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];HOST=ROOT/'docs/verification/kali8b-native-v64-20261112/host-private.json';S=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12'
def verify_native_scores(study=S,native=None):
 study=pathlib.Path(study);native=pathlib.Path(native or ROOT/'docs/verification/kali8b-native-v64-20261112');assert not(study/'confirmation').exists()
 j=json.loads((native/'journal-private.json').read_text());selection=json.loads((study/'native-selection-private.json').read_text());assert j['head']['result']=='completed' and j['run_id']==selection['native_run_id'];seen={}
 for directory,files in j['scored_outputs'].items():
  pointer=json.loads(files['final_model/model.json']['text']);cid=pointer['candidate_id'];assert cid in ['P13','P14'] and cid not in seen
  receipt=json.loads((study/cid/'run/receipt-private.json').read_text());score=json.loads((study/cid/'run/scores-private.json').read_text());assert pointer['adapter_sha256']==receipt['adapter_sha256'] and receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==733
  matches=[a for a in j['actions'] if '/score_program_' in a['target'] and a['output'].get('output_dir')==directory];assert len(matches)==1;action=matches[0];assert action['output']['failed'] is False and action['output']['score']==score['ABA_score'];assert any(a['target']==action['target'] and a['return_code']==0 for a in j['program_attempts']);seen[cid]={'score':score['ABA_score'],'adapter_sha256':receipt['adapter_sha256']}
 assert set(seen)=={'P13','P14'},'Both candidates must actually pass native score programs in this recovery before confirmation'
 return {'status':'PASS_TWO_CURRENT_NATIVE_SCORE_PROGRAMS','native_run_id':j['run_id'],'candidate_ids':sorted(seen),'certified_scores':seen,'before_confirmation_created':True,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_calls':0,'official_TEST_rows':0}
def main():
 subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);until=time.monotonic()+18*3600;last=None
 while time.monotonic()<until:
  try:r=json.loads(HOST.read_text()) if HOST.exists() else {'status':'WAITING_NATIVE_CONTROLLER'}
  except json.JSONDecodeError:time.sleep(2);continue
  if r['status']!=last:print(json.dumps({'stage':'native','status':r['status']}),flush=True);last=r['status']
  if r['status']=='FAILED':raise SystemExit('Native stage failed; receipts preserved; sealed64 remains unqueried')
  if r['status']=='COMPLETE_VERIFIED_NATIVE_8B_STUDY':
   assert r['native_completed'] and not r['cleanup_errors']
   try:os.kill(r['local_controller_pid'],0)
   except ProcessLookupError:
    final=json.loads(HOST.read_text());assert final['status']=='COMPLETE_VERIFIED_NATIVE_8B_STUDY' and final['native_completed'] and not final['cleanup_errors'];break
   # COMPLETE is saved before the driver's finally cleanup. Wait for its
   # actual exit,then reread the final cleanup receipt before querying64.
   time.sleep(5);continue
  time.sleep(30)
 else:raise TimeoutError('Bounded stage continuation expired without new GPU allocation')
 assert not (S/'confirmation').exists(),'Do not re-query or overwrite a confirmation attempt'
 try:audit=verify_native_scores()
 except BaseException as e:
  (S/'native-score-audit-aggregate.json').write_text(json.dumps({'status':'FAILED_NATIVE_SCORE_AUDIT_NO_CONFIRMATION','error_type':type(e).__name__,'error':str(e)[:250]},indent=2)+'\n');raise
 (S/'native-score-audit-aggregate.json').write_text(json.dumps(audit,indent=2)+'\n')
 p=subprocess.run([sys.executable,str(ROOT/'scripts/run-kali8b-final64-20261112.py')],cwd=ROOT,timeout=21900)
 assert p.returncode==0,'Confirmation failed; inspect existing private output before any recovery'
 r=json.loads((S/'confirmation/host-private.json').read_text());assert r['status']=='COMPLETE' and not r['cleanup_errors'];print('STUDY_TRAIN_NATIVE_AND_CONFIRMATION_COMPLETE',flush=True)
if __name__=='__main__':main()
