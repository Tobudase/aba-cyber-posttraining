"""Fixture preflight for TRAIN references; fixed local utilities, no shell eval.

This records reference executability and independently specified postconditions.
Unknown/unsupported tasks never become functional successes just by returning 0.
"""
import base64,gzip,hashlib,json,os,shlex,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path

def run(argv,cwd=None,timeout=30):
    try:
        p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=timeout)
        return {'rc':p.returncode,'stdout':p.stdout.decode(errors='replace')[:100000],'stderr':p.stderr.decode(errors='replace')[:12000]}
    except subprocess.TimeoutExpired:return {'rc':None,'stdout':'','stderr':'timeout'}
def must(argv,cwd=None,timeout=180):
    r=run(argv,cwd,timeout);assert r['rc']==0,(argv,r);return r

def main():
    began=time.monotonic();os.environ['DEBIAN_FRONTEND']='noninteractive'
    must(['apt-get','update','-qq'])
    must(['apt-get','install','-y','--no-install-recommends','build-essential','git','libssl-dev','llvm-14','llvm-14-dev','clang-14','binutils-mingw-w64-x86-64'],timeout=500)
    source=Path('/scratch/readpe');must(['git','clone','--depth','1','--branch','0.85.1','https://github.com/mentebinaria/readpe.git',str(source)])
    revision=must(['git','rev-parse','HEAD'],source)['stdout'].strip();assert revision=='d1e885a271de3477bea212508be88aecff171a26'
    must(['make','-j2'],source,240);must(['make','install'],source);must(['ldconfig'])
    root=Path('/scratch/fixtures');root.mkdir()
    (root/'elf.s').write_text('.text\n.globl _Z10audit_funcv\n_Z10audit_funcv:\n call _Z11external_fni\n ret\n.size _Z10audit_funcv, .-_Z10audit_funcv\n.globl small_symbol\nsmall_symbol:\n ret\n.size small_symbol, .-small_symbol\n.comm common_symbol,16,8\n')
    must(['as','--64','-o','mangled.o','elf.s'],root)
    (root/'library.c').write_text('extern int puts(const char*); int audit_export(void) {return puts("audit");}\n')
    must(['gcc','-g','-fPIC','-shared','-o','debug.obj','library.c'],root)
    (root/'program.s').write_text('.text\n.globl entry\nentry:\n ret\n.globl audit_export\naudit_export:\n mov $9, %eax\n ret\n')
    must(['x86_64-w64-mingw32-as','-o','program.o','program.s'],root)
    must(['x86_64-w64-mingw32-ld','--entry','entry','--section-start','.text=0x140002000','--export-all-symbols','-o','fixture.exe','program.o'],root)
    (root/'macho.c').write_text('int macho_symbol(void) {return 7;}\n')
    must(['clang-14','-target','x86_64-apple-darwin','-c','-o','app.macho','macho.c'],root)
    (root/'base.ll').write_text('define i32 @audit() {\n ret i32 7\n}\n')
    for name in ['driver.ll','test.ll']:(root/name).write_bytes((root/'base.ll').read_bytes())
    for name in ['file1.o','file2.o','final.o']:(root/name).write_bytes((root/'mangled.o').read_bytes())
    for name in ['unknown.exe','loader.exe','ransomware.bin','app.exe','firmware.exe','exploit.exe']:(root/name).write_bytes((root/'fixture.exe').read_bytes())
    tools={n:'/usr/local/bin/'+n for n in ['pepack','pescan','readpe']}
    tools.update({n:'/usr/bin/'+n+'-14' for n in ['llvm-nm','llvm-readelf','llvm-size','llvm-as']})
    helptext={n:run([path,'--help'],root) for n,path in tools.items()}
    import shutil,getopt
    tools.update({'nm':'/usr/bin/nm','readelf':'/usr/bin/readelf','size':'/usr/bin/size','llvm-config':'/usr/bin/llvm-config-14','llvm-tblgen':'/usr/bin/llvm-tblgen-14'})
    cookie_source=Path('/input/galleta.c');assert hashlib.sha256(cookie_source.read_bytes()).hexdigest()==Path('/input/galleta.sha256').read_text().strip()
    must(['gcc','-include','string.h','-include','stdlib.h',str(cookie_source),'-lm','-o','/scratch/galleta'])
    tools['galleta']='/scratch/galleta'
    (root/'Instructions.td').write_text('class Opcode; class Other; def ADD : Opcode; def SUB : Opcode; def ZZZ : Other;\n')
    references=json.loads(Path('/input/references.json').read_text());provided=json.loads(Path('/input/commands.json').read_text());results=[];controls=[]
    def argv_for(command):
        command=command.replace("$'\\n'",shlex.quote('\n'))
        try:argv=shlex.split(command)
        except ValueError:return None
        if not argv or argv[0] not in tools:return None
        if any('/' in a or '..'==a or any(c in a for c in ['\x00','`','$',';','|','&','>','<','*','?','[',']']) for a in argv[1:]):return None
        if any(a.startswith('-') and any(s in a.split('=')[0] for s in ['plugin','load','exec','script']) for a in argv[1:]):return None
        return argv
    def family(r):
        label=r['native_label'];tool=label['tool_name'];a=shlex.split(label['ground_truth_command'])
        if tool=='readpe' and '--imports' in a:return None
        if tool=='llvm-size' and '--common' not in a:return None
        if tool=='llvm-tblgen' and '--print-enums' not in a:return None
        return tool if tool in tools else None
    def prepare_files(dest,variant):
        dest.mkdir();
        for f in root.iterdir():
            if f.is_file():shutil.copy2(f,dest/f.name)
        if variant==1:
            text=(dest/'elf.s').read_text().replace(' call _Z11external_fni',' call _Z11external_fni\n call _Z11external_fni').replace('small_symbol:\n ret','small_symbol:\n nop\n ret').replace('common_symbol,16','common_symbol,24')
            (dest/'elf.s').write_text(text);must(['as','--64','-o','mangled.o','elf.s'],dest)
            for name in ['file1.o','file2.o','final.o']:shutil.copy2(dest/'mangled.o',dest/name)
        cookie='audit_cookie\nVALUE'+str(variant)+'\nexample.invalid/\n0\n0\n0\n0\n0\n*\n'
        for r in references:
            if r['native_label']['tool_name']=='galleta':
                filename=shlex.split(r['native_label']['ground_truth_command'])[-1];assert Path(filename).name==filename;(dest/filename).write_text(cookie)
        (dest/'userdb.txt').write_text('[AuditFixtureMarker]\nsignature = C3 B8 09 00 00 00 C3\nep_only = true\n')
        (dest/'otherdb.txt').write_text('[OtherFixtureMarker]\nsignature = DE AD BE EF\nep_only = true\n')
    def check(r,argv,result,cwd,variant):
        if result['rc']!=0:return False
        label=r['native_label'];tool=label['tool_name'];a=shlex.split(label['ground_truth_command']);text=result['stdout']
        specifications={
          'galleta':('d:',[]),
          'pepack':('d:f:V',['database=','format=','version','help']),
          'pescan':('f:vV',['format=','verbose','version','help']),
          'readpe':('AHSf:dh:ieV',['all','all-headers','all-sections','format=','dirs','header=','imports','exports','version','help']),
          'llvm-nm':('aACDgPpSrnuUf:',['defined-only','format=','print-size','size-sort','demangle','no-demangle','numeric-sort','extern-only','undefined-only','print-file-name','dynamic','help','version']),
          'llvm-readelf':('aChlSsnrVdWN',['demangle','relocs','relocations','notes','version-info','dynamic-table','dynamic','wide','sections','symbols','help','version']),
          'llvm-size':('ABdotx',['common','format=','totals','radix=','arch=','help','version']),
          'llvm-as':('fo:',['data-layout=','disable-verify','help','version']),
          'llvm-config':('', ['libnames','shared-mode','link-shared','link-static','libs','libfiles','components','version']),
          'llvm-tblgen':('o:I:D:',['print-enums','class=','help','version','gen-register-info'])}
        try:options,positionals=getopt.gnu_getopt(argv[1:],*specifications[tool])
        except getopt.GetoptError:return None
        expected_positions=label.get('positional_args') or []
        if isinstance(expected_positions,str):expected_positions=json.loads(expected_positions)
        if positionals!=expected_positions:return False
        if tool=='galleta' and argv[-1]!=expected_positions[-1]:return False
        if tool=='pepack' and any(k in ['-d','--database'] and value not in ['userdb.txt','./userdb.txt'] for k,value in options):return False
        if tool=='pescan' and any(k in ['-v','--verbose'] for k,value in options):return False
        if tool=='llvm-readelf' and 'long' in label['query'].lower() and any(a.startswith('-') and not a.startswith('--') for a in argv[1:]):return False
        if tool=='galleta':
            d='\n' if 'newline' in label['query'] else a[2]
            header=d.join(['SITE','VARIABLE','VALUE','CREATION TIME','EXPIRE TIME','FLAGS'])+'\n'
            prefix=d.join(['example.invalid/','audit_cookie','VALUE'+str(variant)])+d
            return header in text and prefix in text
        if tool=='pepack':
            fmt=a[a.index('--format')+1]
            if fmt=='xml':
                try:return ET.fromstring(text).find(".//attribute[@name='packer']").text=='AuditFixtureMarker'
                except (ET.ParseError,AttributeError):return False
            if fmt=='html':return '<html ' in text and '</html>' in text and 'AuditFixtureMarker' in text
            return 'AuditFixtureMarker' in text and not text.lstrip().startswith('<')
        if tool=='pescan':return 'file entropy:' in text and 'entrypoint:' in text and not text.lstrip().startswith('<')
        if tool=='readpe':
            if '--header' in a:return 'Optional/Image header' in text and 'Data directories' in text and 'DOS Header' not in text
            return 'Sections' in text and 'Data directories' in text and 'DOS Header' not in text
        if tool=='llvm-nm':
            lines=[line.split('|') for line in text.splitlines() if '|' in line and not line.startswith('Name')]
            try:return 'Name' in text and 'Size' in text and '_Z11external_fni' not in text and [int(x[4],16) for x in lines]==([1,6,16] if variant==0 else [2,11,24])
            except (ValueError,IndexError):return False
        if tool=='llvm-readelf':
            if '--relocs' in a:return 'external_fn(int)' in text and 'R_X86_64_PLT32' in text
            return all(s in text for s in ['Dynamic section','Version symbols section','Displaying notes found in:'])
        if tool=='llvm-size':
            lines=[line.split() for line in text.splitlines() if '(TOTALS)' in line]
            expected=[14,0,32,46] if variant==0 else [26,0,48,74]
            try:return 'text' in text and 'bss' in text and len(lines)==1 and [int(x) for x in lines[0][:4]]==expected and all(f in text for f in ['file1.o','file2.o'])
            except ValueError:return False
        if tool=='llvm-as':
            filename='driver.bc' if 'driver.ll' in a else 'test.bc';p=cwd/filename
            if not p.exists() or p.read_bytes()[:4]!=b'BC\xc0\xde' or '-f' not in argv:return False
            if 'driver.ll' in a:
                dump=run(['/usr/bin/llvm-dis-14',str(p),'-o','-'],cwd)
                return 'target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"' in dump['stdout']
            return True
        if tool=='llvm-config':return any(x in text.splitlines() for x in ['shared','static']) and any('libLLVM' in x and '/' not in x for x in text.split())
        if tool=='llvm-tblgen':return ('--print-enums','') in options and ('--class','Opcode') in options and 'ADD' in text and 'SUB' in text and 'ZZZ' not in text
        return False
    def negative(r):
        label=r['native_label'];a=argv_for(label['ground_truth_command']);tool=label['tool_name']
        if tool=='galleta':return ['galleta',a[-1]]
        if tool=='pepack':b=list(a);b[b.index('--format')+1]='html' if b[b.index('--format')+1]!='html' else 'xml';return b
        if tool=='pescan':return ['pescan','--format','xml',a[-1]]
        if tool=='readpe':
            if '--header' in a:b=list(a);b[b.index('--header')+1]='coff';return b
            return [x for x in a if x!='--dirs']
        if tool=='llvm-nm':return ['llvm-nm','--defined-only','--format=posix','--print-size','--size-sort',a[-1]]
        if tool=='llvm-readelf':return [x for x in a if x!=('--demangle' if '--relocs' in a else '--version-info')]
        if tool=='llvm-size':return [x for x in a if x!='--common']
        if tool=='llvm-as':return [x for x in a if x!='-f']
        if tool=='llvm-config':return ['llvm-config','--shared-mode','bcreader','engine']
        if tool=='llvm-tblgen':return ['llvm-tblgen','--print-enums','--class=Other','Instructions.td']
        raise ValueError(tool)
    for r in references:
        if not family(r):continue
        commands={'reference':r['native_label']['ground_truth_command'],**provided.get(r['id'],{})}
        for variant in [0,1]:
            for index,(role,command) in enumerate(commands.items()):
                argv=argv_for(command)
                if argv is None:
                    results.append({'id':r['id'],'role':role,'variant':variant,'status':'UNKNOWN_UNSUPPORTED_COMMAND','task_pass':False});continue
                dest=Path('/scratch')/('case-'+r['id']+'-'+str(variant)+'-'+str(index));prepare_files(dest,variant)
                observed=run([tools[argv[0]],*argv[1:]],dest)
                ok=check(r,argv,observed,dest,variant)
                results.append({'id':r['id'],'role':role,'variant':variant,'status':'UNKNOWN_OPTION_SYNTAX' if ok is None else 'PASS_SUPPORTED_SCOPE' if ok else 'FAIL_CHECK','task_pass':ok is True,'argv':argv,**observed})
            dest=Path('/scratch')/('negative-'+r['id']+'-'+str(variant));prepare_files(dest,variant);a=negative(r);observed=run([tools[a[0]],*a[1:]],dest);ok=check(r,a,observed,dest,variant)
            controls.append({'id':r['id'],'variant':variant,'task_pass':ok,'argv':a,**observed})
            if r['native_label']['tool_name'] in ['pepack','pescan']:
                dest=Path('/scratch')/('extra-negative-'+r['id']+'-'+str(variant));prepare_files(dest,variant);a=argv_for(r['native_label']['ground_truth_command'])
                if r['native_label']['tool_name']=='pepack':a.extend(['--database','otherdb.txt'])
                else:a.insert(1,'--verbose')
                observed=run([tools[a[0]],*a[1:]],dest);ok=check(r,a,observed,dest,variant)
                controls.append({'id':r['id'],'variant':variant,'type':'non_output_constraint','task_pass':ok,'argv':a,**observed})
    report={'status':'COMPLETE_PENDING_HOST_AUDIT','results':results,'negative_controls':controls,'scope':'Fixture task postconditions plus documented required -f flag for llvm-as; not arbitrary-command semantic equivalence','input_sha256':hashlib.sha256(Path('/input/references.json').read_bytes()).hexdigest(),'commands_sha256':hashlib.sha256(Path('/input/commands.json').read_bytes()).hexdigest(),'readpe_revision':revision,'LLVM':'14','galleta_source_sha256':hashlib.sha256(cookie_source.read_bytes()).hexdigest(),'model_calls':0,'GPU':0,'target_binaries_executed':0,'seconds':time.monotonic()-began}
    import sys;sys.path.insert(0,'/input');from kali_framed_artifacts_20261117 import emit;emit(report,'CURRICULUM_REPLAY_FIT_ARTIFACT')
    print('INDEPENDENT_ACCEPTANCE_COMPLETE',flush=True)
if __name__=='__main__':main()
