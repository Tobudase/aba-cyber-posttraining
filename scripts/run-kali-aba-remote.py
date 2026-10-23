#!/usr/bin/env python3
"""Execute one native ABA CUDA integration; credential only on stdin."""
import os,subprocess,sys
from pathlib import Path
root=Path('/home/minhao/kali-aba-cuda-20261023');manager=Path('/home/minhao/aba-synthetic-20261016/manager')
if not (manager/'conda-meta').is_dir():raise SystemExit('Pinned Conda manager missing')
token=sys.stdin.read().strip()
if not token or '\n' in token:raise SystemExit('One private stdin credential required')
state=root/'cli-state';state.mkdir(mode=0o700,exist_ok=True);os.umask(0o077)
env=os.environ.copy();env.update({'AIBUILDAI_BASE_URL':'https://ellm.nrp-nautilus.io/anthropic','AIBUILDAI_API_KEY':token,
 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1','DISABLE_TELEMETRY':'1','DISABLE_ERROR_REPORTING':'1',
 'XDG_RUNTIME_DIR':'/run/user/1000','DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/1000/bus','PATH':str(manager/'bin')+os.pathsep+env.get('PATH',''),'CLAUDE_CONFIG_DIR':str(state)})
for name in ['SMALL_FAST','HAIKU','SONNET','OPUS','SUBAGENT']:env['AIBUILDAI_'+name+'_MODEL']='qwen3-small'
p=Path.home()/'.config/systemd/user/aibuildai-run-.service.d/90-kali-cuda-limits.conf';p.parent.mkdir(parents=True,exist_ok=True)
limits='[Service]\nRuntimeMaxSec=2700\nTimeoutStopSec=30\nMemoryMax=6G\nCPUQuota=200%\nTasksMax=8192\n'
if p.exists() and p.read_text()!=limits:raise SystemExit('Unexpected existing limit file')
p.write_text(limits);subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
with (root/'native-run.log').open('x') as log:
 r=subprocess.run(['systemd-run','--user','--scope','--unit=kali-aba-cuda-client-20261023','--property=CPUQuota=200%','--property=MemoryMax=6G','--property=RuntimeMaxSec=2700','--property=TasksMax=512',str(manager/'bin/aibuildai'),'run',str(root/'task-config.json')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
print('NATIVE_ABA_EXIT_CODE='+str(r.returncode));raise SystemExit(r.returncode)
