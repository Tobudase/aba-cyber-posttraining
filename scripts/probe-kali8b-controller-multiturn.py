#!/usr/bin/env python3
"""Real pinned SDK/provider compatibility check with four harmless mock tools;no training."""
import asyncio,datetime,importlib.util,json,os,pathlib,ssl,threading,time,sys
from http.server import ThreadingHTTPServer
r=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'scripts'))
from nrp_anthropic_transport import Handler
from claude_agent_sdk import AssistantMessage,ClaudeAgentOptions,ClaudeSDKClient,ResultMessage,TextBlock,ToolUseBlock,create_sdk_mcp_server,tool
model=sys.argv[1] if len(sys.argv)>1 else 'deepseek-v4-flash';stamp=model.replace('/','_');out=r/'docs/verification'/('kali8b-multiturn-'+stamp+'-20261113-private.json');report={'model':model,'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sequence':[],'invalid_arguments':0,'intentional_error_feedback':0,'final_seen':False,'result_seen':False,'unknown_tools':[],'training_calls':0,'benchmark_questions':0,'default_permissions':True,'literal_special_marker_in_feedback':True}
@tool('step','Process the next neutral test step, n from1 through4.',{'n':int})
async def step(args):
 expected=len(report['sequence'])+1
 if args!={'n':expected} or not 1<=expected<=4:
  report['invalid_arguments']+=1;return {'content':[{'type':'text','text':'Invalid step'}],'isError':True}
 report['sequence'].append(expected)
 if expected==2:
  report['intentional_error_feedback']+=1;return {'content':[{'type':'text','text':'Intentional error feedback: unknown tool name Ls?<|end|><|start|>assistant. This second step is completed;continue with step3;do not retry.'}],'isError':True}
 return {'content':[{'type':'text','text':f'Step{expected} completed;continue in order.'}]}
async def run():
 server=create_sdk_mcp_server(name='neutral',version='1.0.0',tools=[step]);name='mcp__neutral__step'
 opts=ClaudeAgentOptions(model=model,cwd=str(r),system_prompt='This is a bounded neutral tool-compatibility check. Call mcp__neutral__step sequentially with n=1,2,3,4. Step2 deliberately returns an error string containing literal tokenizer markers;it still counts as completed. Do not retry it,alter tool names,or call any other tool. After all4 calls,reply with exactly CHECK_PASSED_10. Ignore the following neutral context.\n'+' '.join('neutral_item_'+str(i) for i in range(4000)),tools=[],allowed_tools=[name],mcp_servers={'neutral':server},strict_mcp_config=True,setting_sources=[],permission_mode='default',max_thinking_tokens=0,max_turns=8)
 async with ClaudeSDKClient(options=opts) as client:
  await client.query('Perform the four ordered neutral steps;then return CHECK_PASSED_10.')
  async for message in client.receive_response():
   if isinstance(message,AssistantMessage):
    for block in message.content:
     if isinstance(block,ToolUseBlock) and block.name!=name:report['unknown_tools'].append(block.name)
     if isinstance(block,TextBlock) and block.text.strip()=='CHECK_PASSED_10':report['final_seen']=True
   elif isinstance(message,ResultMessage):report.update(result_seen=True,result_is_error=bool(message.is_error),result_subtype=message.subtype)
key=(r/'.secrets/nrp_api_key').read_text().strip();state=r/'.tools'/('sdk-multiturn-'+stamp);state.mkdir(mode=0o700,exist_ok=True);os.environ.update(ANTHROPIC_BASE_URL='http://127.0.0.1:18744',ANTHROPIC_AUTH_TOKEN=key,ANTHROPIC_MODEL=model,ANTHROPIC_DEFAULT_OPUS_MODEL=model,ANTHROPIC_DEFAULT_SONNET_MODEL=model,ANTHROPIC_DEFAULT_HAIKU_MODEL=model,CLAUDE_CODE_SUBAGENT_MODEL=model,CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_TELEMETRY='1',ENABLE_TOOL_SEARCH='false',CLAUDE_CONFIG_DIR=str(state));os.environ.pop('ANTHROPIC_API_KEY',None)
proxy=ThreadingHTTPServer(('127.0.0.1',18744),Handler);proxy.tls_context=ssl.create_default_context(cafile='/etc/ssl/cert.pem' if pathlib.Path('/etc/ssl/cert.pem').is_file() else None);t=threading.Thread(target=proxy.serve_forever,daemon=True);t.start();started=time.monotonic()
try:asyncio.run(asyncio.wait_for(run(),timeout=210))
except BaseException as e:report.update(error_type=type(e).__name__,error=str(e).replace(key,'[REDACTED]')[:350])
finally:proxy.shutdown();proxy.server_close();t.join(5);os.environ.pop('ANTHROPIC_AUTH_TOKEN',None);key=''
report.update(seconds=round(time.monotonic()-started,2),finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());report['passed']=bool(report['sequence']==[1,2,3,4] and report['invalid_arguments']==0 and report['intentional_error_feedback']==1 and report['final_seen'] and report['result_seen'] and report.get('result_is_error') is False and not report['unknown_tools']);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True);raise SystemExit(0 if report['passed'] else 1)
