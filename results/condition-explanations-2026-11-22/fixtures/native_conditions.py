"""Read-only behavior checks using scratch MBR images, synthetic kernel logs and inert LLVM IR."""
import hashlib
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

def invoke(argv, folder):
    exe = shutil.which(argv[0]) or shutil.which(argv[0]+'-14')
    if not exe:
        return {'rc':127,'out':'','err':'utility unavailable'}
    process = subprocess.run([exe,*argv[1:]], cwd=folder, capture_output=True, timeout=15,
                             env=dict(os.environ, LC_ALL='C'))
    return dict(rc=process.returncode, out=process.stdout.decode(errors='replace')[:10000],
                err=process.stderr.decode(errors='replace')[:1000])

def make(folder, v):
    img = bytearray(512*2048)
    img[510:512] = bytes.fromhex('55aa')
    for idx in range(2):
        offset = 446+16*idx
        img[offset+4]=0x83
        struct.pack_into('<II',img,offset+8,32+16*v+500*idx,64+16*v+16*idx)
    (folder/'disk.img').write_bytes(img)
    # Numeric priorities encode facility*8+severity. Every fixture contains both targets and distractors.
    messages = [(2,'kernel_critical'),(3,'kernel_error'),(6,'kernel_info'),
                (19,'mail_error'),(14,'user_info'),(10,'user_critical')]
    (folder/'messages.log').write_text(''.join(f'<{p}>[    1.00000{i}] {m}_{v}\n' for i,(p,m) in enumerate(messages)))
    for file,target in [('a','arm64-apple-darwin'),('b','x86_64-apple-darwin')]:
        (folder/(file+'.ll')).write_text(f'target triple = "{target}"\ndefine i32 @func_{v}() {{ ret i32 {v} }}\n')
        invoke(['llvm-as',file+'.ll','-o',file+'.ir'],folder)
    (folder/'plain.c').write_text('int marker(void){return 0;}\n')
    (folder/'unit.m').write_text('__attribute__((objc_root_class)) @interface Widget @end\n@implementation Widget @end\n')
    for src,out in [('plain.c','plain.bc'),('unit.m','lib.objc.bc')]:
        invoke(['clang','-target','x86_64-apple-darwin','-emit-llvm','-c',src,'-o',out],folder)

def bind(i, args):
    # Substitute only task file handles. Never open physical devices or consult the running kernel.
    if i in ('6664','6666'):
        return ['disk.img' if s in ('/dev/sda','/dev/sdd') else s for s in args]
    if i in ('6441','6443'):
        return args+['--file','messages.log']
    return args

def score_outputs(i, pair, v):
    gold, wrong = pair
    if gold['rc'] or wrong['rc'] or gold['out']==wrong['out']:
        return False
    s, n = gold['out'],wrong['out']
    if i=='6664':
        return 'NR="1"' in s and 'NR="2"' in s and 'START=' in s and 'UUID=' in s and 'UUID=' not in n
    if i=='6666':
        return s.splitlines()[0].split()==['NR','START','SIZE'] and str(32+16*v) in s and 'SIZE' not in n
    if i.startswith('644'):
        want = {'kernel_critical','kernel_error','kernel_info','mail_error'} if i=='6441' else {'kernel_critical','kernel_error','mail_error','user_critical'}
        got={word for word in ('kernel_critical','kernel_error','kernel_info','mail_error','user_info','user_critical') if word+'_'+str(v) in s}
        return got==want and (i!='6441' or isinstance(json.loads(s),dict))
    if i=='7371':
        return 'a.ir' in s and 'b.ir' in s and 'a.ir' not in n and len(set(s.splitlines()))>=2
    if i=='7369':
        return ('yes' in s.lower() and 'no' in n.lower()) or ('contains' in s.lower() and 'not' in n.lower() and 'not' not in s.lower())
    raise ValueError(i)

def run(plan, root):
    cases=plan['cases']
    dirs=[]
    for v in range(2):
        d=root/str(v);d.mkdir(parents=True,exist_ok=True);make(d,v);dirs.append(d)
    out={}
    for i,r in cases.items():
        records=[]
        for v,d in enumerate(dirs):
            pair=[invoke(bind(i,argv),d) for argv in (r['gold'],r['wrong'])]
            records.append(dict(gold=pair[0],negative=pair[1],verified=score_outputs(i,pair,v)))
        helptext=invoke([r['gold'][0],'--help'],dirs[0])
        out[i]=dict(records=records,eligible=all(x['verified'] for x in records),
                    help=(helptext['out'] or helptext['err'])[:5000])
    return out

if __name__=='__main__':
    from kali_framed_artifacts_20261117 import emit
    plan=json.loads(Path('/input/conditions.json').read_text())
    emit(run(plan,Path('/scratch/conditions')),'CONDITIONS')
