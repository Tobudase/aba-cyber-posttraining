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
    import collections,getopt,re
    for name in ['llvm-readobj','llvm-dis','llvm-bcanalyzer','llvm-objdump','llvm-strings']:tools[name]='/usr/bin/'+name+'-14'
    (root/'elf.s').write_text('.text\n.globl _Z10audit_funcv\n_Z10audit_funcv:\n call _Z11external_fni\n ret\n.size _Z10audit_funcv, .-_Z10audit_funcv\n.globl small_symbol\nsmall_symbol:\n ret\n.size small_symbol, .-small_symbol\nlocal_private:\n nop\n.size local_private, .-local_private\n.comm common_symbol,16,8\n')
    must(['as','--64','-o','elf.o','elf.s'],root)
    shutil.copy2(root/'debug.obj',root/'shared.so')
    (root/'module.ll').write_text('@audit_text = private constant [8 x i8] c"AuditIR\\00"\n@audit_global = global i32 7\ndefine i32 @audit_fixture(i32 %value) {\nentry:\n %added = add i32 %value, 7\n ret i32 %added\n}\n!llvm.module.flags = !{!0}\n!0 = !{i32 1, !"wchar_size", i32 4}\n')
    must(['/usr/bin/llvm-as-14','module.ll','-o','module.bc'],root)
    (root/'library.s').write_text('.text\n.globl audit_import\naudit_import:\n mov $7, %eax\n ret\n')
    (root/'program.s').write_text('.text\n.globl entry\nentry:\n call *__imp_audit_import(%rip)\n ret\n.globl audit_export\naudit_export:\n mov $9, %eax\n ret\n')
    must(['x86_64-w64-mingw32-as','-o','library.o','library.s'],root)
    must(['x86_64-w64-mingw32-ld','--dll','--entry','audit_import','--export-all-symbols','--out-implib','audit.lib','-o','audit.dll','library.o'],root)
    must(['x86_64-w64-mingw32-as','-o','program.o','program.s'],root)
    must(['x86_64-w64-mingw32-ld','--entry','entry','--export-all-symbols','-o','pe.exe','program.o','audit.lib'],root)
    candidates=json.loads(Path('/input/candidates.json').read_text());extra=json.loads(Path('/input/commands.json').read_text()) if Path('/input/commands.json').exists() else {}
    def prepare(dest,variant):
        dest.mkdir()
        for f in root.iterdir():
            if f.is_file():shutil.copy2(f,dest/f.name)
        if variant:
            s=(dest/'elf.s').read_text().replace(' call _Z11external_fni',' call _Z11external_fni\n call _Z11external_fni').replace('small_symbol:\n ret','small_symbol:\n nop\n ret').replace('common_symbol,16','common_symbol,24');(dest/'elf.s').write_text(s);must(['as','--64','-o','elf.o','elf.s'],dest)
            s=(dest/'module.ll').read_text().replace('i32 7','i32 9').replace('%value, 7','%value, 9');(dest/'module.ll').write_text(s);must(['/usr/bin/llvm-as-14','module.ll','-o','module.bc'],dest)
        # Independent file bytes for PE, shared library and enum fixtures too.
        if variant:
            import struct
            data=bytearray((dest/'pe.exe').read_bytes());offset=struct.unpack_from('<I',data,0x3c)[0];struct.pack_into('<I',data,offset+8,123456789);(dest/'pe.exe').write_bytes(data)
            (dest/'library.c').write_text((dest/'library.c').read_text().replace('"audit"','"audit_variant"'))
            must(['gcc','-g','-fPIC','-shared','-o','shared.so','library.c'],dest)
            (dest/'Instructions.td').write_text((dest/'Instructions.td').read_text().replace('def ADD','def MUL').replace('def SUB','def DIV'))
        for name in ['file1.o','file2.o']:shutil.copy2(dest/'elf.o',dest/name)
        (dest/'cookies.dat').write_text('audit_cookie\nVALUE'+str(variant)+'\nexample.invalid/\n0\n0\n0\n0\n0\n*\n')
        (dest/'text.bin').write_bytes(b'\x00'*(16 if variant==0 else 32)+b'AuditLongString123456\x00EightLen\x00TwelveString\x00seven77\x00midlen\x00tiny\x00')
        (dest/'userdb.txt').write_text('[AuditFixtureMarker]\nsignature = FF 15 ?? ?? ?? ?? C3\nep_only = true\n')
        (dest/'otherdb.txt').write_text('[OtherFixtureMarker]\nsignature = DE AD BE EF\nep_only = true\n')
    def validated(argv):
        if not argv or argv[0] not in tools:return False
        if any('/' in a or a=='..' or any(c in a for c in ['\x00','`','$',';','|','&','>','<','*','?','[',']']) for a in argv[1:]):return False
        return not any(a.startswith('-') and any(s in a.split('=')[0] for s in ['plugin','load','exec','script']) for a in argv[1:])
    def operands(row,argv):
        specs={
          'llvm-readelf':('aChlSsnrVdW',['header','file-header','sections','section-headers','symbols','syms','relocs','relocations','dynamic-table','dynamic','notes','version-info','demangle','wide']),
          'llvm-readobj':('hSsCr',['file-header','file-headers','section-headers','sections','syms','symbols','relocs','relocations','needed-libs','demangle','elf-output-style=']),
          'llvm-nm':('aACDgPpSrnuUf:',['defined-only','undefined-only','extern-only','demangle','format=','print-size','size-sort','numeric-sort','no-sort']),
          'llvm-size':('ABdotx',['format=','common','totals','radix=']),
          'llvm-as':('fo:',['data-layout=','disable-verify']),
          'llvm-dis':('o:',['show-annotations']),
          'llvm-bcanalyzer':('',['dump','dump-blockinfo','disable-histogram','non-symbolic','show-binary-blobs']),
          'llvm-objdump':('dtrshC',['disassemble','symbols','syms','headers','section-headers','symbol-table','section-headers','reloc','relocations','full-contents','demangle']),
          'llvm-strings':('an:t:',['all','bytes=','radix=','print-file-name']),
          'readpe':('AHSf:dh:ie',['all','all-headers','all-sections','format=','dirs','header=','imports','exports']),
          'pepack':('d:f:',['database=','format=']),
          'pescan':('f:v',['format=','verbose']),
          'galleta':('d:',[]),
          'llvm-config':('', ['shared-mode','libnames','libs','libfiles','components','link-shared','link-static']),
          'llvm-tblgen':('o:I:D:',['print-enums','class='])}
        try:options,pos=getopt.gnu_getopt(argv[1:],*specs[row['tool']])
        except getopt.GetoptError:return None,None
        return options,pos
    def postcondition(row,argv,result,cwd,variant):
        if result['rc']!=0:return False
        if argv[0]!=row['tool']:return False
        options,pos=operands(row,argv)
        if options is None:return None
        _,expected_pos=operands(row,row['argv'])
        if pos!=expected_pos:return False
        if row['tool']=='galleta' and argv[-1]!='cookies.dat':return False
        text=result['stdout'];kind=row['kind'];needs=row['needs'];textsize=8 if not variant else 14;common=16 if not variant else 24
        if kind.startswith('elf_'):
            observed={'header':'ELF Header:' in text,'sections':'Section Headers:' in text,'symbols':"Symbol table '" in text,'relocations':'Relocation section' in text,'dynamic':'Dynamic section' in text,'notes':'Displaying notes found in:' in text,'versions':'Version symbols section' in text}
            if kind=='elf_demangle':return observed['relocations'] and 'external_fn(int)' in text and '_Z11external_fni' not in text
            return all(observed[n] for n in needs) and all(not yes for n,yes in observed.items() if n not in needs)
        if kind.startswith('readobj_'):
            observed={'header':'ElfHeader {' in text,'sections':'Sections [' in text,'symbols':'Symbols [' in text,'relocations':'Relocations [' in text,'libraries':'NeededLibraries [' in text}
            if kind=='readobj_demangle':return observed['symbols'] and 'external_fn(int)' in text and '_Z11external_fni' not in text
            return all(observed[n] for n in needs) and ('libc.so.6' in text if 'libraries' in needs else True)
        if kind.startswith('nm_'):
            if kind=='nm_defined':return 'small_symbol' in text and 'local_private' in text and '_Z11external_fni' not in text
            if kind=='nm_undefined':return '_Z11external_fni' in text and 'small_symbol' not in text and 'local_private' not in text
            if kind=='nm_external':return 'small_symbol' in text and '_Z11external_fni' in text and 'local_private' not in text
            if kind=='nm_demangle':return 'external_fn(int)' in text and '_Z11external_fni' not in text and 'small_symbol' not in text
            if kind=='nm_sysv':return 'Name' in text and 'Size' in text and 'Class' in text and '|' in text and 'small_symbol' in text and '_Z11external_fni' not in text
            if kind=='nm_posix':return any(l.startswith('small_symbol ') for l in text.splitlines()) and '_Z11external_fni' not in text
            numeric=[];sizes=[]
            for l in text.splitlines():
                parts=l.split()
                if len(parts)<3:continue
                try:
                    numeric.append(int(parts[0],16))
                    if len(parts)==4:sizes.append(int(parts[1],16))
                except ValueError:continue
            if kind=='nm_numeric_sort':
                expected={'_Z10audit_funcv':0,'small_symbol':6 if not variant else 11,'local_private':7 if not variant else 13,'common_symbol':16 if not variant else 24}
                entries=[l.split() for l in text.splitlines() if len(l.split())>=3]
                try: correct=all(int(l[0],16)==expected[l[-1]] for l in entries) and {l[-1] for l in entries}==set(expected)
                except (KeyError,ValueError):correct=False
                return correct and len(numeric)==4 and numeric==sorted(numeric) and '_Z11external_fni' not in text
            return len(sizes)==4 and sizes==sorted(sizes) and sorted(sizes)==([1,1,6,16] if not variant else [1,2,11,24]) and '_Z11external_fni' not in text
        if kind.startswith('size_'):
            if kind=='size_common_totals':
                lines=[l.split() for l in text.splitlines() if '(TOTALS)' in l]
                try:return len(lines)==1 and [int(x) for x in lines[0][:4]]==[2*textsize,0,2*common,2*(textsize+common)] and all(f in text for f in ['file1.o','file2.o'])
                except ValueError:return False
            if kind=='size_sysv':return 'section' in text and 'addr' in text and any(l.split()[:2]==['.text',str(textsize)] for l in text.splitlines())
            return '0x'+format(textsize,'x') in text and any(l.split() in [['text','data','bss','dec','hex','filename'],['text','data','bss','hex','filename']] for l in text.splitlines())
        if kind.startswith('as_'):
            path=cwd/'assembled.bc'
            if not path.exists() or path.read_bytes()[:4]!=b'BC\xc0\xde':return False
            output=run(['/usr/bin/llvm-dis-14',str(path),'-o','-'],cwd)['stdout']
            return '@audit_fixture' in output and ('target datalayout = "e-p:64:64"' in output if kind=='as_layout' else True)
        if kind.startswith('dis_'):
            if kind=='dis_output':return (cwd/'decoded.ll').exists() and '@audit_fixture' in (cwd/'decoded.ll').read_text()
            if kind=='dis_stdout':return '@audit_fixture' in text and '@audit_global' in text
            return '@audit_fixture' in text and '[#uses=' in text
        if kind.startswith('bc_'):
            dump='<MODULE_BLOCK' in text
            if kind=='bc_dump':return dump
            if kind=='bc_no_histogram':return dump and 'Record Histogram:' not in text
            return dump and '<BLOCKINFO_BLOCK NumWords=' in text and 'Record Histogram:' not in text
        if kind.startswith('objdump_'):
            observed={'disassembly':'Disassembly of section .text:' in text,'symbols':'SYMBOL TABLE:' in text,'sections':'Sections:' in text,'relocations':('RELOCATION RECORDS FOR [' in text or 'R_X86_64_PLT32' in text),'contents':'Contents of section .text:' in text}
            if kind=='objdump_demangle':return observed['symbols'] and 'audit_func()' in text and '_Z10audit_funcv' not in text
            return all(observed[n] for n in needs)
        if kind.startswith('strings_'):
            good=all(t in text for t in ['AuditLongString123456','EightLen','TwelveString']) and all(t not in text for t in ['seven77','midlen','tiny'])
            if kind=='strings_min':return good
            return good and re.search(r'^\s*'+('10' if not variant else '20')+r'\s+AuditLongString123456',text,re.M) is not None
        if kind.startswith('pe_'):
            if kind=='pe_import_export':
                try:
                    tree=ET.fromstring(text);names={e.attrib.get('name') for e in tree.iter()}
                    return {'Imported functions','Exported functions'}<=names and not {'DOS Header','Sections'}&names and 'audit_import' in text and 'audit_export' in text
                except ET.ParseError:return False
            observed={'dos':'DOS Header' in text,'coff':'COFF/File header' in text,'optional':'Optional/Image header' in text,'directories':'Data directories' in text,'sections':'Sections' in text,'imports':'Imported functions' in text,'exports':'Exported functions' in text}
            desired=needs if kind=='pe_header' else ['directories'] if kind=='pe_directories' else ['sections']
            return all(observed[n] for n in desired) and all(not v for n,v in observed.items() if n not in desired)
        if kind=='packer':
            if any(k in ['-d','--database'] and v!='userdb.txt' for k,v in options):return False
            fmt=needs[0]
            if not any(k in ['-f','--format'] and v==fmt for k,v in options):return False
            if fmt=='xml':
                try:return ET.fromstring(text).find(".//attribute[@name='packer']").text=='AuditFixtureMarker'
                except (ET.ParseError,AttributeError):return False
            if fmt=='html':return '<html ' in text and '</html>' in text and 'AuditFixtureMarker' in text
            return 'AuditFixtureMarker' in text and not text.lstrip().startswith('<')
        if kind=='scan_default':return 'file entropy:' in text and 'entrypoint:' in text and not text.lstrip().startswith('<') and not any(k in ['-v','--verbose'] for k,v in options)
        if kind=='scan_xml':
            try:return ET.fromstring(text).find(".//attribute[@name='file entropy']") is not None
            except ET.ParseError:return False
        if kind=='cookie':
            d=needs[0];header=d.join(['SITE','VARIABLE','VALUE','CREATION TIME','EXPIRE TIME','FLAGS'])+'\n';prefix=d.join(['example.invalid/','audit_cookie','VALUE'+str(variant)])+d
            return header in text and prefix in text
        if kind=='config_link':return any(s in text.splitlines() for s in ['shared','static']) and any('libLLVM' in s and '/' not in s for s in text.split())
        if kind=='tablegen_enum':return all(x in text for x in (['ADD','SUB'] if not variant else ['MUL','DIV'])) and 'ZZZ' not in text
        raise ValueError(kind)
    results=[];last=None
    for index,row in enumerate(candidates):
        for variant in [0,1]:
            commands={'reference':row['argv'],'negative':row['negative_argv']}
            if row['tool']=='pepack':commands['negative_wrong_database']=['pepack','--database','otherdb.txt','--format',row['needs'][0],'pe.exe']
            if row['tool']=='pepack':commands['negative_no_explicit_format']=['pepack','pe.exe']
            if row['kind'].startswith('strings_'):commands['negative_minimum9']=['llvm-strings','-n','9',*(['-t','x'] if row['kind']=='strings_offsets' else []),'text.bin']
            if row['kind']=='size_hex':commands['negative_sysv_hex']=['llvm-size','-A','-x','elf.o']
            if row['kind']=='pe_header':commands['negative_extra_imports']=[*row['argv'][:-1],'--imports',row['argv'][-1]]
            if row['kind']=='scan_default':commands['negative_verbose']=['pescan','--verbose','pe.exe']
            if row['tool'] not in ['llvm-config','galleta']:commands['negative_wrong_input']=[a if a not in ['elf.o','module.bc','pe.exe','text.bin','shared.so','module.ll','Instructions.td','file1.o','file2.o'] else 'missing-input.bin' for a in row['argv']]
            for role,command in extra.get(row['id'],{}).items():
                try:
                    if re.search(r'(?<!\S)~(?:\s|$)',command):commands[role]=[];continue
                    commands[role]=shlex.split(command.replace("$'\\n'",shlex.quote('\n')))
                except ValueError:commands[role]=[]
            for count,(role,argv) in enumerate(commands.items()):
                original_argv=list(argv)
                if argv and argv[0] in [tools[row['tool']],Path(tools[row['tool']]).name]:argv=[row['tool'],*argv[1:]]
                parse_argv=argv
                if argv and argv[0]==row['tool'] and row['tool'].startswith('llvm-'):
                    # Normalize parser spelling only; original argv is what the tool executes.
                    parsed=[]
                    for token in argv[1:]:
                        name=token.split('=',1)[0]
                        if name.startswith('-') and not name.startswith('--') and len(name)>2:
                            probe='--'+token[1:]
                            if operands(row,[argv[0],probe])[0] is not None:token=probe
                        parsed.append(token)
                    parse_argv=[argv[0],*parsed]
                if not validated(argv):results.append({'id':row['id'],'role':role,'variant':variant,'status':'UNKNOWN_UNSUPPORTED_COMMAND','pass':False,'original_argv':original_argv});continue
                dest=Path('/scratch')/('curriculum-'+str(index)+'-'+str(variant)+'-'+str(count));prepare(dest,variant);observed=run([tools[argv[0]],*argv[1:]],dest)
                ok=postcondition(row,parse_argv,observed,dest,variant)
                results.append({'id':row['id'],'role':role,'variant':variant,'status':'UNKNOWN_OPTION_SYNTAX' if ok is None else 'PASS' if ok else 'FAIL','pass':ok is True,'argv':argv,'original_argv':original_argv,'parse_argv':parse_argv,**observed})
        if index%8==7:print('CURRICULUM_VALIDATED '+str(index+1)+'/'+str(len(candidates)),flush=True)
    artifact={'status':'COMPLETE_PENDING_HOST_AUDIT','results':results,'source_sha256':hashlib.sha256(Path('/input/candidates.json').read_bytes()).hexdigest(),'commands_sha256':hashlib.sha256(Path('/input/commands.json').read_bytes()).hexdigest() if Path('/input/commands.json').exists() else None,'help':{n:run([path,'--help'],root) for n,path in tools.items()},'versions':must(['dpkg-query','-W','llvm-14','llvm-14-dev','binutils'])['stdout'],'readpe_revision':revision,'target_binaries_executed':0,'model_calls':0,'GPU':0,'seconds':time.monotonic()-began}
    print('VERIFIED_CURRICULUM_ARTIFACT='+base64.b64encode(gzip.compress(json.dumps(artifact).encode())).decode(),flush=True)
    print('VERIFIED_CURRICULUM_COMPLETE',flush=True)
if __name__=='__main__':main()
