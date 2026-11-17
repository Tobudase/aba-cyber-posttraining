"""Sequential fixed pair launcher; preflight is default unless --execute is set."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--model-path',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--scorer',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    source=Path(__file__).resolve().parent;manifest=json.loads((a.stage/'execution-manifest-private.json').read_text())
    for name,digest in manifest['scripts'].items():assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest
    for name,digest in manifest['stage_files'].items():assert hashlib.sha256((a.stage/name).read_bytes()).hexdigest()==digest
    expected=manifest['stage_files']['paired-training-private.json']
    ev=[sys.executable,str(source/'eval_kali_rationale_pair_20261117.py'),'--stage',str(a.stage),'--model-path',str(a.model_path)]
    commands=[ev+['--output',str(a.output/'base-predictions.json')]]
    for arm in ['answer_only','reasoning']:
        commands.append([sys.executable,str(source/'train_kali_rationale_pair_20261117.py'),'--data',str(a.stage/'paired-training-private.json'),'--expected-sha256',expected,'--arm',arm,'--model-path',str(a.model_path),'--output',str(a.output/arm)])
        commands.append(ev+['--adapter',str(a.output/arm/'adapter'),'--output',str(a.output/(arm+'-predictions.json'))])
    commands.append([sys.executable,str(source/'score_kali_rationale_pair_20261117.py'),'--stage',str(a.stage),'--runs',str(a.output),'--scorer',str(a.scorer),'--output',str(a.output/'comparison-private.json')])
    if not a.execute:print(json.dumps({'status':'EXECUTION_PLAN_VALID','subprocesses':len(commands),'planned_training_updates':96,'planned_eval_responses':264,'training_started':False},indent=2));return
    assert not a.output.exists();a.output.mkdir(parents=True)
    began=time.monotonic()
    for n,cmd in enumerate(commands):
        remaining=10800-(time.monotonic()-began);assert remaining>0,'Three-hour experiment budget exhausted'
        with (a.output/f'stage-{n}.log').open('w') as f:
            subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=min(7200,remaining))
    a1=json.loads((a.output/'answer_only/receipt.json').read_text());a2=json.loads((a.output/'reasoning/receipt.json').read_text())
    assert a1['initial_adapter_sha256']==a2['initial_adapter_sha256']
    assert a1['updates']==a2['updates']==48
    print(json.dumps({'status':'FIXED_PAIR_COMPLETE','training_updates':96,'promoted':False}))
if __name__=='__main__':main()
