"""Add explicit opposite-mode supervision and counterexamples for PyInstaller."""
import ast,copy,itertools,json,shlex
from pathlib import Path
import kali_functional_data_20261115 as prior

ROOT=prior.ROOT
DATA=ROOT/'data/benchkit/kali-functional-repair-v2-2026-11-15'
materialize=prior.materialize

def oracle(root,r,rc,raw):
    if not prior.oracle(root,r,rc,raw):return False
    if r['tool']!='pyi-makespec':return True
    spec=next((root/'specs').glob('*.spec'));tree=ast.parse(spec.read_text());calls={n.func.id:n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    values={}
    for arg in calls['EXE'].keywords:
        try:values[arg.arg]=ast.literal_eval(arg.value)
        except (ValueError,TypeError):pass
    if r['expected'].get('repair_onedir') and not ('COLLECT' in calls and values.get('exclude_binaries') is True):return False
    if r['expected'].get('repair_console') and values.get('console') is not True:return False
    return True

def generate():
    DATA.mkdir(exist_ok=True);target=DATA/'fixtures.json';assert not target.exists()
    data=json.loads((prior.DATA/'fixtures.json').read_text());out={s:[] for s in data}
    for split,rows in data.items():
        for original in rows:
            r=copy.deepcopy(original);r['source_v1_id']=r['id'];r['source_v1_group']=r['constraint_group']
            if r['tool']=='pyi-makespec':
                additions=[]
                if 'onefile' not in r['expected']['values']:additions.append(('--onedir','--onefile','Use a directory-based bundle.','repair_onedir','onedir'))
                if 'windowed' not in r['expected']['values']:additions.append(('--console','--windowed','Enable a console window.','repair_console','console'))
                for flag,bad,text,key,feature in additions:
                    for command in [r['argv'],r['alternate_argv'],*r['mutations']]:command.insert(-1,flag)
                    r['expected'][key]=True;r['primitive_constraints'].append(feature);r['query']+=' '+text;r['native_label']['optional_args'][flag]=None
                for flag,bad,text,key,feature in additions:
                    mutation=r['argv'].copy();mutation[mutation.index(flag)]=bad;r['mutations'].append(mutation)
                r['primitive_constraints']=sorted(r['primitive_constraints']);r['constraint_group']='pyi-makespec:'+','.join(r['primitive_constraints'])
            r['id']='kfr2-'+prior.h(r['constraint_group']+':'+split+':'+str(r['variant']))[:20];r['native_label']['custom_id']=r['id'];r['native_label']['query']=r['query'];r['native_label']['ground_truth_command']=shlex.join(r['argv']);r['target']='<output>\n'+shlex.join(r['argv'])+'\n</output>';out[split].append(r)
    families={s:{r['constraint_group'] for r in rows} for s,rows in out.items()};assert all(not families[a]&families[b] for a,b in itertools.combinations(families,2))
    prior.write(target,out);prior.write(DATA/'data-build-audit.json',{'source':str(prior.DATA/'fixtures.json'),'source_224_linux_checks_passed':True,'refinement':'Explicit onedir/onefile and console/windowed contrast, with independent mode constraints and negative controls; no model outputs used to allocate families. V1 retained unchanged.','rows':{s:len(rr) for s,rr in out.items()},'families':{s:len(g) for s,g in families.items()},'quality':'AI_AUTHORED_V2_PENDING_LINUX_VALIDATION','protected_confirm384_opened':False})
    return {'rows':{s:len(rr) for s,rr in out.items()},'families':{s:len(g) for s,g in families.items()}}

if __name__=='__main__':print(json.dumps(generate(),indent=2))
