#!/usr/bin/env python3
"""Freeze a small assistant-reviewed SOURCE-SILVER pilot, never official CTI data."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(p, obj): p.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')

# Explicit semantic review of the pinned English CNA descriptions; not expert adjudication.
# These are source labels, not newly invented gold labels. No predictions used for selection.
ACCEPT = {
 'CWE-787': {
 '0461':'DDR receive-buffer overflow crosses allocation boundary.',
 '0482':'USB buffer overflow overwrites a function pointer.',
 '103680':'Counter causes writes past an allocated buffer.',
 '103416':'TLS message writes past cache into control block.',
 '79900':'Digest-name copy exceeds allocated heap field.',
 '84854':'Driver writes outside kernel buffer.',
 '104036':'Oversized idmap copy continues after bounds failure.'},
 'CWE-125': {
 '105838':'Oversized pattern parsing reads adjacent heap.',
 '104029':'Incorrect offset causes explicit out-of-bounds read.',
 '65122':'Description explicitly identifies out-of-bounds read; terse source.',
 '79896':'TLS parser reads outside bounds.',
 '104030':'Unterminated token read crosses buffer end.',
 '19029':'Filter decoder overreads heap without chunk-bound checks.',
 '104042':'Zero-length token processing reads beyond buffer.',
 '75819':'Unchecked file-header offsets cause out-of-bounds read.',
 '106026':'Rewrite-string routine has explicit out-of-bounds read.',
 '103641':'Truncated image scanline read passes mapped data end.'},
 'CWE-502': {
 '95534':'Untrusted PHP deserialization/object injection.',
 '100511':'Untrusted deserialization.',
 '103349':'Untrusted deserialization.',
 '55083':'Unsafe Java deserialization.',
 '93617':'Untrusted deserialization.',
 '107104':'User-controlled unsafe deserialization.',
 '103831':'Unrestricted classes during PHP unserialize.',
 '103877':'LDAP parsing deserializes untrusted Java objects.'},
 'CWE-78': {
 '71451':'Explicit OS command injection; terse source.',
 '106059':'Unescaped file name enters a shell command.',
 '75937':'Explicit arbitrary OS command execution in web administration.',
 '91140':'Untrusted specification enters shell cleanup command.',
 '101207':'Explicit OS command injection.',
 '104859':'Untrusted configuration enters shell command strings.',
 '105793':'Reparsed shell command on Android; not host/root execution.',
 '102160':'Backup operation permits OS command injection.',
 '79898':'CRL URL reaches shell substitution.'},
 'CWE-918': {
 '82044':'Unvalidated server-side URL fetch reaches internal resources.',
 '105263':'Unvalidated metadata URL triggers server-side request.',
 '103757':'Attachment URL is passed to server-side fetch.',
 '76274':'Unvalidated outbound destination can disclose API token.',
 '105301':'CRL/OCSP URL is fetched before certificate trust validation.',
 '80464':'Explicit server-side request forgery; terse source.',
 '55232':'IPv6 blacklist gap in server-side fetch.',
 '105122':'Unvalidated jwks_uri causes server-side fetch.'},
 'CWE-89': {n:'Description explicitly identifies SQL injection from untrusted input.' for n in
 ['85215','42708','62059','96267','42720','62060','39785','103766','42721']},
 'CWE-22': {n:'Missing path confinement permits traversal or access outside intended directory.' for n in
 ['105816','105834','105751','87115','105174','105286','103648','104871','41958']},
 'CWE-79': {n:'Unescaped or insufficiently sanitized web input enables script execution.' for n in
 ['92826','105124','102295','102576','95595','7174','103063','59666','104673']},
}
HOLD = {
 '25269':'Excess allocation/memory corruption does not clearly distinguish write mechanism.',
 '59783':'Null-byte input and crash do not establish out-of-bounds write.',
 '102163':'Crash/RCE consequence does not establish write mechanism.',
 '107221':'Bounds-checked Go panic does not establish unsafe memory write.',
 '101258':'Memory corruption plus sandbox-bypass chain is ambiguous.',
 '59782':'Reading other heap data does not clearly establish out-of-bounds access.',
 '104037':'Integer underflow/read chain: root versus consequence is ambiguous.',
 '104043':'Integer underflow/read chain: root versus consequence is ambiguous.',
 '102164':'Memory disclosure consequence does not establish read mechanism.',
 '106061':'Integer overflow/read chain: root versus consequence is ambiguous.',
 '106558':'Object import/instantiation is not a clear deserialization description.',
 '12544':'Template injection and deserialization chain has multiple candidate roots.',
 '105697':'Compound command feature/misconfiguration is ambiguous for this pilot.',
 '103546':'Administrative changes do not clearly describe an outbound request.',
}
def main():
    source = ROOT/'data/raw/cti-source-pilot/source-candidates.jsonl'
    fetch = json.loads((ROOT/'docs/verification/cti-source-pilot-fetch.json').read_text())
    assert sha(source.read_bytes()) == fetch['candidate_sha256']
    rows = {r['id']:r for r in map(json.loads, source.read_text().splitlines())}
    exposed = set(json.loads((ROOT/'data/manifests/cti-development-exposure.json').read_text())['linked_ids_conservatively_exposed'])
    accepted=[]; reviews=[]
    for label, decisions in ACCEPT.items():
        for number, reason in decisions.items():
            r = rows['CVE-2026-'+number]
            assert r['label']==label and not r['structural_issues'] and r['id'] not in exposed
            raw = ROOT/'.tools/cti-source-pilot/cna'/f'{r["id"]}.json'
            assert sha(raw.read_bytes()) == r['source_sha256']
            cna=json.loads(raw.read_text())['containers']['cna']
            assert [d['value'].strip() for d in cna['descriptions'] if d['lang'].lower().startswith('en')] == [r['description']]
            reviews.append({'id':r['id'],'source_sha256':r['source_sha256'],
                            'decision':'ACCEPT_SOURCE_SILVER_EXPLORATORY','rationale':reason})
            accepted.append(r)
    for number,reason in HOLD.items():
        r=rows['CVE-2026-'+number]
        reviews.append({'id':r['id'],'source_sha256':r['source_sha256'],
                        'decision':'HOLD_AMBIGUOUS','rationale':reason})
    # Conservative vendor grouping across the small selected pool, combined with
    # earlier reference/text groups. Broad vendors may merge unrelated products;
    # overmerging is disclosed and safer than splitting SSSD/BoKS/Quay variants.
    parent={r['id']:r['id'] for r in accepted}
    def find(k):
        while parent[k]!=k:
            parent[k]=parent[parent[k]]; k=parent[k]
        return k
    def union(a,b): parent[find(a)]=find(b)
    seen={}
    for r in accepted:
        keys=['intake:'+r['group_id']]
        for p in r['products']:
            vendor=str(p.get('vendor') or '').strip().lower()
            product=str(p.get('packageName') or p.get('product') or '').strip().lower()
            if vendor and vendor not in {'n/a','unknown','none'}: keys.append('vendor:'+vendor)
            elif product: keys.append('product:'+product)
        for key in keys:
            if key in seen: union(r['id'],seen[key])
            else: seen[key]=r['id']
    components=defaultdict(list)
    for r in accepted: components[find(r['id'])].append(r['id'])
    groups={i:'pilot-'+sha('|'.join(sorted(v)).encode())[:16] for v in components.values() for i in v}
    # First deterministic assignment satisfying count constraints, never model scores.
    for seed in range(10000):
        assignment={g:('dev' if int(sha(f'cti-pilot:{seed}:{g}'.encode())[:8],16)%100<30 else 'train') for g in set(groups.values())}
        pools={(s,c):[r for r in accepted if assignment[groups[r['id']]]==s and r['label']==c] for s in ['train','dev'] for c in ACCEPT}
        if all(len(pools['dev',c])>=2 and len(pools['train',c])>=(5 if c=='CWE-787' else 6) for c in ACCEPT): break
    else: raise RuntimeError('No group-disjoint balanced assignment found')
    out=ROOT/'data/raw/cti-pilot-v1';out.mkdir(parents=True,exist_ok=True)
    license_source=ROOT/'.tools/cti-source-pilot/CVE-TERMS-SOURCE.html'
    html=license_source.read_text()
    assert 'MITRE' in html and 'CVE Usage' in html and 'copyright' in html.lower()
    # Preserve all visible text of the official terms, including the full licence
    # and copyright, as inert plain text rather than an executable HTML page.
    class VisibleTerms(HTMLParser):
        def __init__(self):super().__init__();self.skip=0;self.lines=[]
        def handle_starttag(self,tag,attrs):
            if tag in {'script','style'}:self.skip+=1
        def handle_endtag(self,tag):
            if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        def handle_data(self,text):
            if not self.skip and text.strip():self.lines.append(text.strip())
    parser=VisibleTerms();parser.feed(html)
    terms='\n'.join(parser.lines)+'\n'
    assert 'CVE Usage' in terms and 'Copyright' in terms and 'MITRE' in terms
    (out/'CVE-TERMS.txt').write_text(terms)
    (out/'NOTICE.md').write_text('Derived exploratory data from CVEProject/cvelistV5.\n'
       'CVE source copyright and complete licence: CVE-TERMS.txt.\n'
       'Official terms source: https://cveproject.github.io/docs/terms.html\n'
       'These are assistant-reviewed source-silver labels, not independently adjudicated gold.\n'
       'Descriptions are the pinned CNA English text; original CVE records remain unchanged.\n')
    artifacts={};counts={};selected=[]
    for split in ['train','dev']:
        dest=[]
        for label in ACCEPT:
            ordered=sorted(pools[split,label],key=lambda r:sha(('pilot-select:'+r['id']).encode()))
            target=2 if split=='dev' else (5 if label=='CWE-787' else 6)
            for r in ordered[:target]:
                dest.append({k:r[k] for k in ['id','label','description','source_url','source_sha256']})
                dest[-1].update({'group_id':groups[r['id']], 'split':split,
                    'label_quality':'SOURCE_SILVER_ASSISTANT_REVIEWED',
                    'training_eligible':split=='train','official_benchmark':False,
                    'notice_file':'NOTICE.md'})
        b=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in dest).encode()
        (out/f'{split}.jsonl').write_bytes(b)
        artifacts[split]={'path':str((out/f'{split}.jsonl').relative_to(ROOT)), 'sha256':sha(b),'rows':len(dest),'labels':dict(Counter(r['label'] for r in dest))}
        counts[split]=len(dest);selected+=dest
    a,b=([r for r in selected if r['split']==s] for s in ['train','dev'])
    assert not ({r['group_id'] for r in a}&{r['group_id'] for r in b})
    assert not ({r['id'] for r in a}&{r['id'] for r in b})
    assert not ({sha(r['description'].encode()) for r in a}&{sha(r['description'].encode()) for r in b})
    report={'created_at_utc':datetime.now(timezone.utc).isoformat(),
      'status':'FROZEN_EXTERNAL_SOURCE_SILVER_EXPLORATORY_V1','reviewer':'AI assistant, not independent domain expert',
      'source_candidate_sha256':sha(source.read_bytes()),'cvelist_revision':fetch['cvelist_revision'],
      'reviewed_accept':len(accepted),'reviewed_hold':len(HOLD),'reviews':reviews,
      'counts':counts,'artifacts':artifacts,'assignment_seed':seed,
      'groups':{g:sorted(i for i,v in groups.items() if v==g) for g in sorted(set(groups.values()))},
      'training_scope':'Only the frozen pilot train file; original 1977-row intake remains HOLD.',
      'official_test_rows':0,'model_predictions_used_for_selection':False,
      'prior_debug_group_ids_excluded':len(exposed),
      'license':{'source':'https://cveproject.github.io/docs/terms.html', 'source_html_sha256':sha(license_source.read_bytes()),'plain_text_sha256':sha(terms.encode()),'notice_files':['NOTICE.md','CVE-TERMS.txt']},
      'limitations':['Eight-class convenience subset, not representative benchmark data.',
        'CNA/NVD are related sources; agreement is not independent gold.',
        'Assistant semantic review is not expert adjudication.',
        'Vendor grouping intentionally overmerges products; hidden aliases may remain.',
        'Development split guides engineering; it is not an independent final test.',
        'No official CTI benchmark body was loaded.']}
    dump(ROOT/'data/manifests/cti-source-pilot-v1.json',report)
    print(json.dumps({'status':report['status'],'counts':counts,'reviewed_accept':len(accepted),'reviewed_hold':len(HOLD),'seed':seed,'groups':len(components)},indent=2))

if __name__=='__main__': main()
