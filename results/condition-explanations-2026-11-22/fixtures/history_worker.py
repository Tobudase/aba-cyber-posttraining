"""Calibration for four sources previously allocated exclusively to pilot training."""
import gzip,json,os,shutil,struct,subprocess
from pathlib import Path
from oracle import INPUT,ROOT
from kali_framed_artifacts_20261117 import emit

def folder(v):
    d=ROOT/('local-history-'+str(v));d.mkdir()
    db=gzip.decompress((INPUT/f'historical{v}.gz').read_bytes())
    for n in ['sales.mdb','network.mdb']:(d/n).write_bytes(db)
    size=48+4*v; raw=bytearray(size*2048); off=16*2048
    raw[off:off+7]=b'\x01CD001\x01'
    for end,step in [('<',0),('>',4)]:struct.pack_into(end+'I',raw,off+80+step,size)
    for end,step in [('<',0),('>',2)]:struct.pack_into(end+'H',raw,off+128+step,2048)
    (d/'system.iso').write_bytes(raw)
    (d/'fixture.dict').write_text('aardvark\nAd!m'+str(v)+'\nadmission\nzebra\n')
    return d

def invoke(i,args,d):
    local=ROOT/'usr/bin'/args[0]
    tool=str(local) if local.exists() else shutil.which(args[0])
    if not tool:return dict(rc=127,out='',err='utility missing')
    a=[tool,*args[1:]]
    if i=='6234' and '--help' not in a:a.append('fixture.dict')
    env=dict(os.environ,LC_ALL='C',LD_LIBRARY_PATH=str(ROOT/'usr/lib/x86_64-linux-gnu')+':'+str(ROOT/'lib/x86_64-linux-gnu'))
    r=subprocess.run(a,cwd=d,env=env,capture_output=True,timeout=10)
    return dict(rc=r.returncode,out=r.stdout.decode(errors='replace'),err=r.stderr.decode(errors='replace')[:400])
def test(i,v,g,b):
    if g['rc'] or b['rc'] or g['out']==b['out']:return False
    if i=='6539':return g['out'].strip()==str(48+4*v) and b['out'].strip()==str(2*(48+4*v))
    if i=='6234':return 'Ad!m'+str(v) in g['out'] and 'Ad!m'+str(v) not in b['out']
    try:x=json.loads(g['out'])['label'];y=json.loads(b['out'])['label']
    except (ValueError,KeyError,TypeError):return False
    original='unit'+str(v)+'\x01tail';replaced=original.replace('\x01',' ')
    return (x,y)==((replaced,original) if i=='6115' else (original,replaced))
def controls():
    rows=json.loads((INPUT/'hist.json').read_text())
    locations=[folder(v) for v in range(2)];out={}
    for i,row in rows.items():
        checks=[]
        for v,d in enumerate(locations):
            g=invoke(i,row['gold'],d);b=invoke(i,row['negative'],d)
            checks.append(dict(verified=test(i,v,g,b),gold=g,negative=b))
        helpout=invoke(i,[row['gold'][0],'--help'],locations[0])
        out[i]=dict(eligible=all(t['verified'] for t in checks),tests=checks,help=(helpout['out'] or helpout['err'])[:5000])
    emit(out,'HIST')
if __name__=='__main__':controls()
