#!/usr/bin/env python3
"""Loopback-only Anthropic transport: nonstream upstream -> typed valid SSE.

NRP mixed SSE reproducibly emits text_delta inside tool_use, which clients reject.
Never remove text or change tool names/IDs/arguments. This adapter obtains the
complete upstream Message and serializes each typed content block separately.
No prompt/credential logs, no tool execution, no extra retries, no safety changes.
"""
import json,ssl,urllib.request,urllib.error,threading
from urllib.parse import urlsplit,parse_qsl
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

UPSTREAM='https://ellm.nrp-nautilus.io/anthropic'
# Explicit compatibility alias: ABA's catalog uses the full model name;NRP
# publishes the short service alias. Message/tool content is never rewritten.
MODEL_ALIASES={'gpt-oss-120b':'gpt-oss'}
def route_payload(payload):
 result=dict(payload)
 if result.get('model') in MODEL_ALIASES:result['model']=MODEL_ALIASES[result['model']]
 return result

def route_target(target):
 parsed=urlsplit(target)
 if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path not in ['/v1/messages','/v1/messages/count_tokens']:
  raise ValueError('Unsupported route')
 if parsed.query and parse_qsl(parsed.query,keep_blank_values=True)!=[('beta','true')]:
  raise ValueError('Unsupported query')
 return parsed.path,parsed.path+('?' + parsed.query if parsed.query else '')

def encode_events(message):
 if message.get('type')!='message' or message.get('role')!='assistant':raise ValueError('Upstream is not an assistant Message')
 content=message.get('content')
 if not isinstance(content,list):raise ValueError('Invalid upstream content')
 blocks=[]
 for i,b in enumerate(content):
  if not isinstance(b,dict):raise ValueError('Invalid upstream block')
  t=b.get('type')
  if t=='text':
   if not isinstance(b.get('text'),str):raise ValueError('Invalid text')
   blocks.extend([{'type':'content_block_start','index':i,'content_block':{'type':'text','text':''}},{'type':'content_block_delta','index':i,'delta':{'type':'text_delta','text':b['text']}},{'type':'content_block_stop','index':i}])
  elif t=='tool_use':
   if not isinstance(b.get('name'),str) or not isinstance(b.get('id'),str) or not isinstance(b.get('input'),dict):raise ValueError('Invalid tool use')
   blocks.extend([{'type':'content_block_start','index':i,'content_block':{**b,'input':{}}},{'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(b['input'],ensure_ascii=False,separators=(',',':'))}},{'type':'content_block_stop','index':i}])
  elif t in ['thinking','redacted_thinking']:
   # Typed complete start blocks retain reasoning/signatures exactly.
   blocks.extend([{'type':'content_block_start','index':i,'content_block':b},{'type':'content_block_stop','index':i}])
  else:raise ValueError('Unsupported content block: '+str(t))
 start={k:v for k,v in message.items() if k not in ['content','stop_reason','stop_sequence']};start.update(content=[],stop_reason=None,stop_sequence=None)
 events=[{'type':'message_start','message':start},*blocks,{'type':'message_delta','delta':{'stop_reason':message.get('stop_reason'),'stop_sequence':message.get('stop_sequence')},'usage':message.get('usage',{})},{'type':'message_stop'}]
 return b''.join(('event: '+e['type']+'\ndata: '+json.dumps(e,ensure_ascii=False)+'\n\n').encode() for e in events)

class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*args):pass
 def do_POST(self):
  parsed=urlsplit(self.path)
  # Diagnostic metadata only: never prompts, bodies, credentials or query values.
  meta={'at_utc':datetime.now(timezone.utc).isoformat(),'method':'POST','path':parsed.path,'query_keys':[k for k,v in parse_qsl(parsed.query)]}
  with (Path(__file__).resolve().parents[1]/'.tools/nrp-transport-metadata.jsonl').open('a') as f:f.write(json.dumps(meta)+'\n')
  try:path,target=route_target(self.path)
  except ValueError:self.send_error(404);return
  stage='request_validation';status=None;shape=None
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=12*1024**2:raise ValueError('Invalid request size')
   payload=route_payload(json.loads(self.rfile.read(n)));stream=bool(payload.get('stream'))
   if path=='/v1/messages':payload['stream']=False
   headers={k:v for k,v in self.headers.items() if k.lower() in ['content-type','authorization','x-api-key','anthropic-version','anthropic-beta']}
   headers['Content-Type']='application/json'
   request=urllib.request.Request(UPSTREAM+target,data=json.dumps(payload).encode(),headers=headers,method='POST')
   stage='upstream_request'
   try:
    with urllib.request.urlopen(request,context=self.server.tls_context,timeout=240) as r:status=r.status;body=r.read();returned=r.headers
   except urllib.error.HTTPError as exc:status=exc.code;body=exc.read();returned=exc.headers
   if status==200 and stream and path=='/v1/messages':
    stage='upstream_json';message=json.loads(body)
    shape={'message_type':message.get('type'),'role':message.get('role'),'stop_reason':message.get('stop_reason'),'blocks':[{'type':b.get('type'),'input_type':type(b.get('input')).__name__} if isinstance(b,dict) else {'python_type':type(b).__name__} for b in message.get('content',[])]} if isinstance(message,dict) and isinstance(message.get('content'),list) else {'python_type':type(message).__name__}
    stage='typed_sse_validation';body=encode_events(message);ctype='text/event-stream; charset=utf-8'
   else:ctype=returned.get('Content-Type','application/json')
   self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close')
   for name in ['x-ratelimit-remaining','x-ratelimit-reset','retry-after']:
    if returned.get(name):self.send_header(name,returned[name])
   self.end_headers();self.wfile.write(body);self.close_connection=True
  except Exception as exc:
   # Shapes and a stage are sufficient to distinguish malformed provider output
   # from transport errors; never persist prompts, tool arguments or credentials.
   diagnostic={**meta,'stage':stage,'error_type':type(exc).__name__,'upstream_status':status,'shape':shape}
   with (Path(__file__).resolve().parents[1]/'.tools/nrp-transport-errors.jsonl').open('a') as f:f.write(json.dumps(diagnostic)+'\n')
   body=json.dumps({'type':'error','error':{'type':'api_error','message':'Loopback transport validation failed: '+type(exc).__name__}}).encode()
   try:self.send_response(502);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   except OSError:pass
   self.close_connection=True

def server(port=18743):
 import certifi
 s=ThreadingHTTPServer(('127.0.0.1',port),Handler);s.tls_context=ssl.create_default_context(cafile=certifi.where());return s
if __name__=='__main__':server().serve_forever()
