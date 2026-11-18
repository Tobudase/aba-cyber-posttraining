"""Conditional original-code continuation for one frozen24/3-row output file.

No training, gold labels, alternative seeds, model selection or fresh cohort.
Only used after an actually failed original deadline, with every prefix kept.
"""
import argparse,copy,hashlib,json,os,time
from pathlib import Path
from kali_curriculum_prefix_resume_20261118 import blocks,batches,validate_prefix,require_exact_first_batch

def durable_json(path,value):
    temp=path.with_suffix('.tmp')
    with temp.open('w') as f:f.write(json.dumps(value)+'\n');f.flush();os.fsync(f.fileno())
    temp.replace(path)

def main():
    parser=argparse.ArgumentParser()
    for name in ['stage','model-path','output','prefix','original-eval-source']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--adapter',type=Path)
    parser.add_argument('--prefix-sha256',required=True);parser.add_argument('--original-eval-sha256',required=True)
    a=parser.parse_args();assert not a.output.exists()
    raw=a.prefix.read_bytes();original=a.original_eval_source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==a.prefix_sha256 and hashlib.sha256(original).hexdigest()==a.original_eval_sha256
    prefix=json.loads(raw);protocol=json.loads((a.stage/'evaluation-protocol.json').read_text())
    inputs=a.stage/'evaluation-inputs-private.json';assert hashlib.sha256(inputs.read_bytes()).hexdigest()==protocol['input_sha256']
    rows=json.loads(inputs.read_text());assert len(rows)==protocol['rows'] and len(rows) in [3,24]
    assert {r['panel'] for r in rows}=={'confirmation24' if len(rows)==24 else 'known_training_gap3'}
    expected_adapter=hashlib.sha256((a.adapter/'adapter_model.safetensors').read_bytes()).hexdigest() if a.adapter else None
    n=validate_prefix(prefix,rows,protocol,expected_adapter,minimum=1)
    expected_total=len(rows)*len(protocol['seeds'])*len(protocol['modes']);assert n<expected_total
    setup,generation,block_sha256=blocks(original.decode())
    env={'a':a,'json':json,'hashlib':hashlib,'Path':Path,'time':time}
    exec(compile(setup,str(a.original_eval_source)+':original-setup','exec'),env)
    assert env['torch'].cuda.get_device_name(0)=='NVIDIA RTX A6000'
    generate=compile(generation,str(a.original_eval_source)+':original-generation','exec')
    saved=copy.deepcopy(prefix['predictions']);offset=0;replayed=False;began=time.monotonic()
    for sampling_seed,mode,off,batch in batches(rows,protocol):
        count=len(batch)
        if offset+count<=n and offset!=0:offset+=count;continue
        target=[];env.update(sampling_seed=sampling_seed,mode=mode,off=off,
            thinking=mode=='thinking',gen=protocol['generation'][mode],allrows=target)
        exec(generate,env)
        if offset==0:
            require_exact_first_batch(target,saved[:count]);replayed=True
            print('EXACT_ORIGINAL_FIRST_BATCH_REPLAY_PASS '+str(count),flush=True)
        else:
            assert offset==len(saved) and replayed;saved.extend(target)
            durable_json(a.output,{'status':'RUNNING','predictions':saved,'adapter_sha256':expected_adapter,
                'seconds':prefix['seconds']+time.monotonic()-began,'resumed_prefix_responses':n,'first_batch_replayed_exact':True})
            print('FROZEN_COHORT_RESUME_PROGRESS '+str(len(saved))+'/'+str(expected_total),flush=True)
        offset+=count
    assert replayed and offset==len(saved)==expected_total
    durable_json(a.output,{'status':'COMPLETE','predictions':saved,'adapter_sha256':expected_adapter,
        'seconds':prefix['seconds']+time.monotonic()-began,'GPU':env['torch'].cuda.get_device_name(0),
        'inputs_sha256':protocol['input_sha256'],'no_evaluation_gold_loaded':True,'reload_audit':env['reload_audit'],
        'prefix_resume':{'prefix_sha256':a.prefix_sha256,'original_eval_sha256':a.original_eval_sha256,
            'original_generation_block_sha256':block_sha256,'retained_original_prefix_responses':n,
            'new_suffix_unique_responses':expected_total-n,'exact_first_batch_replay_responses':min(len(rows),protocol['batch_size']),
            'replayed_batch_not_double_counted':True,'new_training_updates':0,'frozen_unique_responses':expected_total}})
    print('FROZEN_COHORT_FILE_COMPLETE_WITH_EXACT_PREFIX_CONTINUATION',flush=True)

if __name__=='__main__':main()
