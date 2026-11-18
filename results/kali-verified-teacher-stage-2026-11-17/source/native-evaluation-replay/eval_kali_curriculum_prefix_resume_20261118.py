"""Conditional same-code, same-seed prefix continuation, zero SFT.

The original model setup and numerical generation block are compiled unchanged
from the SHA-pinned original evaluation file. Prefix answers are NEVER model
inputs. The first original batch is regenerated and must match every field.
"""
import argparse,copy,hashlib,json,os,time
from pathlib import Path
from kali_curriculum_prefix_resume_20261118 import blocks,batches,validate_prefix,require_exact_first_batch


def durable_json(path,data):
    temp=path.with_suffix('.tmp')
    with temp.open('w') as stream:
        stream.write(json.dumps(data)+'\n');stream.flush();os.fsync(stream.fileno())
    temp.replace(path)


def main():
    parser=argparse.ArgumentParser()
    for name in ['stage','model-path','output','adapter','prefix','original-eval-source']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--original-eval-sha256',required=True)
    parser.add_argument('--prefix-sha256',required=True)
    parser.add_argument('--minimum-prefix-responses',type=int,choices=[416,512],default=512)
    a=parser.parse_args();assert not a.output.exists()
    raw=a.prefix.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.prefix_sha256
    original=a.original_eval_source.read_bytes()
    assert hashlib.sha256(original).hexdigest()==a.original_eval_sha256
    prefix=json.loads(raw);protocol=json.loads((a.stage/'evaluation-protocol.json').read_text())
    inputs=a.stage/'evaluation-inputs-private.json'
    assert hashlib.sha256(inputs.read_bytes()).hexdigest()==protocol['input_sha256']
    rows=json.loads(inputs.read_text());assert len(rows)==104 and len({r['id'] for r in rows})==104
    receipt=json.loads((a.adapter.parent/'receipt.json').read_text())
    n=validate_prefix(prefix,rows,protocol,receipt['adapter_sha256'],minimum=a.minimum_prefix_responses)
    setup,generation,block_sha256=blocks(original.decode())
    env={'a':a,'json':json,'hashlib':hashlib,'Path':Path,'time':time}
    # These are trusted, byte-pinned original code blocks, not generated commands
    # or contents from cases. No original source file is modified.
    exec(compile(setup,str(a.original_eval_source)+':original-setup','exec'),env)
    assert env['torch'].cuda.get_device_name(0)=='NVIDIA RTX A6000'
    generate=compile(generation,str(a.original_eval_source)+':original-generation','exec')
    saved=copy.deepcopy(prefix['predictions']);began=time.monotonic();offset=0;replayed=False
    prior_seconds=prefix['seconds']
    for sampling_seed,mode,off,batch in batches(rows,protocol):
        count=len(batch)
        if offset+count<=n and offset!=0:
            offset+=count;continue
        target=[]
        env.update(sampling_seed=sampling_seed,mode=mode,off=off,
            thinking=mode=='thinking',gen=protocol['generation'][mode],allrows=target)
        exec(generate,env)
        if offset==0:
            require_exact_first_batch(target,saved[:count]);replayed=True
            print('EXACT_ORIGINAL_FIRST_BATCH_REPLAY_PASS '+str(count),flush=True)
        else:
            assert offset==len(saved) and replayed
            saved.extend(target)
            durable_json(a.output,{'status':'RUNNING','predictions':saved,
                'adapter_sha256':receipt['adapter_sha256'],'seconds':prior_seconds+time.monotonic()-began,
                'resumed_prefix_responses':n,'first_batch_replayed_exact':True})
            print('PREFIX_RESUME_PROGRESS '+str(len(saved))+'/624',flush=True)
        offset+=count
    assert replayed and offset==len(saved)==624
    result={'status':'COMPLETE','predictions':saved,'adapter_sha256':receipt['adapter_sha256'],
        'seconds':prior_seconds+time.monotonic()-began,'GPU':env['torch'].cuda.get_device_name(0),
        'inputs_sha256':protocol['input_sha256'],'no_evaluation_gold_loaded':True,
        'reload_audit':env['reload_audit'],'prefix_resume':{
            'prefix_sha256':a.prefix_sha256,'original_eval_sha256':a.original_eval_sha256,
            'original_generation_block_sha256':block_sha256,'retained_original_prefix_responses':n,
            'new_suffix_unique_responses':624-n,'exact_first_batch_replay_responses':len(rows[:protocol['batch_size']]),
            'replayed_batch_not_double_counted':True,'new_training_updates':0,
            'timing_note':'Committed-prefix inference seconds + this continuation including replay. Full failed allocations are separately retained in the GPU ledger.'}}
    durable_json(a.output,result);print('EVAL_COMPLETE_WITH_EXACT_PREFIX_CONTINUATION',flush=True)

if __name__=='__main__':main()
