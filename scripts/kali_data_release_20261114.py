"""Public runtime-only extraction from the executed private release module.

Protected task generation and split allocation are deliberately omitted.
Used function bodies are AST-identical; full source byte hashes differ.
See dependency-audit.json. This module does not recreate the protected release.
"""
import ast,base64,hashlib,os,re,shlex,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'.tools/kali-data-prep-venv/bin'
SHA=lambda x:hashlib.sha256(x).hexdigest()

def materialize(root,r):
    for name,text in r['files'].items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode())
    if r['tool']=='hardlink':
        for p in (root/'copies').iterdir():os.utime(p,(100000,100000))
    (root/'private-home').mkdir();(root/'private-cache').mkdir()

def expected_domains(domain, fuzzers):
    x,suffix=domain.rsplit('.',1);out=set()
    for f in fuzzers:
        if f=='hyphenation':a={x[:i]+'-'+x[i:] for i in range(1,len(x))}
        elif f=='omission':a={x[:i]+x[i+1:] for i in range(len(x))}
        elif f=='repetition':a={x[:i]+x[i]+x[i:] for i in range(len(x))}
        elif f=='transposition':a={x[:i]+x[i+1]+x[i]+x[i+2:] for i in range(len(x)-1)}
        elif f=='vowel-swap':a={x[:i]+c+x[i+1:] for i in range(len(x)) if x[i] in 'aeiou' for c in 'aeiou'}
        else:raise ValueError(f)
        out|={z+'.'+suffix for z in a if z!=x}
    return out

def oracle(root,r,rc,raw):
    e=r['expected'];k=e['kind'];text=raw.decode(errors='replace')
    if rc!=0:return False
    if k=='stdout':return text==e['text']
    if k=='bytes':return raw==base64.b64decode(e['base64'])
    if k=='file':return (root/e['path']).is_file() and (root/e['path']).read_bytes()==e['text'].encode()
    if k=='conversion':return (root/e['path']).is_file() and (root/e['path']).read_bytes()==e['text'].encode() and (root/'input.txt').read_bytes()==e['input'].encode()
    if k=='contains':return e['text'].casefold() in text.casefold()
    if k=='nonempty':return bool(text.strip())
    if k=='positive_integer':return text.strip().isdigit() and int(text)>0 and (e['key']!='LONG_BIT' or int(text) in (32,64))
    if k=='table':return [x.split() for x in text.splitlines()]==e['rows']
    if k=='shell_tokens':
        t=shlex.split(text);return t==e['tokens'] or (t[:4]==['-b',e['tokens'][2],'-a','--'] and t[4:]==['rest'])
    if k=='ssh_config':
        d=dict(x.split(None,1) for x in text.splitlines() if len(x.split(None,1))==2)
        norm=lambda x: {'true':'yes','false':'no'}.get(str(x).lower(),str(x).lower())
        return all(norm(d.get(a))==norm(b) for a,b in e['values'].items())
    if k=='style':
        d=dict((a.strip(),b.strip()) for a,b in (x.split(':',1) for x in text.splitlines() if ':' in x and not x.startswith(' ')))
        return all(d.get(a)==b for a,b in e['values'].items())
    if k=='domains':return set(text.splitlines())-{e['domain']}==expected_domains(e['domain'],e['fuzzers'])
    if k=='spec':
        specs=list((root/'specs').glob('*.spec'))
        if len(specs)!=1:return False
        tree=ast.parse(specs[0].read_text());calls={n.func.id:n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        def kw(name):
            d={}
            for arg in calls[name].keywords:
                try:d[arg.arg]=ast.literal_eval(arg.value)
                except (ValueError,TypeError):pass
            return d
        a=kw('Analysis');exe=kw('EXE');v=e['values']
        checks={'onefile':lambda:'COLLECT' not in calls,'windowed':lambda:exe.get('console') is False,'noupx':lambda:exe.get('upx') is False,'name':lambda:exe.get('name')==v['name'] and specs[0].stem==v['name'],'hidden-import':lambda:v['hidden-import'] in a.get('hiddenimports',[]),'exclude-module':lambda:v['exclude-module'] in a.get('excludes',[]),'add-data':lambda:('asset.txt','assets') in a.get('datas',[]),'paths':lambda:any(str(z).rstrip('/').split('/')[-1]=='extra' for z in a.get('pathex',[]))}
        return all(checks[f]() for f in v)
    if k=='venv':
        d=root/e['dest'];cfg=(d/'pyvenv.cfg').read_text() if (d/'pyvenv.cfg').exists() else '';v=e['values']
        if not (d/'bin/python').exists() or list(d.glob('lib/python*/site-packages/pip*')):return False
        checks={'copies':lambda:not (d/'bin/python').is_symlink(),'symlinks':lambda:(d/'bin/python').is_symlink(),'clear':lambda:not (d/'existing.txt').exists(),'system':lambda:'include-system-site-packages = true' in cfg,'prompt':lambda:'prompt = '+v['prompt'] in cfg,'bash':lambda:(d/'bin/activate').exists() and not (d/'bin/activate.fish').exists(),'fish':lambda:(d/'bin/activate.fish').exists() and not (d/'bin/activate').exists()}
        return all(checks[f]() for f in v)
    if k=='renamed':return (root/'one.new').read_text()=='a' and (root/'two.new').read_text()=='b' and not (root/'one.old').exists() and not (root/'two.old').exists()
    if k=='namei':return 'item.txt' in text and bool(re.search(r'-rw',text))
    if k=='hardlinks':
        a,b,c=[(root/'copies'/n).stat().st_ino for n in ['a.txt','b.txt','c.txt']]
        return a!=b if e['dry'] else a==b and a!=c
    if k=='html':return (root/e['path']).is_file() and e['module'] in (root/e['path']).read_text()
    if k=='syntax_only':return not (root/'a.out').exists() and not list(root.glob('*.o'))
    raise ValueError(k)

def execute(r,argv):
    # Executable, arguments, and fixtures are from this generator, never model output.
    binary=ENV/argv[0]
    exe=str(binary) if binary.exists() else shutil.which(argv[0])
    if argv[0]=='pydoc':exe=sys.executable;argv=[sys.executable,'-m','pydoc']+argv[1:]
    if not exe:return {'status':'UNAVAILABLE','tool':argv[0]}
    with tempfile.TemporaryDirectory(prefix='kali-data-') as tmp:
        root=Path(tmp);materialize(root,r)
        args=[exe]+[a.replace('/workspace/task',str(root)) for a in argv[1:]]
        env=dict(os.environ,LC_ALL='C',LANG='C',HOME=str(root/'private-home'),XDG_CACHE_HOME=str(root/'private-cache'),VIRTUALENV_OVERRIDE_APP_DATA=str(root/'private-cache'),PYTHONHASHSEED='0')
        try:
            p=subprocess.run(args,cwd=root,env=env,input=r['setup'].get('stdin','').encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
            try:ok=oracle(root,r,p.returncode,p.stdout)
            except Exception as exc:return {'status':'ORACLE_ERROR','error':str(exc)[:180]}
            return {'status':'PASS' if ok else 'FAIL','exit_code':p.returncode,'stdout_sha256':SHA(p.stdout),'stderr_tail':p.stderr.decode(errors='replace')[-240:]}
        except subprocess.TimeoutExpired:return {'status':'TIMEOUT'}
        except OSError as exc:return {'status':'EXEC_ERROR','error':str(exc)[:180]}
