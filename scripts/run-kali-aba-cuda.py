#!/usr/bin/env python3
"""Run the prepared native ABA task only after verified matched E0 is available.

Requires an already-ready owned VM. Token is read locally and sent on SSH stdin,
never printed or placed in command arguments. Loopback bridge lives only during
this process. The native client/service have45-minute limits; VM also auto-stops.
This does not publish, query official tests, or adopt an adapter automatically.
"""
import json,subprocess,threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from kali_cuda_jobs import ROOT,canonical,sha,frozen,verified_receipt
from kali_cuda_broker import Broker,Handler


def main():
 p,_=frozen();phash=sha(canonical(p));base=ROOT/'docs/verification/kali-cuda-cycle-v1/E0/infer'
 if not (base/'receipt.json').is_file() or not (base/'scores.json').is_file():raise SystemExit('Verified matching CUDA baseline required; no model API call made')
 receipt=verified_receipt(base,p);scores=json.loads((base/'scores.json').read_text())
 if receipt['status']!='COMPLETE' or receipt['protocol_sha256']!=phash or scores['protocol_sha256']!=phash:raise SystemExit('Verified matching CUDA baseline required; no model API call made')
 task=ROOT/'.tools/kali-aba-cuda-task';manifest=json.loads((task/'manifest.json').read_text())
 if manifest['protocol_sha256']!=phash or any(sha((task/n).read_bytes())!=h for n,h in manifest['files'].items()):raise SystemExit('Task bytes mismatch; no API call made')
 server=ThreadingHTTPServer(('127.0.0.1',18741),Handler);server.broker=Broker();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  # Authentication is retained solely in private local/remote owner-only state.
  token=(ROOT/'.secrets/nrp_api_key').read_text().strip()
  if not token or '\n' in token:raise ValueError('Missing local private credential')
  command=['bash',str(ROOT/'scripts/vm-ssh.sh'),'--local-ssh-opts=-R 127.0.0.1:18742:127.0.0.1:18741','--local-ssh-opts=-o ExitOnForwardFailure=yes','--command','python3 /home/minhao/kali-aba-cuda-20261023/run-native.py']
  process=subprocess.run(command,input=token,text=True,capture_output=True,timeout=2800)
  # Avoid exposing remote logs, environment state, or credentials on errors.
  out=process.stdout.replace(token,'[REDACTED]');err=process.stderr.replace(token,'[REDACTED]')
  (ROOT/'.tools/kali-aba-native-client.json').write_text(json.dumps({'returncode':process.returncode,'stdout':out,'stderr':err},indent=2)+'\n')
  print(json.dumps({'status':'NATIVE_CLIENT_EXITED','returncode':process.returncode,'native_terminal_and_artifact_verification_still_required':True}))
  return process.returncode
 finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=='__main__':raise SystemExit(main())
