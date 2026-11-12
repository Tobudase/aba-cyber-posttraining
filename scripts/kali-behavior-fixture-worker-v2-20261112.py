#!/usr/bin/env python3
"""Author and execute 64 local CLI fixtures with a paired incorrect command each."""
import ast,hashlib,importlib.metadata,json,os,re,shlex,subprocess,sys,tempfile
from pathlib import Path

def run(argv,cwd,timeout=30):
 p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=timeout)
 return p.returncode,p.stdout,p.stderr

def digest(x):return hashlib.sha256(x).hexdigest()

def setup(root,tool,kind,v):
 if tool=='hardlink':
  d=root/('files'+str(v));d.mkdir()
  for n in ['a.dat','b.dat','skip.bak','small.dat']:
   (d/n).write_bytes((b'x'*64) if n!='small.dat' else b'y')
   os.utime(d/n,(100000,100000))
  if kind=='respect-name':
   (d/'sub').mkdir();(d/'sub/a.dat').write_bytes(b'x'*64);os.utime(d/'sub/a.dat',(100000,100000))
  if kind=='ignore-mode':(d/'b.dat').chmod(0o600)
  if kind=='keep-oldest':os.utime(d/'a.dat',(50000,50000));os.utime(d/'b.dat',(60000,60000));os.utime(d/'skip.bak',(70000,70000))
 if tool=='virtualenv' and kind=='clear':
  (root/('env'+str(v))).mkdir();(root/('env'+str(v))/'old-marker').write_text('remove me')
 if tool=='pyi-makespec':
  (root/('app'+str(v)+'.py')).write_text('print("fixture")\n');(root/'asset.txt').write_text('benign data')

def snapshot(root):
 return {str(p.relative_to(root)):(p.stat().st_ino,p.stat().st_nlink,digest(p.read_bytes())) for p in root.rglob('*') if p.is_file()}

def check(root,tool,kind,v,rc,out,before):
 if rc!=0:return False
 if tool=='hardlink':
  f=root/('files'+str(v));same=lambda a,b:(f/a).stat().st_ino==(f/b).stat().st_ino
  if kind=='dry-run':return before==snapshot(root)
  if kind=='exclude':return same('a.dat','b.dat') and not same('a.dat','skip.bak')
  if kind=='include':return same('a.dat','b.dat') and not same('a.dat','skip.bak')
  if kind=='respect-name':return same('a.dat','sub/a.dat') and not same('a.dat','b.dat')
  if kind=='minimum-size':return all((f/n).stat().st_nlink==1 for n in ['a.dat','b.dat','skip.bak'])
  if kind=='ignore-mode':return same('a.dat','b.dat')
  if kind=='keep-oldest':return same('a.dat','b.dat') and (f/'b.dat').stat().st_mtime==50000
  if kind=='consolidate':return same('a.dat','b.dat')
 if tool=='virtualenv':
  e=root/('env'+str(v)); cfg=(e/'pyvenv.cfg').read_text() if (e/'pyvenv.cfg').exists() else ''
  if not (e/'bin/python').exists():return False
  if kind=='no-seed':return not list(e.glob('lib/python*/site-packages/pip*'))
  if kind=='copies':return not (e/'bin/python').is_symlink()
  if kind=='symlinks':return (e/'bin/python').is_symlink()
  if kind=='prompt':return 'prompt = lab'+str(v) in cfg
  if kind=='system-site-packages':return 'include-system-site-packages = true' in cfg
  if kind=='clear':return not (e/'old-marker').exists()
  if kind=='bash':return (e/'bin/activate').exists() and not (e/'bin/activate.fish').exists()
  if kind=='fish':return (e/'bin/activate.fish').exists() and not (e/'bin/activate').exists()
 if tool=='dnstwist':
  label='alpha'+('lab' if v==1 else 'zone'); domain=label+'.invalid'
  got=set(out.splitlines());got.discard(domain)
  variants={
   'addition':{label+c for c in 'abcdefghijklmnopqrstuvwxyz'},
   'hyphenation':{label[:i]+'-'+label[i:] for i in range(1,len(label))},
   'omission':{label[:i]+label[i+1:] for i in range(len(label))},
   'repetition':{label[:i]+label[i]+label[i:] for i in range(len(label))},
   'transposition':{label[:i]+label[i+1]+label[i]+label[i+2:] for i in range(len(label)-1)},
   'vowel-swap':{label[:i]+c+label[i+1:] for i in range(len(label)) if label[i] in 'aeiou' for c in 'aeiou'},
   'insertion':set(), 'replacement':set(),
  }
  if kind in ('insertion','replacement'):
   # Verify an allowed operation rather than an implementation's keyboard table.
   def valid(s):
    x=s.removesuffix('.invalid')
    if not s.endswith('.invalid'):return False
    if kind=='insertion':return len(x)==len(label)+1 and any(x[:i]+x[i+1:]==label for i in range(len(x)))
    return len(x)==len(label) and sum(a!=b for a,b in zip(x,label))==1
   return bool(got) and all(valid(s) for s in got)
  expected={s+'.invalid' for s in variants[kind] if s!=label}
  return bool(got) and got==expected
 if tool=='pyi-makespec':
  specs=list((root/'specs').glob('*.spec'))
  if len(specs)!=1:return False
  tree=ast.parse(specs[0].read_text()); calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  def kws(name):
   c=next(n for n in calls if n.func.id==name);return {k.arg:ast.literal_eval(k.value) for k in c.keywords if isinstance(k.value,(ast.Constant,ast.List,ast.Tuple))}
  names={n.func.id for n in calls};a=kws('Analysis');e=kws('EXE')
  if kind=='onefile':return 'COLLECT' not in names and not e.get('exclude_binaries',False)
  if kind=='onedir':return 'COLLECT' in names and e.get('exclude_binaries') is True
  if kind=='name':return specs[0].stem=='fixture'+str(v) and e.get('name')=='fixture'+str(v)
  if kind=='console':return e.get('console') is True
  if kind=='windowed':return e.get('console') is False
  if kind=='add-data':return ('asset.txt','assets') in a.get('datas',[])
  if kind=='hidden-import':return 'json' in a.get('hiddenimports',[])
  if kind=='exclude-module':return 'tkinter' in a.get('excludes',[])
  if kind=='noupx':return e.get('upx') is False
  if kind=='collect-all':return any(n.func.id=='collect_all' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='json' for n in calls)
 return False

def cases():
 for v in (1,2):
  for kind in ['consolidate','dry-run','exclude','include','respect-name','minimum-size','ignore-mode','keep-oldest']:
   opts={'consolidate':[],'dry-run':['--dry-run'],'exclude':['--exclude',r'\.bak$'],'include':['--include',r'\.dat$'],'respect-name':['--respect-name'],'minimum-size':['--minimum-size',str(128*v)],'ignore-mode':['--ignore-mode'],'keep-oldest':['--keep-oldest']}[kind]
   desc={'consolidate':'Consolidate duplicate files','dry-run':'Preview duplicate consolidation without changing any files','exclude':'Consolidate duplicate files but exclude names matching regex \\.bak$','include':'Consolidate duplicate files but include only names matching regex \\.dat$','respect-name':'Consolidate duplicates only when their filenames are identical','minimum-size':f'Consolidate duplicates only for files at least {128*v} bytes long','ignore-mode':'Consolidate duplicates even when their permission modes differ','keep-oldest':'Consolidate duplicate files and preserve the oldest duplicate'}[kind]
   cmd=['hardlink']+opts+['files'+str(v)];bad=['hardlink','--dry-run','files'+str(v)] if kind=='consolidate' else ['hardlink','files'+str(v)]
   yield 'hardlink',kind,v,desc+f' in directory files{v}.',cmd,bad
  for kind in ['no-seed','copies','symlinks','prompt','system-site-packages','clear','bash','fish']:
   opts={'no-seed':[],'copies':['--copies'],'symlinks':['--symlinks'],'prompt':['--prompt','lab'+str(v)],'system-site-packages':['--system-site-packages'],'clear':['--clear'],'bash':['--activators','bash'],'fish':['--activators','fish']}[kind]
   desc={'no-seed':'without installing seed packages','copies':'using copies rather than symlinks for the interpreter','symlinks':'using symlinks for the interpreter','prompt':'with activation prompt lab'+str(v),'system-site-packages':'with access to system site packages','clear':'clearing the existing destination first','bash':'generating only the bash activator','fish':'generating only the fish activator'}[kind]
   cmd=['virtualenv','--no-seed','--no-periodic-update']+opts+['env'+str(v)];bad=cmd.copy()
   if kind=='no-seed':bad.remove('--no-seed')
   elif kind in ['copies','symlinks']:bad[bad.index('--'+kind)]='--symlinks' if kind=='copies' else '--copies'
   elif kind=='prompt':bad[bad.index('lab'+str(v))]='wrong'
   elif kind in ['bash','fish']:bad[bad.index(kind)]='fish' if kind=='bash' else 'bash'
   else:bad.remove('--'+kind)
   yield 'virtualenv',kind,v,f'Create virtual environment env{v} '+desc+'. Disable seeding and periodic updates.',cmd,bad
  for kind in ['addition','hyphenation','omission','repetition','transposition','vowel-swap','insertion','replacement']:
   domain='alpha'+('lab' if v==1 else 'zone')+'.invalid'
   cmd=['dnstwist','--format','list','--fuzzers',kind,domain];bad=cmd.copy();bad[bad.index(kind)]='omission' if kind!='omission' else 'hyphenation'
   yield 'dnstwist',kind,v,f'List offline domain permutations for {domain} using only the {kind} fuzzer.',cmd,bad
  for kind in ['onefile','onedir','name','console','windowed','add-data','hidden-import','exclude-module','noupx','collect-all']:
   opts={'onefile':['--onefile'],'onedir':['--onedir'],'name':['--name','fixture'+str(v)],'console':['--console'],'windowed':['--windowed'],'add-data':['--add-data','asset.txt:assets'],'hidden-import':['--hidden-import','json'],'exclude-module':['--exclude-module','tkinter'],'noupx':['--noupx'],'collect-all':['--collect-all','json']}[kind]
   desc={'onefile':'for a single-file executable','onedir':'for a directory-based bundle','name':'with application and spec name fixture'+str(v),'console':'with a console window','windowed':'without a console window','add-data':'including asset.txt under destination assets','hidden-import':'including hidden import json','exclude-module':'excluding module tkinter','noupx':'with UPX compression disabled','collect-all':'collecting all submodules, data files, and binaries of package json'}[kind]
   cmd=['pyi-makespec','--specpath','specs']+opts+['app'+str(v)+'.py'];bad=cmd.copy()
   if kind in ['onefile','onedir']:bad[bad.index('--'+kind)]='--onedir' if kind=='onefile' else '--onefile'
   elif kind in ['console','windowed']:bad[bad.index('--'+kind)]='--windowed' if kind=='console' else '--console'
   elif kind=='noupx':bad.remove('--noupx')
   else:bad[-2]='wrong'
   yield 'pyi-makespec',kind,v,f'Generate a PyInstaller spec for app{v}.py in specs '+desc+'.',cmd,bad

SOURCES={'hardlink':'https://github.com/util-linux/util-linux/blob/v2.37.2/misc-utils/hardlink.1','virtualenv':'https://virtualenv.pypa.io/en/stable/reference/cli.html','dnstwist':'https://github.com/elceef/dnstwist/tree/20240812','pyi-makespec':'https://pyinstaller.org/en/v6.10.0/man/pyi-makespec.html'}

def main():
 p=subprocess.run([sys.executable,'-m','pip','install','--quiet','virtualenv==20.26.6','pyinstaller==6.10.0','dnstwist==20240812'],capture_output=True,text=True,timeout=240)
 assert p.returncode==0,p.stderr[-700:]
 rows=[];receipts=[]
 for tool,kind,v,query,cmd,bad in cases():
  results=[]
  for argv in (cmd,bad):
   with tempfile.TemporaryDirectory(prefix='kali-label-') as d:
    root=Path(d);setup(root,tool,kind,v);before=snapshot(root)
    try:
     rc,out,err=run(argv,root);ok=check(root,tool,kind,v,rc,out,before)
     results.append({'oracle_pass':bool(ok),'exit_code':rc,'stdout_sha256':digest(out.encode()),'stderr_tail':err[-350:]})
    except Exception as e:results.append({'oracle_pass':False,'exception':type(e).__name__+':'+str(e)[:180]})
  admitted=results[0]['oracle_pass'] and not results[1]['oracle_pass']
  ident=f'kali-fixture-{tool}-{kind}-{v}'
  receipt={'id':ident,'reference':results[0],'mutation':results[1],'admitted':admitted}
  receipts.append(receipt)
  # Native labels explicitly enumerate every requested flag and its value.
  options={};pos=[];i=1
  while i<len(cmd):
   arg=cmd[i]
   takes=arg in ['--exclude','--include','--minimum-size','--prompt','--activators','--format','--fuzzers','--specpath','--name','--add-data','--hidden-import','--exclude-module','--collect-all']
   if arg.startswith('-'):
    options[arg]=cmd[i+1] if takes else None;i+=2 if takes else 1
   else:pos.append(arg);i+=1
  target=shlex.join(cmd)
  label={'custom_id':ident,'query':query,'tool_name':tool,'ground_truth_command':target,'optional_args':options,'positional_args':pos}
  rows.append({'id':ident,'benchmark':'kali','split':'train','official_test':False,'self_authored':True,'training_eligible':admitted,'quality':'AI_AUTHORED_LINUX_BEHAVIOR_VERIFIED_SILVER' if admitted else 'QUARANTINE_FIXTURE_FAILURE','group_id':tool+':'+kind,'template_family':tool+':'+kind,'messages':[{'role':'user','content':query}],'target':'<output>'+target+'</output>','native_label':label,'source_url':SOURCES[tool],'fixture_kind':kind,'fixture_variant':v})
 versions={t:run([t,'--version'],Path('/tmp'))[:2] for t in ['hardlink','virtualenv','dnstwist','pyi-makespec']}
 print(json.dumps({'status':'BEHAVIOR_FIXTURES_COMPLETE','rows':rows,'receipts':receipts,'versions':versions,'pip_freeze':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),'official_TEST_rows':0,'gpu':0}))
if __name__=='__main__':main()
