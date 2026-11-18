"""Atomic <=4KiB log frames with sequence, SHA256 and gzip integrity checks."""
import base64,gzip,hashlib,json,os,re
def emit(value,prefix):
    assert re.fullmatch('[A-Z0-9_]+',prefix)
    packed=gzip.compress(json.dumps(value).encode());encoded=base64.b64encode(packed).decode();parts=[encoded[i:i+3000] for i in range(0,len(encoded),3000)];digest=hashlib.sha256(packed).hexdigest()
    def line(s):
        data=(s+'\n').encode();assert len(data)<4096
        count=os.write(1,data);assert count==len(data)
    line(prefix+'_BEGIN '+json.dumps({'parts':len(parts),'sha256':digest,'bytes':len(packed)}))
    for index,part in enumerate(parts):line(prefix+'_PART '+str(index)+' '+part)
    line(prefix+'_END '+digest)
def parse(log,prefix):
    headers=[s.split(' ',1)[1] for s in log.splitlines() if s.startswith(prefix+'_BEGIN ')]
    if not headers:return None
    assert len(headers)==1,'Ambiguous artifact envelopes';header=json.loads(headers[0]);parts={}
    for line in log.splitlines():
        if line.startswith(prefix+'_PART '):
            _,index,body=line.split(' ',2);index=int(index);assert index not in parts,'Duplicate frame';parts[index]=body
    endings=[s.split(' ',1)[1] for s in log.splitlines() if s.startswith(prefix+'_END ')]
    if len(parts)!=header['parts'] or not endings:return None
    assert endings==[header['sha256']] and set(parts)==set(range(header['parts']))
    packed=base64.b64decode(''.join(parts[i] for i in range(header['parts'])),validate=True)
    assert len(packed)==header['bytes'] and hashlib.sha256(packed).hexdigest()==header['sha256'],'Corrupt artifact frames'
    return json.loads(gzip.decompress(packed))
