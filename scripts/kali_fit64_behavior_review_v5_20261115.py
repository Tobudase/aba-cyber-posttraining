"""Bounded fixture checks for generated commands, with explicit unknowns.

The builder embeds only authored fixture tasks and model responses. No secrets,
official tests, shell invocation, arbitrary tools or outside paths are allowed.
"""
import json, re, shlex, subprocess, sys, tempfile
from pathlib import Path

def admitted_argv(command, tool, case_args):
    try: args=shlex.split(command)
    except ValueError:return None
    if not args or args[0]!=tool or any(x in command for x in ('\n','\r',';','|','&','`','>','<')):return None
    # Only tokens already reviewed for this exact fixture, plus safe alternate
    # flags from its paired mutation. Unknown forms are not scored as wrong.
    allowed=set(case_args) | set(REVIEWED_EXTRA_TOKENS.get(tool, []))
    for value in args[1:]:
        pieces=value.split('=',1) if value.startswith('--') and '=' in value else [value]
        if any(x not in allowed for x in pieces):return None
        if any(x.startswith('/') or '..' in x for x in pieces):return None
    # Domain permutations must remain offline. Environment creation must not
    # download packages; this is also required explicitly by all task prompts.
    if tool=='dnstwist' and not ('--format' in args and args[args.index('--format')+1:args.index('--format')+2]==['list']):return None
    if tool=='virtualenv' and not {'--no-seed','--no-periodic-update'}.issubset(args):return None
    return args

REVIEWED_EXTRA_TOKENS={'hardlink':['--no-action','--minsize','--consolidate-duplicates','--respect-pmode','--dry-run','--respect-name','--ignore-mode','-n','-f','-p'],'virtualenv':['--copies','--symlinks','--clear','--system-site-packages'],'pyi-makespec':['--directory','--application-name','--noconsole','--singlefile','--onefile','--onedir','--console','--windowed','--noupx','-F','-D','-c','-w']}

def reviewed_preflight(ns):
    checks=[('onedir',['pyi-makespec','--specpath','specs','--directory','app1.py'],False),('name',['pyi-makespec','--specpath','specs','--application-name','fixture1','--name','fixture1','app1.py'],False),('windowed',['pyi-makespec','--specpath','specs','--noconsole','app1.py'],True)]
    receipts=[]
    for kind,argv,expected in checks:
        with tempfile.TemporaryDirectory(prefix='review-preflight-') as temp:
            root=Path(temp);ns['setup'](root,'pyi-makespec',kind,1);before=ns['snapshot'](root)
            rc,out,err=ns['run'](argv,root,timeout=12)
            passed=bool(ns['check'](root,'pyi-makespec',kind,1,rc,out,before))
            assert passed is expected
            if not expected:assert rc!=0 and 'unrecognized arguments' in err
            receipts.append({'kind':kind,'argv':argv,'returncode':rc,'fixture_pass':passed,'stderr_tail':err[-500:]})
    print('REVIEWED_TOKEN_PREFLIGHT='+json.dumps(receipts),flush=True)

def main():
    ns={'__name__':'fixture_library'};exec(FIXTURE_SOURCE,ns)
    p=subprocess.run([sys.executable,'-m','pip','install','--quiet','virtualenv==20.26.6','pyinstaller==6.10.0','dnstwist==20240812'],capture_output=True,text=True,timeout=240)
    assert p.returncode==0,p.stderr[-500:]
    reviewed_preflight(ns)
    print('TOOL_HELP_AUDIT='+json.dumps({tool:ns['run']([tool,'--help'],Path('/scratch'),timeout=15) for tool in ['hardlink','pyi-makespec','virtualenv','dnstwist']}),flush=True)
    cases={f'kali-fixture-{t}-{kind}-{v}':(t,kind,v,gold,bad) for t,kind,v,query,gold,bad in ns['cases']()}
    def execute(argv, case):
        tool,kind,v,_,_=case
        with tempfile.TemporaryDirectory(prefix='fit64-') as temp:
            root=Path(temp);ns['setup'](root,tool,kind,v);before=ns['snapshot'](root)
            try:
                rc,out,err=ns['run'](argv,root,timeout=12)
                return bool(ns['check'](root,tool,kind,v,rc,out,before))
            except (subprocess.TimeoutExpired,ValueError,OSError,StopIteration,SyntaxError):return False
    controls={};details={}
    ids={x['id'] for x in next(iter(PREDICTIONS.values()))}
    for ident in sorted(ids):
        case=cases[ident];controls[ident]={'positive':execute(case[3],case),'negative_rejected':not execute(case[4],case)}
    for arm,rows in PREDICTIONS.items():
        details[arm]={}
        for row in rows:
            ident=row['id'];case=cases[ident];out=re.findall(r'<output>\s*(.*?)\s*</output>',row['response'],re.S)
            if row['truncated'] or len(out)!=1:status='invalid_output'
            elif not all(controls[ident].values()):status='unknown_fixture_control'
            else:
                argv=admitted_argv(out[0],case[0],case[3][1:]+case[4][1:])
                status='unknown_unreviewed_command' if argv is None else ('fixture_pass' if execute(argv,case) else 'fixture_fail')
            details[arm][ident]=status
    from collections import Counter
    print(json.dumps({'status':'FIT64_BOUNDED_BEHAVIOR_COMPLETE','controls':controls,'models':{k:dict(Counter(v.values())) for k,v in details.items()},'details':details,'scope':'v5: uniform finite admission of valid defaults and aliases plus v4 reviewed spellings; fixed fixture semantics unchanged. Unknown tool mismatch remains UNKNOWN. No new model generation.','official_TEST_rows':0,'GPU':0}))

if __name__=='__main__':main()
