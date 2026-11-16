"""Extend local-only finite admission to iconv and rev for sealed confirmation."""
import re,shlex
from kali_qwen_aux_admission_20261115 import admitted as aux

def admitted(command,tool):
 if tool not in ['iconv','rev']:return aux(command,tool)
 if len(command)>800 or any(c in command for c in ['\n','\r',';','|','&','`','$','>','<','\\']):return None
 try:a=shlex.split(command)
 except ValueError:return None
 if not a or a[0]!=tool or len(a)>12:return None
 if tool=='rev':return a if len(a)==2 and a[1] in ['evidence.txt','./evidence.txt','wrong.txt'] else None
 enc={'UTF-8','UTF-16LE','UTF-16BE','UTF-32LE','UTF-32BE','ISO-8859-1'};i=1
 while i<len(a):
  k,sep,v=a[i].partition('=')
  if k in ['-f','-t','--from-code','--to-code']:
   if not sep:
    i+=1
    if i>=len(a):return None
    v=a[i]
   if v not in enc:return None
  elif a[i] not in ['text.txt','./text.txt','wrong.txt']:return None
  i+=1
 return a
