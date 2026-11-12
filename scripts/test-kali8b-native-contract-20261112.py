#!/usr/bin/env python3
"""Contract tests only: mocked numerical results are never study receipts."""
import importlib.util,json,pathlib,sys,tempfile,threading,time,unittest.mock as mock
import kali8b_native_bridge as b
from kali8b_native_client import main as client_main

def main():
 with tempfile.TemporaryDirectory(prefix='kali8b-contract-') as tmp:
  root=pathlib.Path(tmp);(root/'task').mkdir();manifest=root/'task/training_manifest.json';manifest.write_text('{}\n')
  class Driver:
   OUT=root
   valid_setup=True;valid_worker=True
   def collect_journal(self):return {'run_id':'MOCK_ONLY','actions':[{'target':'search_1/setup_1','output':{'failed':not self.valid_setup}}],'started_actions':['search_1/complete_worker_1/worker_1'] if self.valid_worker else []}
  d=Driver();baseline={'candidate_id':'E0','score':0,'pointer':{'candidate_id':'E0','optimizer_steps':0}}
  with mock.patch.object(b,'S',root),mock.patch.object(b,'freeze_baseline',return_value=baseline):
   broker=b.Broker(d)
   def rejects(req):
    try:broker.call(req)
    except (AssertionError,ValueError,KeyError):return
    raise AssertionError('Unsafe request accepted: '+str(req))
   request={'action':'submit','candidate_id':'P13','manifest_sha256':b.sha(manifest)}
   rejects({**request,'candidate_id':'P15'});rejects({**request,'manifest_sha256':'0'*64});rejects({'action':'status','candidate_id':'P13'});rejects({'action':'score','pointer':{'candidate_id':'P13'}})
   d.valid_setup=False;rejects(request);d.valid_setup=True;d.valid_worker=False;rejects(request);d.valid_worker=True
   calls=[];ready=threading.Event();release=threading.Event()
   def fake_train(cid):
    calls.append(cid);ready.set();release.wait(3)
    with broker.lock:broker.states[cid]={'status':'REAL_GPU_TRAINING_COMPLETE','candidate_id':cid};broker.current=None
   with mock.patch.object(broker,'train',side_effect=fake_train):
    assert broker.call(request)['status']=='SUBMITTED';assert ready.wait(2);rejects(request);rejects({**request,'candidate_id':'P14'});release.set();broker.threads[0].join(3);assert calls==['P13'];rejects(request)
   # The native client may write artifacts only for verified, completed updates.
   sys.path.insert(0,str(pathlib.Path(__file__).parent));import kali8b_native_client as client
   for response in [{'status':'IN_PROGRESS'},{'status':'REAL_GPU_TRAINING_COMPLETE','training_receipt':{'optimizer_steps':0,'nonzero_gradient_steps':0,'changed_tensors':0,'adapter_reload_max_logit_delta':0}}]:
    with mock.patch.object(client,'call',return_value=response),mock.patch.object(sys,'argv',['client','finalize','--candidate','P13']):
     try:client_main()
     except (AssertionError,KeyError):pass
     else:raise AssertionError('Client accepted incomplete or zero-step training')
  print(json.dumps({'status':'PASS_NATIVE_CONTRACT_TESTS','scope':'Mocked control flow only;no model scores,optimizer updates,or study artifacts generated','checks':['recipe allowlist','manifest hash','native Setup gate','active Worker gate','single-GPU concurrency','duplicate denial','certified-pointer scoring','incomplete/zero-step finalize denied']}))
if __name__=='__main__':main()
