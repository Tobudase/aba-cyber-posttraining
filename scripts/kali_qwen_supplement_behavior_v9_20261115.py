"""Expanded frozen DEV46 fixture review, preserving v6 four-tool scoring."""
import base64,collections,gzip,hashlib,json,re,shlex,sys
from pathlib import Path

def main():
    sys.path.insert(0,'/input');cfg=json.loads(Path('/input/config.json').read_text())
    for name,digest in cfg['module_sha256'].items():assert hashlib.sha256((Path('/input')/name).read_bytes()).hexdigest()==digest
    raw=gzip.decompress(Path('/input/payload.json.gz').read_bytes());assert hashlib.sha256(raw).hexdigest()==cfg['payload_sha256'];data=json.loads(raw)
    import kali_data_release_20261114 as base
    import kali_functional_data_v2_20261115 as repair
    import kali_fit64_behavior_review_v5_20261115 as reviewed
    from kali_hardlink_oracle_v6_20261115 import execute_preview
    source=Path('/input/kali-behavior-fixture-worker-v2-20261112.py').read_text();legacy={'__name__':'fixture_library'};exec(source,legacy)
    reviewed.reviewed_preflight(legacy)
    import subprocess,tempfile
    version=subprocess.run(['hardlink','--version'],capture_output=True,text=True,check=True).stdout.strip()
    assert '2.37.2' in version,version
    with tempfile.TemporaryDirectory(prefix='preview-controls-') as temp:
        root=Path(temp);legacy['setup'](root,'hardlink','dry-run',1)
    setup=lambda root:legacy['setup'](root,'hardlink','dry-run',1)
    preview_checks={
        'valid_long':execute_preview(['hardlink','--dry-run','files1'],setup,'files1'),
        'valid_short':execute_preview(['hardlink','-n','files1'],setup,'files1'),
        'filtered_all_rejected':not execute_preview(['hardlink','--dry-run','--include','^$','files1'],setup,'files1'),
        'wrong_scope_rejected':not execute_preview(['hardlink','--dry-run','files1/small.dat'],setup,'files1'),
        'wrong_name_filter_rejected':not execute_preview(['hardlink','--dry-run','--respect-name','files1'],setup,'files1'),
        'real_mutation_rejected':not execute_preview(['hardlink','files1'],setup,'files1')}
    assert all(preview_checks.values()),preview_checks
    print('PREVIEW_ORACLE_CONTROLS '+json.dumps(preview_checks),flush=True)
    base.ENV=Path('/nonexistent')
    original_materialize,original_oracle=base.materialize,base.oracle
    primary={'hardlink','virtualenv','dnstwist','pyi-makespec'}
    base.materialize=lambda root,row:repair.materialize(root,row) if row['tool'] in primary else original_materialize(root,row)
    base.oracle=lambda root,row,rc,raw:equal_dump(style_expected[row['id']],rc,raw) if row['tool']=='clang-format' else repair.oracle(root,row,rc,raw) if row['tool'] in primary else original_oracle(root,row,rc,raw)
    from kali_qwen_confirm_admission_20261115 import admitted as admit_aux
    from kali_qwen_full_style_oracle_20261115 import run_dump,counterexamples,equal_dump,canonical_dump
    style_expected={}
    cases={f'kali-fixture-{t}-{kind}-{v}':(t,kind,v,gold,bad) for t,kind,v,query,gold,bad in legacy['cases']()}
    rows={r['id']:r for r in data['fixtures']};predictions=data['predictions'];ids=set().union(*({r['id'] for r in rr} for rr in predictions.values()))
    assert ids<=set(cases)|set(rows);assert not any(i.startswith('sample_') for i in ids),'Old commands must never execute'
    def run_legacy(argv,case):
        import tempfile,subprocess
        tool,kind,v,_,_=case
        if tool=='hardlink' and kind=='dry-run':
            return execute_preview(argv,lambda root:legacy['setup'](root,tool,kind,v),'files'+str(v))
        with tempfile.TemporaryDirectory(prefix='kfr-legacy-') as tmp:
            root=Path(tmp);legacy['setup'](root,tool,kind,v);before=legacy['snapshot'](root)
            try:rc,out,err=legacy['run'](argv,root,timeout=12);return bool(legacy['check'](root,tool,kind,v,rc,out,before))
            except (subprocess.TimeoutExpired,ValueError,OSError,StopIteration,SyntaxError):return False
    def execute_row(row,argv):
        if row['tool']=='hardlink' and row['expected'].get('features')==['dry-run']:
            ok=execute_preview(argv,lambda root:repair.materialize(root,row),row['expected']['directory'])
            return {'status':'PASS' if ok else 'FAIL'}
        return base.execute(row,argv)
    style_controls={}
    import shutil
    for i,row in rows.items():
        if row['tool']!='clang-format':continue
        expected=run_dump(shutil.which('clang-format'),row['argv']);style_expected[i]=expected
        wrongs=counterexamples(row['argv']);checks=[canonical_dump(run_dump(shutil.which('clang-format'),a))!=canonical_dump(expected) for a in wrongs]
        assert all(checks),'Full-style counterexample not discriminated'
        style_controls[i]={'full_effective_config':True,'wrong_base_rejected':checks[0],'extra_setting_rejected':checks[1],'expected_dump_sha256':hashlib.sha256(expected).hexdigest()}
    print('FULL_STYLE_CONTROLS '+str(len(style_controls)),flush=True)
    controls={}
    from concurrent.futures import ThreadPoolExecutor
    def control(i):
        if i in cases:
            c=cases[i];return i,{'positive':run_legacy(c[3],c),'negative_rejected':not run_legacy(c[4],c)}
        row=rows[i];ref=execute_row(row,row['argv']);alt=execute_row(row,row['alternate_argv']);negative=[execute_row(row,a) for a in row['mutations']]
        if ref['status']!='PASS' or alt['status']!='PASS' or any(x['status']!='FAIL' for x in negative):print('CONTROL_FAILURE '+json.dumps({'id':i,'tool':row['tool'],'reference':ref,'alternate':alt,'negative':negative}),flush=True)
        return i,{'positive':ref['status']=='PASS','alternate':alt['status']=='PASS','negative_rejected':bool(negative) and all(x['status']=='FAIL' for x in negative)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,c in pool.map(control,sorted(ids)):controls[i]=c
    print('FIXTURE_CONTROL_DETAILS '+json.dumps(controls),flush=True)
    assert all(all(c.values()) for c in controls.values()),'Fixture controls failed; no model outputs scored'
    print('FUNCTIONAL_CONTROLS_PASS '+str(len(controls)),flush=True)
    flags={'hardlink':{'--dry-run','--respect-name','--ignore-mode','--minimum-size','--include','--exclude','-n','-f','-p','-s','-i','-x','--no-action','--minsize','--consolidate-duplicates','--respect-pmode'},
        'virtualenv':{'--no-seed','--no-periodic-update','--copies','--symlinks','--clear','--system-site-packages','--prompt','--activators'},
        'dnstwist':{'--format','-f','--fuzzers'},
        'pyi-makespec':{'--specpath','--name','--onefile','--onedir','--windowed','--noconsole','--console','--noupx','--hidden-import','--exclude-module','--add-data','--paths','--collect-all','--directory','--singlefile','--application-name','-F','-D','-w','-c','-n'}}
    def admit_new(command,row):
        if row['tool'] not in primary:return admit_aux(command,row['tool'])
        if any(s in command for s in ['\n','\r',';','|','&','`','>','<']):return None
        try:args=shlex.split(command)
        except ValueError:return None
        if not args or args[0]!=row['tool'] or len(args)>40:return None
        for arg in args[1:]:
            if len(arg)>256:return None
            if arg.startswith('-') and arg.split('=',1)[0] not in flags[row['tool']]:return None
            if any(p.startswith(('/','~')) or '..' in p.split('/') for p in arg.split('=',1)[-1].split(':')):return None
        def option(*keys):
            for n,a in enumerate(args):
                key,sep,value=a.partition('=')
                if key in keys:return value if sep else args[n+1] if n+1<len(args) else None
        if row['tool']=='dnstwist' and option('--format','-f')!='list':return None
        if row['tool']=='virtualenv' and not {'--no-seed','--no-periodic-update'}<=set(args):return None
        return args
    def evaluate(item):
        arm,row=item;i=row['id'];out=re.findall(r'<output>\s*(.*?)\s*</output>',row['response'],re.S)
        if row['truncated'] or len(out)!=1:return arm,i,'invalid_output'
        if i in cases:
            case=cases[i];argv=reviewed.admitted_argv(out[0],case[0],case[3][1:]+case[4][1:])
            verdict='unknown_unreviewed_command' if argv is None else 'fixture_pass' if run_legacy(argv,case) else 'fixture_fail'
        else:
            fixture=rows[i];argv=admit_new(out[0],fixture)
            if argv is None:verdict='unknown_unreviewed_command'
            else:
                result=execute_row(fixture,argv);verdict='fixture_pass' if result['status']=='PASS' else 'fixture_fail' if result['status']=='FAIL' else 'unknown_execution_error'
        return arm,i,verdict
    details={arm:{} for arm in predictions};count=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for arm,i,status in pool.map(evaluate,[(arm,row) for arm,rr in predictions.items() for row in rr]):
            details[arm][i]=status;count+=1
            if count%64==0:print('FUNCTIONAL_BEHAVIOR '+str(count),flush=True)
    result={'status':'FUNCTIONAL_BEHAVIOR_COMPLETE','revision':'supplemental_v9_full_style_and_local_tools','controls':controls,'details':details,'counts':{a:dict(collections.Counter(v.values())) for a,v in details.items()},'scope':'Actual fixture outcomes; UNKNOWN not counted wrong; no old publisher command executed.','config':cfg,'preview_controls':preview_checks,'hardlink_version':version,'full_style_controls':style_controls}
    print('FUNCTIONAL_BEHAVIOR_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps(result).encode())).decode(),flush=True)
    print('FUNCTIONAL_BEHAVIOR_COMPLETE',flush=True)

if __name__=='__main__':main()
