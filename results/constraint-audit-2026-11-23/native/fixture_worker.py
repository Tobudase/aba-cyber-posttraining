"""Native checks on inert ELF metadata; no output artifact is executed."""
import json, shlex, shutil, subprocess, tempfile, zlib
from pathlib import Path
from kali_framed_artifacts_20261117 import emit

def run(args, wd):
    exe=shutil.which(args[0]) or shutil.which(args[0]+'-14')
    return subprocess.run([exe,*args[1:]],cwd=wd,capture_output=True,timeout=12)

def observe(key,variant,args):
    with tempfile.TemporaryDirectory(dir='/scratch') as tmp:
        wd=Path(tmp)
        name={'7411':'main.exe','7500':'obj.o','7413':'combined.o'}[key]
        sym=f'witness_{variant}'
        asm=f'.text\n.global {sym}\n{sym}: .byte {32+variant}\n.local .Lsaved\n.Lsaved: .byte 17\n.local retained_local\nretained_local: .byte 23\n.section .debug_info.dwo,"e",@progbits\n.byte {42+variant}\n.section .debug_str.dwo,"eMS",@progbits,1\n.asciz "data{variant}"\n'
        (wd/'a.s').write_text(asm)
        assert run(['llvm-mc','-triple=x86_64-unknown-linux','-filetype=obj','-save-temp-labels','a.s','-o',name],wd).returncode==0
        (wd/'debug.info').write_bytes(f'benign debug payload {variant}'.encode())
        r=run(args,wd)
        def dump(file,section):
            dest=wd/'block'
            if dest.exists():dest.unlink()
            if not (wd/file).exists():return None
            rr=run(['llvm-objcopy','--dump-section',section+'=block',file],wd)
            return dest.read_bytes() if rr.returncode==0 and dest.exists() else None
        if key=='7411':
            data=dump('main_with_debuglink.exe','.gnu_debuglink')
            expected=b'debug.info\0'.ljust(12,b'\0')+zlib.crc32((wd/'debug.info').read_bytes()).to_bytes(4,'little')
            features=[data==expected,dump('main_with_debuglink.exe','.text')==bytes([32+variant,17,23])]
        elif key=='7413':
            features=[dump('debug.dwo','.debug_info.dwo')==bytes([42+variant]),dump('debug.dwo','.debug_str.dwo')==f'data{variant}\0'.encode(),dump(name,'.debug_info.dwo') is None,dump(name,'.debug_str.dwo') is None,dump(name,'.text')==bytes([32+variant,17,23])]
        else:
            syms=run(['llvm-nm','-a',name],wd).stdout
            features=[b'.Lsaved' not in syms,sym.encode() in syms,b'retained_local' in syms,dump(name,'.text')==bytes([32+variant,17,23])]
        return {'status':r.returncode,'features':features,'pass':r.returncode==0 and all(features)}
def main():
    inp=Path('/input')
    rows=json.loads((inp/'rows.json').read_text())
    draws=json.loads((inp/'answers.json').read_text()) if (inp/'answers.json').exists() else {}
    out={}
    for k,r in rows.items():
        gold=shlex.split(r['gold'])
        wrong={'7411':['llvm-objcopy','main.exe','main_with_debuglink.exe'],'7413':['llvm-objcopy','--extract-dwo','combined.o','debug.dwo'],'7500':['llvm-strip','--strip-debug','obj.o']}[k]
        helptext=run([gold[0],'--help'],Path('/scratch')).stdout.decode()
        checks=[{'gold':observe(k,v,gold),'wrong':observe(k,v,wrong)} for v in range(2)]
        ok=all(x['gold']['pass'] and not x['wrong']['pass'] and x['wrong']['status']==0 for x in checks)
        result=out[k]={'checks':checks,'ok':ok,'help':helptext,'scores':{}}
        for seed,ans in draws.get(k,{}).items():
            score='format'
            try:
                def unique(items):
                    assert len(items)==len(dict(items))
                    return dict(items)
                x=json.loads(ans['visible'],object_pairs_hook=unique)
                assert ans['ended'] and ans['closed'] and set(x)=={'command','explanation'} and all(isinstance(v,str) and v.strip() for v in x.values())
                a=shlex.split(x['command'])
                if a[0].removeprefix('/usr/bin/').removesuffix('-14')!=gold[0]:raise ValueError('unexpected-tool')
                permitted=set(gold[1:]+wrong[1:]+['-x','-X','--strip-dwo','--keep-section','.text','--add-gnu-debuglink','debug.info','-o','--discard-all'])
                for arg in gold[1:]:
                    permitted.update(arg.split('=',1))
                if any(arg not in permitted and not ('=' in arg and all(x in permitted for x in arg.split('=',1))) for arg in a[1:]):raise ValueError('unreviewed')
                observed=[observe(k,v,[gold[0],*a[1:]]) for v in range(2)]
                score='pass' if all(v['pass'] for v in observed) else 'different-behavior'
            except (KeyError,AssertionError,ValueError,TypeError,IndexError) as exc:
                if str(exc) in ('unreviewed','unexpected-tool'):score=str(exc)
            result['scores'][seed]=score
    emit(out,'EVIDENCE')
if __name__=='__main__':main()
