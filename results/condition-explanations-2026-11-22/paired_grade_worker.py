"""Grade protocol and command behavior separately using the prevalidated read-only database fixtures."""
import hashlib,json,shlex,gzip,shutil
from pathlib import Path
from oracle import INPUT,ROOT,setup,run
from kali_framed_artifacts_20261117 import emit
def parse(visible):
    try:
        obj=json.loads(visible)
        if not isinstance(obj,dict):return None,False
        cmd=obj.get('command')
        return (cmd if isinstance(cmd,str) else None,
                set(obj)=={'command','explanation'} and isinstance(cmd,str) and bool(cmd.strip()) and isinstance(obj['explanation'],str) and bool(obj['explanation'].strip()))
    except ValueError:
        dec=json.JSONDecoder();remaining=visible.strip();cmds=[]
        try:
            while remaining:
                item,n=dec.raw_decode(remaining)
                if not isinstance(item,dict):return None,False
                if 'command' in item:cmds.append(item['command'])
                remaining=remaining[n:].lstrip()
        except ValueError:return None,False
        return (cmds[0],False) if len(cmds)==1 and isinstance(cmds[0],str) else (None,False)
def grade(row,tag,fixtures,ledger):
    cmd,fmt=parse(row['visible'])
    fmt=bool(row['closed'] and row['ended'] and fmt)
    result=dict(tokens=row['tokens'],ended=row['ended'],format=fmt,behavior=False,strict=False)
    if not row['ended']:return dict(result,issue='truncated')
    if not cmd:return dict(result,issue='no-unambiguous-command')
    try:args=shlex.split(cmd)
    except ValueError:return dict(result,issue='invalid-command')
    if not args:return dict(result,issue='empty-command')
    if args[0]=='/usr/bin/mdb-schema':args[0]='mdb-schema'
    args=['catalog.mdb' if t=='./catalog.mdb' else t for t in args]
    if args[0]!='mdb-schema' or args.count('catalog.mdb')!=1 or any(t!='catalog.mdb' and not t.startswith(('--no-','--not-','--comments','--indexes','--relations','--default-values','--drop-table')) for t in args[1:]):
        return dict(result,issue='unreviewed',argv=args)
    # Only ordinary switches, no paths or values are accepted. The reader's only input is the synthetic MDB.
    if any(t.startswith('-') and not all(c.isalpha() or c in '-_' for c in t) for t in args[1:]):return dict(result,issue='unreviewed',argv=args)
    hits=[];rcs=[];reverse=[]
    for reference,folder in zip(ledger[tag],fixtures):
        value=run(args,folder);rcs.append(value['rc'])
        h=hashlib.sha256(value['out'].encode()).hexdigest()
        hits.append(value['rc']==0 and h==reference['expected_sha256'])
        reverse.append(value['rc']==0 and h==reference['reversed_sha256'])
    behavior=all(hits)
    return dict(result,behavior=behavior,strict=behavior and fmt,fixture_matches=hits,reversed_fixture_matches=reverse,
                issue='pass' if behavior and fmt else ('format' if behavior else 'native-error' if any(rcs) else 'different-output'))
def main():
    plan=json.loads((INPUT/'draws.json').read_text())
    folders=[setup(0),setup(1),ROOT/'defaults'];folders[-1].mkdir()
    (folders[-1]/'temp.mdb').write_bytes(gzip.decompress((INPUT/'third.gz').read_bytes()))
    for d in folders:shutil.copyfile(d/'temp.mdb',d/'catalog.mdb')
    result={tag:{s:{kind:grade(r,kind,folders,plan['ledger']) for kind,r in cases.items()} for s,cases in ss.items()} for tag,ss in plan['draws'].items()}
    emit(result,'PAIRSCORES')
if __name__=='__main__':main()
