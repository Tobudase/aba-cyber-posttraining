"""Compile a harmless marker rule and read inert PE headers using two independent inputs."""
import csv,io,json,os,re,shlex,shutil,struct,subprocess,tempfile,zlib
import xml.etree.ElementTree as ET
from pathlib import Path
from fixture_pe import pe
from kali_framed_artifacts_20261117 import emit
def run(args,p):
    return subprocess.run(args,cwd=p,stdin=subprocess.DEVNULL,capture_output=True,timeout=25)
def main():
    root=Path('/scratch')
    repo=root/'sources.list';repo.write_text('deb https://deb.debian.org/debian trixie main\n')
    apt=['apt-get','-o','Dir::Etc::sourcelist='+str(repo),'-o','Dir::Etc::sourceparts=-','-o','Acquire::Retries=2']
    subprocess.run(apt+['update','-qq'],check=True,timeout=150)
    subprocess.run(apt+['install','--download-only','--no-install-recommends','-y','yara','pev'],check=True,stdout=subprocess.DEVNULL,timeout=200)
    tools=root/'tools';tools.mkdir()
    for f in Path('/var/cache/apt/archives').glob('*.deb'):subprocess.run(['dpkg-deb','-x',str(f),str(tools)],check=True)
    os.environ.update(PATH=str(tools/'usr/bin')+':'+os.environ['PATH'],LD_LIBRARY_PATH=str(tools/'usr/lib/x86_64-linux-gnu'))
    config='plugins_dir='+str(tools/'usr/lib/pev/plugins')+'\n'
    (root/'pev.conf').write_text(config)
    rows=json.loads(Path('/input/tasks.json').read_text());f=Path('/input/answers.json')
    draws=json.loads(f.read_text()) if f.exists() else {}
    out={}
    for k,item in rows.items():
        gold=shlex.split(item['gold'])
        helps=run([gold[0],'--help'],root);helptext=(helps.stdout+helps.stderr).decode(errors='replace')
        def test(v,args):
            with tempfile.TemporaryDirectory(dir=root) as d:
                p=Path(d)
                if k=='2289':
                    mark='LOCAL_'+str(v)
                    (p/'custom.yar').write_text('rule Check { strings: $a="'+mark+'" condition: $a and os == "linux" and arch == "x64" }')
                    (p/'note.txt').write_text(mark);(p/'irrelevant.txt').write_text('other')
                    q=run(args,p)
                    if not (p/'custom.yarc').exists():return {'rc':q.returncode,'pass':False,'diagnostic':(q.stderr+q.stdout).decode(errors='replace')[:400]}
                    yes=run(['yara','-C','custom.yarc','note.txt'],p);no=run(['yara','-C','custom.yarc','irrelevant.txt'],p)
                    return {'rc':q.returncode,'pass': q.returncode==0 and yes.returncode==no.returncode==0 and yes.stdout.startswith(b'Check ') and not no.stdout.strip()}
                db,file,fmt=('packers.txt','game.exe','csv') if k=='1605' else ('signatures.txt','trojan.dll','xml')
                (p/'pev.conf').write_text(config);pe(p/file,v)
                b=bytearray((p/file).read_bytes());struct.pack_into('<I',b,152+16,4096);b[512:516]=bytes((65,66,67,68+v));(p/file).write_bytes(b)
                for name,label in [(db,'OfflineMarker'),('other.txt','OtherMarker')]:
                    (p/name).write_text('['+label+str(v)+']\nsignature = 41 42 43 '+format(68+v,'02X')+'\nep_only = true\n')
                q=run(args,p);s=q.stdout.decode(errors='replace');wanted='OfflineMarker'+str(v)
                if fmt=='xml':
                    try:
                        tree=ET.fromstring(s)
                        typed=tree.tag=='document' and any(el.tag=='attribute' and el.get('name')=='packer' and el.text==wanted for el in tree.iter())
                    except ET.ParseError:typed=False
                else:typed=['packer',wanted] in list(csv.reader(io.StringIO(s)))
                return {'rc':q.returncode,'pass':q.returncode==0 and wanted in s and typed,'output':s[:550],'diagnostic':q.stderr.decode(errors='replace')[:200]}
        neg=[('arch=x86' if t=='arch=x64' else t) for t in gold] if k=='2289' else [('other.txt' if t in ['packers.txt','signatures.txt'] else t) for t in gold]
        checks=[{'gold':test(v,gold),'wrong':test(v,neg)} for v in (0,1)]
        valid=all(r['gold']['pass'] and not r['wrong']['pass'] and r['wrong']['rc']==0 for r in checks) and ('--define' if k=='2289' else '--database') in helptext
        entry=out[k]=dict(valid=valid,checks=checks,help=helptext,scores={})
        if k=='2289':
            fixes=[['yarac','-d','os=linux','-d','arch=x64','custom.yar','custom.yarc'],['yarac','--define=os=linux','--define=arch=x64','custom.yar','custom.yarc']]
            entry['alias_checks']=[{'form':args[1], 'positive':[test(v,args) for v in (0,1)],'wrong_value':[test(v,[t.replace('arch=x64','arch=x86') for t in args]) for v in (0,1)]} for args in fixes]
        for seed,r in draws.get(k,{}).items():
            assert valid
            try:
                def unique(pairs):
                    assert len(dict(pairs))==len(pairs)
                    return dict(pairs)
                x=json.loads(r['visible'],object_pairs_hook=unique);assert r['closed'] and r['ended'] and set(x)=={'explanation','command'} and all(isinstance(v,str) and v.strip() for v in x.values())
                args=shlex.split(x['command']);assert args[0].removeprefix('/usr/bin/')==gold[0]
                allowed=set(gold[1:]+neg[1:]+['-d','-f','-o','--output','--format','--db','--define'])
                if any(a not in allowed and not ('=' in a and all(p in allowed for p in a.split('=',1))) for a in args[1:]):raise ValueError('review')
                score='pass' if all(test(v,[gold[0],*args[1:]])['pass'] for v in (0,1)) else 'different-behavior'
            except (ValueError,KeyError,IndexError,TypeError,AssertionError) as e:score='unreviewed' if str(e)=='review' else 'format'
            entry['scores'][seed]=score
    emit(out,'DEFENSE')
if __name__=='__main__':main()
