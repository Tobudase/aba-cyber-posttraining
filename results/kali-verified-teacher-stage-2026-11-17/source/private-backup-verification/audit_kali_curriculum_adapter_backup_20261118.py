"""Read-only verification of four private, actually trained FP32 LoRA backups."""
import array
import datetime
import hashlib
import json
import math
import struct
import sys
import tarfile
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT,save,sha

STAGE=OUT/'paired-sft'

def main():
    dest=STAGE/'adapter-backup'
    record=json.loads((dest/'verified-private.json').read_text())
    assert record['status']=='FOUR_REAL_ADAPTERS_BACKED_UP_LOCALLY'
    assert sha(dest/'adapters.tar.gz')==record['archive_sha256']
    states={}
    with tarfile.open(dest/'adapters.tar.gz') as archive:
        for cid in ['answer_only','reasoning','A1','A2']:
            raw=archive.extractfile(cid+'/adapter/adapter_model.safetensors').read()
            n=struct.unpack('<Q',raw[:8])[0];header=json.loads(raw[8:8+n]);data=raw[8+n:]
            ranges=[];count=0;maxabs=0.;tensors=0
            receipt=json.load(archive.extractfile(cid+'/receipt.json'))
            assert hashlib.sha256(raw).hexdigest()==receipt['adapter_sha256']
            cfg=json.load(archive.extractfile(cid+'/adapter/adapter_config.json'))
            assert cfg['r']==16 and cfg['lora_alpha']==32 and set(cfg['target_modules'])=={'q_proj','v_proj'}
            for name,meta in header.items():
                if name=='__metadata__':continue
                assert meta['dtype']=='F32' and '.lora_' in name
                start,end=meta['data_offsets']
                assert end-start==math.prod(meta['shape'])*4 and 0<=start<end<=len(data)
                ranges.append((start,end));values=array.array('f');values.frombytes(data[start:end])
                if sys.byteorder!='little':values.byteswap()
                assert all(math.isfinite(v) for v in values)
                maxabs=max(maxabs,max(abs(v) for v in values));count+=len(values);tensors+=1
            ranges.sort()
            assert ranges[0][0]==0 and ranges[-1][1]==len(data)
            assert all(a[1]==b[0] for a,b in zip(ranges,ranges[1:]))
            assert tensors==144 and count==7667712
            states[cid]={'adapter_sha256':hashlib.sha256(raw).hexdigest(),'tensors':tensors,
                'parameters':count,'nonfinite_values':0,'max_abs':maxabs,'r':16,'alpha':32,
                'target_modules':sorted(cfg['target_modules'])}
    result={'status':'FOUR_ARCHIVED_ACTUAL_ADAPTERS_FINITE_VALID_SAFETENSORS',
        'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'states':states,
        'archive_sha256':record['archive_sha256'],'GPU':0,'weights_published':False,
        'not_evidence_of_training_benefit':True,'audit_source_sha256':sha(__file__)}
    save(dest/'all-four-finiteness-private.json',result)
    (dest/'all-four-finiteness-private.json').chmod(0o600)
    snapshots=dest/'loaded-runtime-source-private';snapshots.mkdir(exist_ok=True)
    names=['audit_kali_curriculum_adapter_backup_20261118.py','backup_kali_curriculum_adapters_20261117.py']
    for name in names:
        target=snapshots/name
        if target.exists():assert target.read_bytes()==(ROOT/'scripts'/name).read_bytes()
        else:target.write_bytes((ROOT/'scripts'/name).read_bytes())
    save(dest/'runtime-source-freeze-private.json',{name:sha(snapshots/name) for name in names})
    print(json.dumps({'status':result['status'],'states':len(states),'nonfinite_values':0,'GPU':0}))

if __name__=='__main__':main()
