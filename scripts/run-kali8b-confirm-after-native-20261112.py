#!/usr/bin/env python3
"""Finite same-study continuation; no cluster resource while awaiting native ABA."""
import json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];HOST=ROOT/'docs/verification/kali8b-native-v64-20261112/host-private.json';S=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12'
def main():
 subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);until=time.monotonic()+12*3600;last=None
 while time.monotonic()<until:
  try:r=json.loads(HOST.read_text()) if HOST.exists() else {'status':'WAITING_NATIVE_CONTROLLER'}
  except json.JSONDecodeError:time.sleep(2);continue
  if r['status']!=last:print(json.dumps({'stage':'native','status':r['status']}),flush=True);last=r['status']
  if r['status']=='FAILED':raise SystemExit('Native stage failed; receipts preserved; sealed64 remains unqueried')
  if r['status']=='COMPLETE_VERIFIED_NATIVE_8B_STUDY':
   assert r['native_completed'] and not r['cleanup_errors'];break
  time.sleep(30)
 else:raise TimeoutError('Bounded stage continuation expired without new GPU allocation')
 assert not (S/'confirmation').exists(),'Do not re-query or overwrite a confirmation attempt'
 p=subprocess.run([sys.executable,str(ROOT/'scripts/run-kali8b-final64-20261112.py')],cwd=ROOT,timeout=21900)
 assert p.returncode==0,'Confirmation failed; inspect existing private output before any recovery'
 r=json.loads((S/'confirmation/host-private.json').read_text());assert r['status']=='COMPLETE' and not r['cleanup_errors'];print('STUDY_TRAIN_NATIVE_AND_CONFIRMATION_COMPLETE',flush=True)
if __name__=='__main__':main()
