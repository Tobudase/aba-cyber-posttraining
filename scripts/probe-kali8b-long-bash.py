#!/usr/bin/env python3
"""Real SDK long-tool test; only an exact harmless sleep/print is permitted."""
import asyncio,datetime,json,os,pathlib,ssl,sys,threading,time
from http.server import ThreadingHTTPServer
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from nrp_anthropic_transport import Handler
from claude_agent_sdk import ClaudeAgentOptions,ClaudeSDKClient,ResultMessage,PermissionResultAllow,PermissionResultDeny
MODEL='deepseek-v4-flash'
COMMAND="python3 -c 'import time; time.sleep(135); print(\"LONG_WAIT_CHECK_PASSED\")'"
report={'status':'STARTING','started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'accepted_tools':0,'denied_tools':0,'training_calls':0,'benchmark_questions':0}
async def permit(name,args,context):
 if name=='Bash' and args.get('command')==COMMAND and args.get('timeout')==600000 and report['accepted_tools']==0:
  report['accepted_tools']+=1;report['permission_at_monotonic']=time.monotonic();return PermissionResultAllow(updated_input=args)
 report['denied_tools']+=1;return PermissionResultDeny(message='Only the exact harmless long-wait test command with timeout600000 is permitted.')
async def execute():
 opts=ClaudeAgentOptions(model=MODEL,cwd=str(R),tools=['Bash'],setting_sources=[],permission_mode='default',can_use_tool=permit,max_thinking_tokens=0,max_turns=4,system_prompt='Call Bash exactly once with the exact command and timeout below. It harmlessly sleeps135seconds to test a long-running tool. Do not shorten,modify or duplicate it. After it returns,reply LONG_WAIT_CHECK_PASSED. No files,other tools,network or resources are to be modified.\ncommand: '+COMMAND+'\ntimeout:600000')
 async with ClaudeSDKClient(options=opts) as client:
  await client.query('Execute the exact permitted long-tool test,then report its result.')
  async for msg in client.receive_response():
   if isinstance(msg,ResultMessage):report.update(result_seen=True,result_is_error=bool(msg.is_error),num_turns=msg.num_turns,result_text=msg.result)
key=(R/'.secrets/nrp_api_key').read_text().strip();state=R/'.tools/sdk-long-bash-check';state.mkdir(mode=0o700,exist_ok=True)
os.environ.update(ANTHROPIC_BASE_URL='http://127.0.0.1:18746',ANTHROPIC_AUTH_TOKEN=key,ANTHROPIC_MODEL=MODEL,ANTHROPIC_DEFAULT_OPUS_MODEL=MODEL,ANTHROPIC_DEFAULT_SONNET_MODEL=MODEL,ANTHROPIC_DEFAULT_HAIKU_MODEL=MODEL,CLAUDE_CODE_SUBAGENT_MODEL=MODEL,CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_TELEMETRY='1',ENABLE_TOOL_SEARCH='false',CLAUDE_CONFIG_DIR=str(state));os.environ.pop('ANTHROPIC_API_KEY',None)
proxy=ThreadingHTTPServer(('127.0.0.1',18746),Handler);proxy.tls_context=ssl.create_default_context(cafile='/etc/ssl/cert.pem' if pathlib.Path('/etc/ssl/cert.pem').exists() else None);thread=threading.Thread(target=proxy.serve_forever,daemon=True);thread.start();start=time.monotonic()
try:asyncio.run(asyncio.wait_for(execute(),timeout=250))
except BaseException as e:report.update(error_type=type(e).__name__,error=str(e).replace(key,'[REDACTED]')[:300])
finally:proxy.shutdown();proxy.server_close();thread.join(5);os.environ.pop('ANTHROPIC_AUTH_TOKEN',None)
permission=report.pop('permission_at_monotonic',None);report['seconds']=round(time.monotonic()-start,2);report['seconds_after_permission']=round(time.monotonic()-permission,2) if permission else None
report['passed']=bool(report['accepted_tools']==1 and report.get('result_seen') and not report.get('result_is_error') and report['seconds_after_permission']>=135 and 'LONG_WAIT_CHECK_PASSED' in (report.get('result_text') or ''));report['status']='PASS_REAL_SDK_BASH_OVER120SECONDS' if report['passed'] else 'FAILED';report['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(R/'docs/verification/kali8b-long-bash-20261113-private.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
