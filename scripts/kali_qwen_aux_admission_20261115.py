"""Finite argv admission for five local-only validation tools; never rewrite commands."""
import json,re,shlex
STYLE_KEYS={'BasedOnStyle':{'LLVM','Google','Chromium','Mozilla','WebKit','Microsoft','GNU'},'IndentWidth':None,'ColumnLimit':None,'BreakBeforeBraces':{'Allman','Attach'},'SortIncludes':{'Never','CaseSensitive','CaseInsensitive'},'UseTab':{'Always','Never'},'PointerAlignment':{'Left','Right','Middle'},'SpaceBeforeParens':{'Always','ControlStatements','Never'},'AllowShortFunctionsOnASingleLine':{'None','All','Empty','InlineOnly','Inline'}}
def style_safe(value):
 try:d=json.loads(value)
 except ValueError:
  if not (value.startswith('{') and value.endswith('}')):return False
  try:d=dict(p.strip().split(':',1) for p in value[1:-1].split(','));d={k.strip():v.strip() for k,v in d.items()}
  except ValueError:return False
 if not isinstance(d,dict) or not d or not set(d)<=set(STYLE_KEYS):return False
 for k,v in d.items():
  if STYLE_KEYS[k] is None:
   if not re.fullmatch(r'\d{1,3}',str(v)) or not 0<=int(v)<=200:return False
  elif v not in STYLE_KEYS[k]:return False
 return True

def admitted(command,tool):
 if len(command)>1800 or any(x in command for x in ['\n','\r',';','|','&','`','>','<','$','\\']):return None
 try:a=shlex.split(command)
 except ValueError:return None
 if not a or a[0]!=tool or len(a)>32 or any(len(v)>700 for v in a):return None
 tokens=a[1:];i=0
 while i<len(tokens):
  x=tokens[i];key,sep,value=x.partition('=')
  if tool=='clang-format':
   if key in ('--dump-config','-dump-config') and not sep:i+=1;continue
   if key in ('--style','-style'):
    if not sep:
     i+=1
     if i>=len(tokens):return None
     value=tokens[i]
    if not style_safe(value):return None
   else:return None
  elif tool=='ls':
   if x.startswith('-'):
    if not re.fullmatch(r'-[1ArSF]+',x):return None
   elif x not in {'items','./items','absent','./absent'}:return None
  elif tool=='column':
   if x in ('-t','--table'):i+=1;continue
   if key in ('-s','--separator'):
    if not sep:
     i+=1
     if i>=len(tokens):return None
     value=tokens[i]
    if value not in {':',','}:return None
   elif x not in {'records.txt','./records.txt','wrong.txt'}:return None
  elif tool=='look':
   if x not in {'-f','--ignore-case','ap','zz','words.txt','./words.txt'}:return None
  elif tool=='curl':
   if x in ('--silent','--show-error','-s','-S','-sS'):i+=1;continue
   if key in ('--output','-o','--range','-r'):
    if not sep:
     i+=1
     if i>=len(tokens):return None
     value=tokens[i]
    if key in ('--output','-o') and value not in {'copied.txt','./copied.txt','wrong.txt'}:return None
    if key in ('--range','-r') and not re.fullmatch(r'\d{1,3}-\d{1,3}',value):return None
   elif x not in {'file:///workspace/task/evidence.txt','file:///workspace/task/absent.txt'}:return None
  else:return None
  i+=1
 return a
