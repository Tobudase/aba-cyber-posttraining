"""Public runtime-only extraction; protected task builders are omitted.

Used function bodies are AST-identical to the executed private module.
Historical module byte hashes require the original private source.
"""
import collections,copy,hashlib,itertools,json,os,re,shlex,stat
from pathlib import Path
import kali_data_release_20261114 as base
_BASE_MATERIALIZE=base.materialize
_BASE_ORACLE=base.oracle
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/benchkit/kali-functional-repair-2026-11-15'

def h(s):return hashlib.sha256(s.encode()).hexdigest()

def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')

def materialize(root,r):
    if r['expected']['kind']!='repair_hardlinks':return _BASE_MATERIALIZE(root,r)
    e=r['expected'];d=root/e['directory'];d.mkdir();size=e['minimum'];big=size+32;small=max(1,size-32)
    entries=[('a.bin','A',big,0o600),('b.bin','A',big,0o600),
        ('s1/same.bin','S',big,0o600),('s2/same.bin','S',big,0o600),
        ('m1/mode.bin','M',big,0o600),('m2/mode.bin','M',big,0o640),
        ('e1/filter.bak','E',big,0o600),('e2/filter.bak','E',big,0o600),
        ('p1/small.bin','P',small,0o600),('p2/small.bin','P',small,0o600)]
    for name,char,n,mode in entries:
        p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(char.encode()*n);p.chmod(mode);os.utime(p,(100000,100000))
    before={str(p.relative_to(root)):{'hash':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode),'inode':p.stat().st_ino,'mtime':p.stat().st_mtime_ns} for p in d.rglob('*') if p.is_file()}
    (root/'before.json').write_text(json.dumps(before));(root/'private-home').mkdir();(root/'private-cache').mkdir()

def oracle(root,r,rc,raw):
    if r['expected']['kind']!='repair_hardlinks':return _BASE_ORACLE(root,r,rc,raw)
    if rc!=0:return False
    e=r['expected'];fs=set(e['features']);before=json.loads((root/'before.json').read_text());names=sorted(before)
    if any(not (root/n).is_file() or hashlib.sha256((root/n).read_bytes()).hexdigest()!=before[n]['hash'] for n in names):return False
    if 'dry-run' in fs:return all((root/n).stat().st_ino==before[n]['inode'] and stat.S_IMODE((root/n).stat().st_mode)==before[n]['mode'] and (root/n).stat().st_mtime_ns==before[n]['mtime'] for n in names)
    def key(n):
        b=before[n];name=Path(n).name
        eligible=('minimum-size' not in fs or b['size']>=e['minimum']) and ('include' not in fs or bool(re.search(r'\.bin$',name))) and ('exclude' not in fs or not re.search(r'\.bak$',name))
        if not eligible:return ('ineligible',n)
        return ('eligible',b['hash'],None if 'ignore-mode' in fs else b['mode'],name if 'respect-name' in fs else None)
    return all(((root/a).stat().st_ino==(root/b).stat().st_ino)==(key(a)==key(b)) for a,b in itertools.combinations(names,2))
