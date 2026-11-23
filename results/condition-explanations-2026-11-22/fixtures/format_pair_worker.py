import hashlib,json,shutil
from history_worker import folder,invoke
from format_pairs import PROBES
from kali_framed_artifacts_20261117 import emit
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
out={}
for v in range(2):
    d=folder(v);shutil.copyfile(d/'network.mdb',d/'ledger.mdb')
    for name,prompt,mode in PROBES:
        f='network.mdb' if name=='original' else 'ledger.mdb'
        actual=[]
        for switch in ([],['-U']):
            row=invoke('6118',['mdb-json',*switch,f,'devices'],d)
            assert row['rc']==0
            actual.append(json.loads(row['out'])['label'])
        assert actual==['unit'+str(v)+'\x01tail','unit'+str(v)+' tail']
        if mode=='replace':actual.reverse()
        out.setdefault(name,[]).append(dict(fixture=v,expected_sha256=sha(actual[0]),reversed_sha256=sha(actual[1]),distinguishes=True))
emit(out,'XPAIR')
