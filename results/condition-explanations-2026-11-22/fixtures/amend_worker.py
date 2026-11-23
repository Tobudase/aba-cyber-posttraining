"""Record separate calibration amendments; preserve the first pass unchanged."""
from native_conditions import make,invoke
from pathlib import Path
from kali_framed_artifacts_20261117 import emit
import json
receipt={k:[] for k in ('6664','7369','7371')}
for v in range(2):
    d=Path('/scratch/amend')/str(v);d.mkdir(parents=True);make(d,v)
    # Check the publisher's mutually exclusive combination separately from a valid local formulation.
    zero=invoke(['partx','--output-all','--pairs','--show','disk.img'],d)
    pos=invoke(['partx','--output-all','--pairs','disk.img'],d)
    neg=invoke(['partx','-o','NR,START','--pairs','disk.img'],d)
    receipt['6664'].append(dict(original=zero['rc'],repair=pos['rc'],discriminates=('UUID=' in pos['out'] and 'UUID=' not in neg['out']),keep_original_excluded=True))
    src='@interface Fixture @end\n@interface Fixture (Extras)\n- (int)number;\n@end\n@implementation Fixture (Extras)\n- (int)number {return '+str(v+1)+';}\n@end\n'
    (d/'category.m').write_text(src)
    cc=invoke(['clang','-target','x86_64-apple-macosx10.13','-fobjc-runtime=macosx-10.13','-emit-llvm','-c','category.m','-o','lib.objc.bc'],d)
    a,b=[invoke(['llvm-lto','--check-for-objc',p],d) for p in ('lib.objc.bc','plain.bc')]
    pos_text=a['out'].strip().lower();neg_text=b['out'].strip().lower()
    good=cc['rc']==a['rc']==b['rc']==0 and 'contains objc' in pos_text and 'does not contain objc' in neg_text
    receipt['7369'].append(dict(verified=good,gold=a,negative=b,help=invoke(['llvm-lto','--help'],d)['out'][:5000]))
    before=invoke(['llvm-lto','--print-macho-cpu-only','a.ir','b.ir'],d)
    a,b=d/'a.ir',d/'b.ir'
    raw=a.read_bytes();a.write_bytes(b.read_bytes());b.write_bytes(raw)
    after=invoke(['llvm-lto','--print-macho-cpu-only','a.ir','b.ir'],d)
    t1='cputype: 16777228';t2='cputype: 16777223'
    ok=all(x['rc']==0 and t1 in x['out'] and t2 in x['out'] for x in (before,after)) and before['out'].index(t1)<before['out'].index(t2) and after['out'].index(t1)>after['out'].index(t2)
    receipt['7371'].append(dict(reversed_architectures=ok))
emit(receipt,'AMEND')
