"""Compare complete effective clang-format configuration, including base defaults."""
import json,subprocess

def style_config(argv):
 for i,arg in enumerate(argv):
  if arg.startswith('--style='):return json.loads(arg.split('=',1)[1])
  if arg=='--style':return json.loads(argv[i+1])
 raise ValueError('Trusted reference lacks inline style')

def run_dump(binary,argv):
 result=subprocess.run([binary]+argv[1:],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
 if result.returncode:raise RuntimeError('Trusted clang-format dump failed: '+result.stderr.decode(errors='replace')[-200:])
 return result.stdout

def counterexamples(argv):
 config=style_config(argv);wrong=dict(config);wrong['BasedOnStyle']='Google' if config['BasedOnStyle']=='LLVM' else 'LLVM'
 extra=dict(config)
 for key,value in [('IndentWidth',197),('ColumnLimit',197),('UseTab','Always'),('PointerAlignment','Middle'),('BreakBeforeBraces','Whitesmiths'),('SpaceBeforeParens','Never'),('SortIncludes','Never'),('AllowShortFunctionsOnASingleLine','All')]:
  if key not in config:extra[key]=value;break
 else:raise ValueError('No extra-property counterexample available')
 return [['clang-format','--style='+json.dumps(c,separators=(',',':')),'--dump-config'] for c in [wrong,extra]]

def canonical_dump(raw):
 return b'\n'.join(line.rstrip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith(b'#'))

def equal_dump(expected,rc,raw):return rc==0 and canonical_dump(raw)==canonical_dump(expected)
