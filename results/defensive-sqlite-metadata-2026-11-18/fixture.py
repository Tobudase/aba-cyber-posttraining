"""Read-only SQLite metadata extraction from synthetic evidence files."""
import hashlib
import json
import random
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "private"
FIELDS = {
    "schema_generation": (40, 4, "schema_version"),
    "release_marker": (60, 4, "user_version"),
    "application_identifier": (68, 4, "application_id"),
    "number_of_free_pages": (36, 4, "freelist_count"),
    "page_size_bytes": (16, 2, "page_size"),
    "total_pages": (28, 4, "page_count"),
}
PRIMARY = list(FIELDS)[:4]
SIZES = [512, 1024, 2048, 4096, 65536]
SYSTEM = ('Examine the supplied SQLite evidence. Return a JSON object with integer fields '
          '"offset" (zero-based byte offset in the file), "width" (bytes), and "value" '
          '(field value in decimal). Put the JSON inside <answer>...</answer>.')
TEACHER = SYSTEM + (' Before your answer, provide a brief evidence citation in the form '
                     '<evidence>offset,width,rawhex</evidence> using decimal offset and width '
                     'and the exact contiguous hexadecimal bytes in file order, without spaces.')
def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def save(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n")
    tmp.replace(path)

def build():
    assert not DATA.exists()
    DATA.mkdir(mode=0o700)
    rng = random.Random(2026111803)
    records = []
    for split, count in [('train',32),('holdout',24),('replay',8),('retention',12)]:
        for idx in range(count):
            field = PRIMARY[idx % 4] if split in ('train','holdout') else list(FIELDS)[4+idx%2]
            offset,width,pragma = FIELDS[field]
            path = DATA / ('snapshot-%016x.db' % rng.getrandbits(64))
            with sqlite3.connect(path) as db:
                db.execute(f'pragma page_size={rng.choice(SIZES)}')
                db.execute('create table register (v blob)')
                db.execute('create table temporary_records (v blob)')
                db.execute('insert into register values (?)',(rng.randbytes(20),))
                db.execute('insert into temporary_records values (zeroblob(?))',(rng.randrange(12000,90000),))
                db.execute('drop table temporary_records')
                for var in ('application_id','user_version','schema_version'):
                    db.execute(f'pragma {var}={rng.randrange(2,64000)}')
                db.commit()
                value = db.execute('pragma '+pragma).fetchone()[0]
                assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
            raw=path.read_bytes()
            header=raw[:100]
            value_raw=header[offset:offset+width]
            parsed=int.from_bytes(value_raw,'big')
            assert value==(65536 if offset==16 and parsed==1 else parsed)
            dump=subprocess.check_output(['/usr/bin/od','-An','-v','-tx1','-N','100',str(path)],text=True)
            assert bytes.fromhex(dump)==header
            formatted='\n'.join(f'{i:04x}: {header[i:i+16].hex(" ")}' for i in range(0,100,16))
            query=f'For the read-only inventory, report the {field.replace("_"," ")} from {path.name}. The od byte dump has hexadecimal offsets on the left.\n'+formatted
            records.append(dict(id=path.stem,split=split,field=field,file_sha=digest(raw),prompt=query,
                                answer=dict(offset=offset,width=width,value=value),evidence=f'{offset},{width},{value_raw.hex()}'))
    assert len({r['file_sha'] for r in records})==len({r['prompt'] for r in records})==len(records)
    for split in ['train','holdout','replay','retention']:
        save(DATA/(split+'.json'),[r for r in records if r['split']==split])
    save(DATA/'freeze.json',dict(hashes={p.stem:digest(p.read_bytes()) for p in sorted(DATA.glob('*.json'))},
         files={r['id']:r['file_sha'] for r in records},primary_metric='strict numeric triple exact match',
         gap='Teacher correct with exact evidence >=2/3; student explicitly wrong >=2/3 in each mode; incomplete or malformed outputs unknown.',
         fallback='If few confirmed gaps, train on all teacher-verified examples, disclose gap count and keep gap-specific interpretation separate.',
         objective='Per update: mean answer CE + 0.25 mean replay CE; reasoning arm additionally 0.5 mean evidence CE on separate prompts.',
         training='Qwen3-8B, 4 epochs, per update one train and one rotating replay example, LoRA rank 16 alpha 32 q/v, lr 1e-5, seed 3407',
         evaluation='One deterministic nonthinking prediction per file for base and both arms. Primary 24 untouched fresh files; retention12 new files on replay fields.'))
if __name__=='__main__': build()
