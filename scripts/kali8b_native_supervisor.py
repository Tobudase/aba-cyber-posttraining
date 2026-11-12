"""Run under a bounded systemd user service, independent of operator SSH."""
import datetime,json,os,pathlib,subprocess,sys,threading
ROOT=pathlib.Path('/mnt/aba-scratch/study')
def main():
 rc=1
 try:
  token=sys.stdin.read().strip();sys.stdin.close();(ROOT/'.nrp-runtime-key-private').unlink(missing_ok=True);assert token and '\n' not in token
  sys.path.insert(0,str(ROOT));from transport import server
  proxy=server(29843);threading.Thread(target=proxy.serve_forever,daemon=True).start()
  from mailbox_server import serve
  threading.Thread(target=serve,daemon=True).start()
  env=os.environ.copy();env.update(AIBUILDAI_BASE_URL='http://127.0.0.1:29843',AIBUILDAI_API_KEY=token,CLAUDE_CONFIG_DIR=str(ROOT/'cli-state'),XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_TELEMETRY='1',CONDA_EXE='/mnt/aba-scratch/conda/bin/conda',CONDA_PREFIX='/mnt/aba-scratch/conda/envs/manager')
  env['PATH']='/mnt/aba-scratch/conda/envs/manager/bin:'+env['PATH']
  controller_model=json.loads((ROOT/'config.json').read_text())['llm']['default']['model']
  for name in ['SMALL_FAST','HAIKU','SONNET','OPUS','SUBAGENT']:env['AIBUILDAI_'+name+'_MODEL']=controller_model
  with (ROOT/'native.log').open('w') as log:
   try:result=subprocess.run(['/mnt/aba-scratch/conda/envs/manager/bin/aibuildai','run',str(ROOT/'config.json')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=27000);rc=result.returncode
   except subprocess.TimeoutExpired:rc=124
 except BaseException as exc:(ROOT/'supervisor-error-private.json').write_text(json.dumps({'error_type':type(exc).__name__}))
 finally:
  (ROOT/'.nrp-runtime-key-private').unlink(missing_ok=True)
  tmp=ROOT/'exit.tmp';tmp.write_text(json.dumps({'returncode':rc,'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}));tmp.replace(ROOT/'exit.json')
if __name__=='__main__':main()
