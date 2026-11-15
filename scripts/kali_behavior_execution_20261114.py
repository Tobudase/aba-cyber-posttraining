"""Run frozen bounded behavior checks behind a verified egress-deny gate.

Dependencies install before isolation. No prediction is executed before the
operator installs the per-job policy and releases the gate. Unknown stays unknown.
"""
import argparse, collections, hashlib, json
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT, OUT, k, submit, write

PRELUDE = r'''
import json, os, socket, subprocess, sys, time
from pathlib import Path
subprocess.run([sys.executable,'-m','pip','install','--quiet','virtualenv==20.26.6','pyinstaller==6.10.0','dnstwist==20240812'],check=True,timeout=240)
ip=socket.gethostbyname('pypi.org')
with socket.create_connection((ip,443),timeout=10): pass
print('READY_FOR_NETWORK_ISOLATION '+json.dumps({'verified_external_ip':ip}),flush=True)
deadline=time.monotonic()+600
while not Path('/scratch/egress-denied').exists():
    assert time.monotonic()<deadline,'Network isolation gate timed out'
    time.sleep(1)
try:
    with socket.create_connection((ip,443),timeout=5): pass
except OSError:
    print('NETWORK_ISOLATION_VERIFIED '+ip,flush=True)
else:
    raise RuntimeError('External connection still permitted; no predictions executed')
os.environ['PIP_NO_INDEX']='1'
'''

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def launch(source, name, review_pyi=False):
    d=OUT/source
    filename='fitting-predictions.json' if (d/'fitting-predictions.json').exists() else 'predictions.json'
    predictions=json.loads((d/filename).read_text())
    assert set(predictions) in [{'E0','A15','A16','A17','A18'},{'E0','F19','F20'}]
    freeze=json.loads((ROOT/'data/benchkit/kali-fit64-diagnostic-2026-11-14/behavior-protocol-freeze.json').read_text())
    for path,digest in freeze['files'].items(): assert sha(ROOT/path)==digest
    fixture=(ROOT/'scripts/kali-behavior-fixture-worker-v2-20261112.py').read_text()
    scorer_path=ROOT/'scripts/kali_fit64_behavior_20261114.py'
    if review_pyi:
        review=json.loads((OUT/'pyi-admission-review-freeze.json').read_text())
        scorer_path=ROOT/'scripts/kali_fit64_behavior_review_v3_20261114.py'
        assert sha(scorer_path)==review['reviewed_scorer_sha256']
    scorer=scorer_path.read_text()
    program=PRELUDE+'\nFIXTURE_SOURCE='+repr(fixture)+'\nPREDICTIONS='+repr(predictions)+'\n'+scorer
    result=submit(name,{'worker.py':program},{'cpu':'1','memory':'2Gi','ephemeral-storage':'2Gi'},runtime=1800)
    write(OUT/name/'source.json',{'source_job':source,'predictions_filename':filename,'predictions_sha256':sha(d/filename),'frozen_scorers':freeze['files'],'admission_revision':'v3_pyi_tokens' if review_pyi else 'v2_original','effective_scorer_sha256':sha(scorer_path),'model_command_network':'deny_all_egress_after_dependency_setup','official_TEST_rows':0})
    return result

def isolate(name):
    d=OUT/name;host=json.loads((d/'host.json').read_text())
    job=json.loads(k('get','job',name,'-o','json').stdout)
    assert job['metadata']['uid']==host['uid']
    logs=k('logs','job/'+name).stdout
    assert 'READY_FOR_NETWORK_ISOLATION ' in logs
    assert 'NETWORK_ISOLATION_VERIFIED ' not in logs,'Already released'
    policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'labels':{'app.kubernetes.io/managed-by':'miw113'}},'spec':{'podSelector':{'matchLabels':{'job-name':name}},'policyTypes':['Egress'],'egress':[]}}
    k('create','--dry-run=server','-f','-',body=policy)
    k('create','-f','-',body=policy)
    write(d/'network-policy.json',policy)
    # A short propagation delay precedes the in-container connectivity assertion.
    k('exec','job/'+name,'--','python','-c',"import time;from pathlib import Path;time.sleep(5);Path('/scratch/egress-denied').touch(exist_ok=False)")
    return {'status':'ISOLATION_GATE_RELEASED','job':name}

def collect(name):
    d=OUT/name;host=json.loads((d/'host.json').read_text());assert host['status']=='SUCCEEDED'
    log=(d/'worker.log').read_text();assert 'NETWORK_ISOLATION_VERIFIED ' in log
    found=[json.loads(line) for line in log.splitlines() if line.startswith('{"status": "FIT64_BOUNDED_BEHAVIOR_COMPLETE"')]
    assert len(found)==1
    result=found[0];n=len(result['controls']);assert n in [16,64]
    assert all(all(v.values()) for v in result['controls'].values()),'Fixture controls failed'
    source=json.loads((d/'source.json').read_text());src=OUT/source['source_job']
    reviewed=source['admission_revision']=='v3_pyi_tokens'
    if reviewed:assert 'REVIEWED_TOKEN_PREFLIGHT=' in log
    assert sha(src/source['predictions_filename'])==source['predictions_sha256']
    score=json.loads((src/'summary.json').read_text())
    refs=json.loads((ROOT/'data/benchkit/kali-fit64-diagnostic-2026-11-14/references-private.json').read_text())
    groups={r['custom_id']:r['tool_name'] for r in refs if r['custom_id'] in result['controls']}
    bounds={};bytool={}
    for arm,detail in result['details'].items():
        assert len(detail)==n and set(detail)==set(groups)
        p=sum(x=='fixture_pass' for x in detail.values());u=sum(x.startswith('unknown') for x in detail.values())
        bounds[arm]={'pass':p,'unknown':u,'lower':p,'upper':p+u,'total':n}
        bytool[arm]={t:dict(collections.Counter(v for i,v in detail.items() if groups[i]==t)) for t in sorted(set(groups.values()))}
    paired={}
    pairs=[('E0','A16'),('E0','A18'),('A15','A16'),('A17','A18')] if n==64 else [('E0','F19'),('E0','F20')]
    for control,treatment in pairs:
        a,b=bounds[control],bounds[treatment]
        paired[treatment+'-minus-'+control]={'pass_delta':b['pass']-a['pass'],'conservative_delta_lower':b['lower']-a['upper'],'conservative_delta_upper':b['upper']-a['lower']}
    if n==64:
        append=[bounds[a] for a in ['A16','A18']]
        decision='TRIGGER_F19_F20' if all(x['upper']<58 for x in append) else 'T_PASS_PROCEED_N64' if any(x['lower']>=58 for x in append) else 'REVIEW_UNKNOWN_BEFORE_BRANCH'
    else:
        passes=[a for a in ['F19','F20'] if bounds[a]['lower']>=15 and score['models'][a]['fit16']['format_errors']==score['models'][a]['fit16']['truncated']==0]
        decision='FIT_ESTABLISHED_PROCEED_COVERAGE_AND_RETENTION_DESIGN' if passes else 'STOP_EXPANSION_AND_ABA_MECHANISM_FAILURE' if all(bounds[a]['upper']<15 or score['models'][a]['fit16']['format_errors'] or score['models'][a]['fit16']['truncated'] for a in ['F19','F20']) else 'REVIEW_UNKNOWN_BEFORE_BRANCH'
        score['fitting_pass_arms']=passes
    score.update(status=f'COMPLETE_TRAIN{n}_DIAGNOSIS',behavior=result['models'],behavior_by_tool=bytool,behavior_bounds=bounds,paired_behavior=paired,decision=decision,behavior_gate_decided=True,scope=f'Original TRAIN{n} fitting; not heldout performance or full semantic certification.')
    score['admission_revision']=source['admission_revision']
    for path,value in [(d/'behavior.json',result),(src/('complete-summary-v3.json' if reviewed else 'complete-summary.json'),score),(d/'collection-audit.json',{'worker_log_sha256':sha(d/'worker.log'),'job_uid':host['uid'],'network_isolation_verified':True,'source':source})]:
        assert not path.exists();write(path,value)
    return score

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','isolate','collect']);p.add_argument('name');p.add_argument('--source');p.add_argument('--review-pyi',action='store_true');a=p.parse_args()
    print(json.dumps(launch(a.source,a.name,a.review_pyi) if a.action=='launch' else isolate(a.name) if a.action=='isolate' else collect(a.name),indent=2))
