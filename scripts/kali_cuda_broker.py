#!/usr/bin/env python3
"""Loopback-only, bounded bridge: fixed TRAIN job and aggregate-only evaluation.

No Kubernetes or model API credentials are served. Agent requests cannot supply
code, hyperparameters, paths, dataset rows or raw development responses.
"""
import argparse,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from kali_cuda_jobs import ROOT,canonical,sha,frozen,execute,verified_receipt
from benchkit import write_json

PORT=18741
class Broker:
 def __init__(self):
  self.protocol,self.inputs=frozen();self.lock=threading.Lock();self.audit=ROOT/'.tools/kali-cuda-broker-audit.jsonl'
 def event(self,action,status):
  with self.audit.open('a') as f:f.write(json.dumps({'action':action,'status':status,'protocol_sha256':sha(canonical(self.protocol))})+'\n')
 def call(self,request):
  if set(request)!={'action'} or request['action'] not in ['health','train','baseline_score','candidate_score']:raise ValueError('Only fixed allowlisted actions permitted')
  action=request['action']
  if action=='health':return {'status':'READY','protocol_sha256':sha(canonical(self.protocol)),'search_enabled':False,'max_ABA_candidates':1}
  with self.lock:
   self.event(action,'START')
   if action=='train':
    receipt=execute('E2','train')
    result={'pointer':{'schema':'kali.cuda.pointer.v1','run_id':'E2','protocol_sha256':sha(canonical(self.protocol)),'adapter_sha256':receipt['adapter_sha256']},'training_receipt':receipt}
   else:
    run='E0' if action=='baseline_score' else 'E2'
    if run=='E2':execute(run,'infer')
    directory=ROOT/'docs/verification/kali-cuda-cycle-v1'/run/'infer'
    receipt=verified_receipt(directory,self.protocol);scores=json.loads((directory/'scores.json').read_text())
    if receipt['status']!='COMPLETE' or receipt['protocol_sha256']!=sha(canonical(self.protocol)):raise ValueError('Verified evaluation required')
    sets=scores['sets'];d=sets['domain'];r=sets['retention']
    gate=True
    if run=='E2':
     base=json.loads((ROOT/'docs/verification/kali-cuda-cycle-v1/E0/infer/scores.json').read_text())['sets']
     gate=(d['summary']['exact_match']>base['domain']['summary']['exact_match'] and d['correct']>base['domain']['correct'] and d['summary']['total_score']>=base['domain']['summary']['total_score'] and r['correct']>=base['retention']['correct'] and receipt['truncated_rows']==0 and all(v['complete_XML_rows']==v['rows'] and v['summary']['runtime_failed_rows']==0 for v in sets.values()))
    result={'score':0.0 if run=='E0' else (1.0 if gate else -1.0),
      'components':{'domain_native_exact':d['summary']['exact_match'],'domain_strict':d['summary']['strict_option_value_correct'],'domain_total':d['summary']['total_score'],'retention_strict':r['summary']['strict_option_value_correct'],'truncated_rows':receipt['truncated_rows'],'official_test_rows':0,'confirmation_rows':0},
      'receipt_sha256':sha((directory/'receipt.json').read_bytes()),'protocol_sha256':sha(canonical(self.protocol)),
      'adoption_gate_passed':bool(run=='E2' and gate)}
    if run=='E2':result['adapter_sha256']=json.loads((directory.parent/'train/receipt.json').read_text())['adapter_sha256']
   self.event(action,'COMPLETE');return result

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  if self.path!='/v1/frozen':self.send_error(404);return
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=256:raise ValueError('Invalid request size')
   result=self.server.broker.call(json.loads(self.rfile.read(length)));code=200
  except Exception as exc:result={'error':type(exc).__name__,'detail':str(exc)[:200]};code=400
  raw=json.dumps(result).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=PORT);a=parser.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.broker=Broker();print('LOOPBACK_BROKER_READY',flush=True);server.serve_forever()
