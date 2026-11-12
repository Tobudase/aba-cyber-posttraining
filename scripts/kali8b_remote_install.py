"""Finite controller installation that survives SSH and local-network resets."""
import hashlib,json,shlex,time
from pathlib import Path
from kali8b_native_daemon import safe_ssh
INSTALL_SUPERVISOR='''import pathlib,subprocess,json,datetime
r=pathlib.Path('/home/fedora');rc=1
(r/'kali8b-install-started.json').write_text(json.dumps({'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
try:
 with (r/'kali8b-install-private.log').open('w') as log:
  try:p=subprocess.run(['/bin/bash',str(r/'kali8b-install.sh')],stdout=log,stderr=subprocess.STDOUT,timeout=1500);rc=p.returncode
  except subprocess.TimeoutExpired:rc=124
except BaseException as exc:(r/'kali8b-install-error.json').write_text(json.dumps({'error_type':type(exc).__name__}))
finally:
 p=r/'kali8b-install-exit.tmp';p.write_text(json.dumps({'returncode':rc}));p.replace(r/'kali8b-install-exit.json')
'''
def install(driver,record):
 source=(driver.ROOT/'scripts/kali8b_native_install.sh').read_text()
 for command,payload in [('sudo loginctl enable-linger fedora',None),('cat > /home/fedora/kali8b-install.sh',source),('cat > /home/fedora/kali8b-install-supervisor.py',INSTALL_SUPERVISOR)]:
  for _ in range(6):
   result=safe_ssh(driver,command,payload=payload,timeout=45)
   if result is not None and result.returncode==0:break
   time.sleep(10)
  else:raise RuntimeError('Unable to stage detached installation')
 launch='''import os,subprocess,json,pathlib
r=pathlib.Path('/home/fedora');e=os.environ.copy();e.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
if (r/'kali8b-install-started.json').exists():print(json.dumps({'already_started':True}))
else:
 p=subprocess.run(['systemd-run','--user','--collect','--unit=kali8b-install.service','--property=Delegate=yes','--property=RuntimeMaxSec=1590','--property=StandardOutput=append:/home/fedora/kali8b-install-supervisor-private.log','--property=StandardError=append:/home/fedora/kali8b-install-supervisor-private.log','/usr/bin/python3','/home/fedora/kali8b-install-supervisor.py'],env=e,capture_output=True,text=True)
 print(json.dumps({'returncode':p.returncode,'stderr':p.stderr[-500:]}))
'''
 result=safe_ssh(driver,'python3 -c '+shlex.quote(launch),timeout=45)
 if result is not None and result.returncode==0:
  ack=json.loads(result.stdout);assert ack.get('already_started') or ack.get('returncode')==0,ack
 record.update(status='INSTALLING_DETACHED',install_program_sha256=hashlib.sha256(source.encode()).hexdigest());driver.save(record);print('PINNED_INSTALL_DAEMON_RUNNING',flush=True)
 status='''import pathlib,json,subprocess,os
r=pathlib.Path('/home/fedora');p=r/'kali8b-install-exit.json';e=os.environ.copy();e.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus');u=subprocess.run(['systemctl','--user','show','kali8b-install.service','--property=ActiveState','--value'],capture_output=True,text=True,env=e)
print(json.dumps({'exit':json.loads(p.read_text()) if p.exists() else None,'unit_state':u.stdout.strip(),'log_tail':(r/'kali8b-install-private.log').read_text(errors='replace')[-1200:] if (r/'kali8b-install-private.log').exists() else ''}))
'''
 until=time.monotonic()+2100;inactive=0
 while time.monotonic()<until:
  result=safe_ssh(driver,'python3 -c '+shlex.quote(status),timeout=45)
  if result is None or result.returncode:record['install_transport_state']='RECONNECTING_NO_RESTART';driver.save(record);time.sleep(15);continue
  state=json.loads(result.stdout);record['install_transport_state']='CONNECTED';driver.save(record)
  if state['exit'] is not None:
   receipt={'returncode':state['exit']['returncode'],'stdout':state['log_tail'],'stderr':'','transport':'detached_systemd','install_program_sha256':hashlib.sha256(source.encode()).hexdigest()};(driver.OUT/'install-private.json').write_text(json.dumps(receipt,indent=2)+'\n');assert receipt['returncode']==0,'Detached installation failed;receipt/log preserved';assert 'REAL_CONDA_RUNTIME_OK' in receipt['stdout'] and 'ACTION_REQUEST_CONTRACT_TEST_PASS' in receipt['stdout'];return
  inactive=inactive+1 if state['unit_state'] in ['failed','inactive',''] else 0
  if inactive>=3:raise RuntimeError('Installer stopped without an exit receipt')
  time.sleep(20)
 raise TimeoutError('Detached installation polling deadline')
