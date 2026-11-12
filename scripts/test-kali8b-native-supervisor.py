#!/usr/bin/env python3
"""Regressions for SSH disconnects, secret delivery and mailbox idempotence."""
import io,json,pathlib,subprocess,sys,tempfile,types,unittest.mock as mock
import kali8b_native_daemon as daemon
import kali8b_native_supervisor as supervisor
import kali8b_native_bridge as bridge
def result(stdout='',returncode=0):return types.SimpleNamespace(stdout=stdout,stderr='',returncode=returncode)
def main():
 with tempfile.TemporaryDirectory(prefix='kali8b-supervisor-test-') as tmp:
  root=pathlib.Path(tmp);calls=[];records=[];count=0
  class Driver:
   ROOT=pathlib.Path(__file__).resolve().parents[1];REMOTE='/mnt/aba-scratch/study';OUT=root
   def save(self,r):records.append(dict(r))
   def ssh(self,command,payload=None,**kwargs):
    nonlocal count
    calls.append((command,payload))
    if 'unit_state' in command:
     count+=1
     if count==1:raise subprocess.TimeoutExpired('MOCK_SSH_RESET',1)
     return result(json.dumps({'exit':None if count==2 else {'returncode':0},'unit_state':'active' if count==2 else 'inactive','credential_source_removed':True,'supervisor_error':None}))
    if 'systemd-run' in command:return result(json.dumps({'returncode':0,'stderr':''}))
    return result()
  with mock.patch.object(daemon.time,'sleep',return_value=None):state=daemon.start_and_wait(Driver(),'MOCK_ONLY_NOT_A_KEY',{})
  assert state['exit']['returncode']==0 and any(r.get('transport_state')=='RECONNECTING_WITHOUT_CANCELLING_NATIVE' for r in records);assert all('MOCK_ONLY_NOT_A_KEY' not in command for command,_ in calls)
  credential=root/'.nrp-runtime-key-private';credential.write_text('MOCK_ONLY_NOT_A_KEY');(root/'config.json').write_text(json.dumps({'llm':{'default':{'model':'MOCK_CONTROLLER'}}}));envs=[]
  fake_transport=types.SimpleNamespace(server=lambda _:types.SimpleNamespace(serve_forever=lambda:None));fake_mailbox=types.SimpleNamespace(serve=lambda:None)
  def fake_run(argv,**kwargs):envs.append(kwargs['env']);return result(returncode=0)
  with mock.patch.object(supervisor,'ROOT',root),mock.patch.object(sys,'stdin',io.StringIO('MOCK_ONLY_NOT_A_KEY')),mock.patch.dict(sys.modules,{'transport':fake_transport,'mailbox_server':fake_mailbox}),mock.patch.object(supervisor.subprocess,'run',side_effect=fake_run):supervisor.main()
  assert not credential.exists() and json.loads((root/'exit.json').read_text())['returncode']==0;assert envs[0]['AIBUILDAI_API_KEY']=='MOCK_ONLY_NOT_A_KEY';assert envs[0]['AIBUILDAI_SUBAGENT_MODEL']=='MOCK_CONTROLLER'
  class Stop:
   stopped=False
   def is_set(self):return self.stopped
   def wait(self,_):pass
   def set(self):self.stopped=True
  stop=Stop();dispatches=[];writes=0
  class FakeBroker:
   def __init__(self,_):self.current=None;self.threads=[];self.started=[];self.states={}
   def call(self,req):dispatches.append(req);return {'status':'MOCK_SUBMITTED'}
  class MailDriver:
   OUT=root
   def ssh(self,command,payload=None,**kwargs):
    nonlocal writes
    if '*.request.json' in command:return result(json.dumps({'request.request.json':json.dumps({'action':'MOCK_SUBMIT'})}))
    writes+=1
    if writes==1:return result(returncode=1)
    stop.set();return result()
  with mock.patch.object(bridge,'Broker',FakeBroker):bridge.bridge(MailDriver(),stop)
  assert len(dispatches)==1 and writes==2,'Lost response delivery must not cause a second training dispatch'
 print(json.dumps({'status':'PASS_DETACHED_CONTROLLER_REGRESSIONS','checks':['SSH loss reconnects without cancelling native','credential only in stdin payload,not command','credential source removed by supervisor','exit receipt survives service completion','mailbox retries do not redispatch'],'scope':'Mocked transport/processes only;no model call,GPU allocation or native benchmark result'}))
if __name__=='__main__':main()
