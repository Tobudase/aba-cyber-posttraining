import gzip,hashlib,json,shutil,subprocess
from pathlib import Path
from oracle import INPUT,ROOT,setup,run
from kali_framed_artifacts_20261117 import emit
from contrast_pack import PROBES
def digest(data):return hashlib.sha256(data).hexdigest()
fixtures=[setup(0),setup(1),ROOT/'sample-defaults']
fixtures[-1].mkdir()
(fixtures[-1]/'temp.mdb').write_bytes(gzip.decompress((INPUT/'third.gz').read_bytes()))
for d in fixtures:shutil.copyfile(d/'temp.mdb',d/'catalog.mdb')
schema=['--no-comments','--no-indexes','--no-not-null','--no-not_empty','--no-relations']
report={}
for i,variants in PROBES.items():
    report[i]={}
    for tag,prompt,target in variants:
        records=[]
        for v,d in enumerate(fixtures):
            if i=='6137':
                name='temp.mdb' if tag=='original' else 'catalog.mdb'
                pos=['--no-default-values','--default-values']
                if target=='retain':pos.reverse()
                first,second=[run(['mdb-schema',*schema,flag,name],d) for flag in pos]
                assert first['rc']==second['rc']==0
                actual,negative=first['out'],second['out']
                if v==2:
                    assert ('default' in actual.lower())==(target=='retain')
                    assert ('default' in negative.lower())!=(target=='retain')
            else:
                filename='origin' if tag=='original' else 'archive'
                src=d/(filename+'.ll'); data=d/(filename+'.bc')
                src.write_text(f'define i32 @{filename}_{v}() {{ ret i32 {v+1} }}\n')
                tool=lambda k:shutil.which(k) or shutil.which(k+'-14')
                subprocess.run([tool('llvm-as'),str(src),'-o',str(data)],check=True)
                def llvm(flag):
                    r=subprocess.run([tool('llvm-c-test'),flag],input=data.read_bytes(),capture_output=True,check=True)
                    return r.stdout.decode()
                flags=['--module-list-functions','--echo']
                if target=='module':flags.reverse()
                actual,negative=map(llvm,flags)
                assert f'{filename}_{v}' in actual and ('define i32' in actual)==(target=='module')
                assert ('define i32' in negative)!=(target=='module')
            records.append(dict(fixture=v,expected_sha256=digest(actual.encode()),reversed_sha256=digest(negative.encode()),distinguishes=actual!=negative))
        assert any(r['distinguishes'] for r in records)
        report[i][tag]=records
emit(report,'PAIRS')
