"""VM loopback mailbox. Requests contain recipe IDs, never credentials or labels."""
import json,threading,time,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

ROOT=Path('/mnt/aba-scratch/study/broker')
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  try:
   size=int(self.headers.get('Content-Length','0'))
   assert self.path=='/candidate' and 0<size<=4096
   req=json.loads(self.rfile.read(size));assert isinstance(req,dict)
   ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
   key=uuid.uuid4().hex;path=ROOT/(key+'.request.json')
   tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(req));tmp.replace(path)
   response=ROOT/(key+'.response.json');until=time.monotonic()+95
   while time.monotonic()<until:
    if response.exists():
     raw=response.read_bytes();self.send_response(200);break
    time.sleep(.5)
   else:raise TimeoutError('Operator mailbox unavailable')
  except Exception as exc:
   raw=json.dumps({'status':'FAILED','error_type':type(exc).__name__}).encode();self.send_response(400)
  self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
def serve():ThreadingHTTPServer(('127.0.0.1',29847),Handler).serve_forever()
