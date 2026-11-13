"""Start once and reconnect to a bounded native controller without persistent SSH."""
import json,shlex,subprocess,time
from pathlib import Path
UNIT='kali8b-native-controller.service'
def safe_ssh(driver,command,**kwargs):
 try:return driver.ssh(command,**kwargs)
 except (subprocess.TimeoutExpired,OSError):return None
def start_and_wait(driver,token,record):
 remote=driver.REMOTE
 result=safe_ssh(driver,'sudo loginctl enable-linger fedora',timeout=45);assert result is not None and result.returncode==0,'Unable to enable bounded controller service'
 source=(driver.ROOT/'scripts/kali8b_native_supervisor.py').read_text();result=safe_ssh(driver,'cat > '+remote+'/native_supervisor.py',payload=source);assert result is not None and result.returncode==0
 keycode="import pathlib,sys,os;p=pathlib.Path('/mnt/aba-scratch/study/.nrp-runtime-key-private');assert not pathlib.Path('/mnt/aba-scratch/study/exit.json').exists();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);f=os.fdopen(fd,'w');f.write(sys.stdin.read());f.close()"
 result=safe_ssh(driver,'python3 -c '+shlex.quote(keycode),payload=token);assert result is not None and result.returncode==0,'Unable to deliver transient service credential'
 launch="""import os,subprocess,json
e=os.environ.copy();e.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
p=subprocess.run(['systemd-run','--user','--collect','--unit=kali8b-native-controller.service','--property=Delegate=yes','--property=RuntimeMaxSec=27090','--property=StandardInput=file:/mnt/aba-scratch/study/.nrp-runtime-key-private','--property=StandardOutput=append:/mnt/aba-scratch/study/supervisor-private.log','--property=StandardError=append:/mnt/aba-scratch/study/supervisor-private.log','/mnt/aba-scratch/conda/envs/manager/bin/python','/mnt/aba-scratch/study/native_supervisor.py'],env=e,capture_output=True,text=True)
print(json.dumps({'returncode':p.returncode,'stderr':p.stderr[-500:]}))
"""
 result=safe_ssh(driver,'python3 -c '+shlex.quote(launch))
 if result is not None and result.returncode==0:
  started=json.loads(result.stdout);assert started['returncode']==0,started['stderr']
 else:record['launch_ack_lost_check_existing_unit_without_resubmission']=True
 record.update(status='NATIVE_RUNNING',native_service=UNIT,transport='detached_systemd_with_reconnecting_SSH');driver.save(record);print('FORMAL_NATIVE_DAEMON_RUNNING',flush=True)
 status="""import os,pathlib,json,subprocess
r=pathlib.Path('/mnt/aba-scratch/study');e=os.environ.copy();e.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus');p=subprocess.run(['systemctl','--user','show','kali8b-native-controller.service','--property=ActiveState','--value'],capture_output=True,text=True,env=e)
print(json.dumps({'exit':json.loads((r/'exit.json').read_text()) if (r/'exit.json').exists() else None,'unit_state':p.stdout.strip(),'credential_source_removed':not (r/'.nrp-runtime-key-private').exists(),'native_log_tail':(r/'native.log').read_text(errors='replace')[-6000:] if (r/'native.log').exists() else None,'supervisor_error':json.loads((r/'supervisor-error-private.json').read_text()) if (r/'supervisor-error-private.json').exists() else None}))
"""
 until=time.monotonic()+27300;failures=0;inactive=0
 while time.monotonic()<until:
  response=safe_ssh(driver,'python3 -c '+shlex.quote(status),timeout=40)
  if response is None or response.returncode:
   failures+=1;record.update(SSH_reconnect_failures=failures,transport_state='RECONNECTING_WITHOUT_CANCELLING_NATIVE');driver.save(record);time.sleep(15);continue
  state=json.loads(response.stdout.replace(token,'[REDACTED]'));record.update(transport_state='CONNECTED',credential_source_removed=state['credential_source_removed'],native_unit_state=state['unit_state']);driver.save(record)
  if state['exit'] is not None:
   (driver.OUT/'detached-supervisor-private.json').write_text(json.dumps(state,indent=2)+'\n');return state
  inactive=inactive+1 if state['unit_state'] in ['failed','inactive',''] else 0
  if inactive>=3:raise RuntimeError('Supervisor stopped without an exit receipt: '+str(state['supervisor_error']))
  time.sleep(20)
 raise TimeoutError('Finite detached native controller deadline')
