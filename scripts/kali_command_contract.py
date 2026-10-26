"""Versioned synthetic-pilot command contracts, separate from official scoring.

Parse supported options with arity; never sort arbitrary shell tokens. Positional
arguments, jq filters, signed counts, repeated field order and required flags remain
meaningful. Unsupported syntax is reported, never silently accepted as equivalent.
No commands are executed here. This is not an official KaliBench metric.
"""
import json,re,shlex

class UnsupportedCommand(ValueError):pass

def split_command(command):
 try:a=shlex.split(command)
 except ValueError as e:raise UnsupportedCommand('invalid quoting') from e
 if not a or any(x in ['|',';','&&','||','&','>','>>','<'] for x in a):raise UnsupportedCommand('empty or compound shell command')
 return a

def options(tokens,values=(),flags=(),repeat=(),aliases=None):
 aliases=aliases or {};out={};pos=[];i=0;ended=False
 while i<len(tokens):
  item=tokens[i]
  if item=='--' and not ended:ended=True;i+=1;continue
  if ended or not item.startswith('-') or item=='-':pos.append(item);i+=1;continue
  key,sep,value=item.partition('=');key=aliases.get(key,key)
  if key in flags:
   if sep:raise UnsupportedCommand('value supplied to boolean flag')
   value=True
  elif key in values or key in repeat:
   if not sep:
    i+=1
    if i>=len(tokens):raise UnsupportedCommand('missing option argument')
    value=tokens[i]
  else:raise UnsupportedCommand('unsupported option')
  if key in repeat:out.setdefault(key,[]).append(value)
  elif key in out:raise UnsupportedCommand('duplicate option is ambiguous')
  else:out[key]=value
  i+=1
 return out,pos

def signed_count(s,tail=False):
 if not re.fullmatch(r'[+-]?\d+',s):raise UnsupportedCommand('unsupported count')
 if tail and s.startswith('+'):return '+'+str(int(s[1:]))
 return str(int(s))

def jq_filter(text):
 # Lex quoted strings as units. Removing whitespace inside a string changes meaning.
 parts=re.findall(r'"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z_0-9]*|==|[.\[\]()|]',text)
 if ''.join(parts)!=re.sub(r'\s+','',text):
  # Strings may contain spaces: compare after removing only inter-token whitespace.
  pattern=r'\s*'+r'\s*'.join(re.escape(t) for t in parts)+r'\s*'
  if not re.fullmatch(pattern,text):raise UnsupportedCommand('unsupported jq grammar')
 return tuple(parts)

def canonical_command(command,family):
 a=split_command(command);tool=a[0]
 if family.startswith('wc_'):
  if tool!='wc':return ('wrong-tool',tool)
  o,p=options(a[1:],flags=['-l','-w','-c','-L'],aliases={'--lines':'-l','--words':'-w','--bytes':'-c','--max-line-length':'-L'})
  if len(p)!=1 or len(o)!=1:raise UnsupportedCommand('wc requires one count mode and one input')
  return ('wc',tuple(sorted(o)),tuple(p))
 if family.startswith(('head_','tail_')):
  expected='head' if family.startswith('head_') else 'tail'
  if tool!=expected:return ('wrong-tool',tool)
  o,p=options(a[1:],values=['-n','-c'],aliases={'--lines':'-n','--bytes':'-c'})
  if len(p)!=1 or len(o)!=1:raise UnsupportedCommand('one count mode/input required')
  return (tool,tuple((k,signed_count(v,tail=tool=='tail')) for k,v in sorted(o.items())),tuple(p))
 if family.startswith('grep_'):
  if tool!='grep':return ('wrong-tool',tool)
  expanded=[]
  for item in a[1:]:
   if re.fullmatch(r'-[Fnicvx]+',item):expanded.extend('-'+c for c in item[1:])
   else:expanded.append(item)
  o,p=options(expanded,flags=['-F','-n','-i','-c','-v','-x'],aliases={'--fixed-strings':'-F','--line-number':'-n','--ignore-case':'-i','--count':'-c','--invert-match':'-v','--line-regexp':'-x'})
  if len(p)!=2:raise UnsupportedCommand('pattern and one input required')
  if '-F' not in o and re.fullmatch(r'[A-Za-z0-9 _-]+',p[0]):o['-F']=True
  return ('grep',tuple(sorted(o)),tuple(p))
 if family.startswith('jq_'):
  if tool!='jq':return ('wrong-tool',tool)
  o,p=options(a[1:],flags=['-r','-c'],aliases={'--raw-output':'-r','--compact-output':'-c'})
  if len(p)!=2:raise UnsupportedCommand('filter and one input required')
  filt=jq_filter(p[0])
  # Raw/compact have no effect on a numeric scalar; preserve string-output flags.
  if family=='jq_length' and filt==('.', 'records','|','length'):o={}
  return ('jq',tuple(sorted(o)),filt,p[1])
 if family=='openssl_serial':
  if a[:2]!=['openssl','x509']:return ('wrong-tool',tuple(a[:2]))
  o,p=options(a[2:],values=['-in'],flags=['-noout','-serial'])
  if p or '-in' not in o:raise UnsupportedCommand('one explicit certificate input required')
  return ('openssl-x509',tuple(sorted(o.items())))
 if family=='openssl_digest':
  if tool=='sha256sum':
   if len(a)!=2 or a[1].startswith('-'):raise UnsupportedCommand('unsupported sha256sum syntax')
   return ('digest','sha256',a[1])
  if a[:2]!=['openssl','dgst']:return ('wrong-tool',tuple(a[:2]))
  o,p=options(a[2:],flags=['-sha256','-sha512'])
  if len(o)!=1 or len(p)!=1:raise UnsupportedCommand('one hash algorithm/input required')
  return ('digest',next(iter(o))[1:],p[0])
 if family.startswith('tshark_'):
  if tool!='tshark':return ('wrong-tool',tool)
  o,p=options(a[1:],values=['-r','-Y','-T'],flags=['-n'],repeat=['-e'])
  if p or '-r' not in o:raise UnsupportedCommand('saved capture input required')
  return ('tshark',tuple((k,tuple(v) if isinstance(v,list) else v) for k,v in sorted(o.items())))
 if family.startswith('tcpdump_'):
  if tool!='tcpdump':return ('wrong-tool',tool)
  o,p=options(a[1:],values=['-r','-c'],flags=['-n','-nn'])
  if '-r' not in o:raise UnsupportedCommand('saved capture input required; no live capture')
  numeric=bool(o.pop('-n',False) or o.pop('-nn',False));o.pop('-nn',None)
  return ('tcpdump',tuple(sorted(o.items())),numeric,tuple(p))
 raise UnsupportedCommand('no reviewed contract for family')

def compare_command(command,row):
 try:
  gold=canonical_command(row['gold_command'],row['intent_family']);actual=canonical_command(command,row['intent_family'])
 except UnsupportedCommand as e:return {'status':'UNSUPPORTED','correct':False,'reason':str(e)}
 return {'status':'SUPPORTED','correct':actual==gold,'reason':'contract_match' if actual==gold else 'different_required_semantics'}
