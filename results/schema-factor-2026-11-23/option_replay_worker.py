"""Replay two independent edits on completed schema answers using inert databases."""
import gzip
import hashlib
import json
import re
import shlex
import shutil
from oracle import INPUT,ROOT,setup,run
from kali_framed_artifacts_20261117 import emit

DEFAULTS = {'--default-values', '--no-default-values'}
FLAGS = {'--'+prefix+field for prefix in ('','no-') for field in
         ('drop-table','not-null','not-empty','comments','indexes','relations','default-values')}
# The native tool really spells this single negative option with an underscore.
# Map visually similar forms to the documented spelling and preserve every valid token.
CANON = {a:('--no-not_empty' if a=='--no-not-empty' else a) for a in FLAGS}
def replay(row,tag,folders,ledger):
    if not row['ended'] or not row['closed']:
        return {'status':'incomplete'}
    try:
        obj=json.loads(row['visible'])
        argv=shlex.split(obj['command'])
        if not argv or argv[0] not in ('mdb-schema','/usr/bin/mdb-schema'):
            return {'status':'other-command'}
    except (ValueError,KeyError,TypeError):
        return {'status':'no-command'}
    filename='temp.mdb' if tag=='original' else 'catalog.mdb'
    args=[filename if a=='./'+filename else a for a in argv[1:]]
    flags=[a for a in args if a!=filename]
    if args.count(filename)!=1 or any(not re.fullmatch(r'--[a-z_-]+',a) or a.replace('_','-') not in FLAGS for a in flags):
        return {'status':'outside-replay'}
    required='--default-values' if tag in ('opposite','distractor') else '--no-default-values'
    def corrected(spelling,direction):
        values=[CANON[a.replace('_','-')] for a in flags] if spelling else flags.copy()
        if direction:
            # Only edit the condition flag. Preserve every unrelated option.
            # Explicitly insert the required spelling even if the original omitted it.
            values=[a for a in values if a.replace('_','-') not in DEFAULTS]+[required]
        return ['mdb-schema',*values,filename]
    forms={}
    for key,spelling,direction in [('literal',False,False),('spelling',True,False),('condition',False,True),('both',True,True)]:
        argv=corrected(spelling,direction)
        hits=[]
        for folder,ref in zip(folders,ledger[tag]):
            r=run(argv,folder)
            hits.append(r['rc']==0 and hashlib.sha256(r['out'].encode()).hexdigest()==ref['expected_sha256'])
        forms[key]=all(hits)
    return dict(status='replayed',underscore_tokens=sum('_' in a for a in flags),forms=forms)

def main():
    plan=json.loads((INPUT/'draws.json').read_text())
    folders=[setup(0),setup(1),ROOT/'defaults']
    folders[-1].mkdir()
    (folders[-1]/'temp.mdb').write_bytes(gzip.decompress((INPUT/'third.gz').read_bytes()))
    for folder in folders:shutil.copyfile(folder/'temp.mdb',folder/'catalog.mdb')
    results={arm:{s:{tag:replay(row,tag,folders,plan['ledger']) for tag,row in draw.items()}
                  for s,draw in seeds.items()} for arm,seeds in plan['draws'].items()}
    emit(results,'EDITS')
if __name__=='__main__':main()
