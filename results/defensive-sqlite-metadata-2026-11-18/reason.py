"""Obtain short teacher explanations with independently checkable lookup/decoding steps."""
import concurrent.futures, json, re, ssl, threading, time, urllib.request, urllib.error
from fixture import DATA, save
from teacher import NoRedirect

FIELD={'schema_generation':'schema cookie','release_marker':'user version','application_identifier':'application id','number_of_free_pages':'freelist count'}
FORMAT=('Rewrite your verified file reading as exactly three sentences, with no extra text. '
        'Use this template: "I locate FIELD at decimal offset O. I read W bytes in file order: HEX. '
        'Decoding HEX as an unsigned big-endian integer gives V." '
        'Use the standard field name (schema cookie, user version, application id, or freelist count), '
        'lowercase contiguous hexadecimal digits including leading zeros, and decimal integers for O, W, V.')
def checked(text,r):
    m=re.fullmatch(r'I locate (schema cookie|user version|application id|freelist count) at decimal offset (\d+)\.\s*I read (\d+) bytes in file order:\s*([0-9a-f]+)\.\s*Decoding ([0-9a-f]+) as an unsigned big-endian integer gives (\d+)\.',text.strip(),re.I)
    if not m:return False
    f,o,w,x,y,v=m.groups();a=r['answer']
    return (f.lower()==FIELD[r['field']] and (int(o),int(w),int(v))==(a['offset'],a['width'],a['value'])
            and x.lower()==y.lower()==r['evidence'].split(',')[-1] and int(x,16)==int(v))
def main():
    dest=DATA/'explanations';dest.mkdir(exist_ok=True)
    rows=json.loads((DATA/'train.json').read_text())
    key=(DATA.parents[1]/'.secrets/nrp_api_key').read_text().strip()
    op=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile='/etc/ssl/cert.pem')))
    # Sequential, in addition to three screening requests at most. Use the same teacher.
    for i,r in enumerate(rows):
        p=dest/f'{i}.json'
        if p.exists():continue
        files=[DATA/'teacher'/f'{i}-{j}.json' for j in range(3)]
        while True:
            returned=[json.loads(f.read_text()) for f in files if f.exists()]
            good=[d for d in returned if d['cert']]
            if len(good)>=2 or len(returned)-len(good)>=2:break
            time.sleep(8)
        if len(good)<2:
            save(p,dict(admitted=False,requests=0));continue
        # Include only the teacher's own certified structured work, never oracle corrections.
        message=good[0]['content']
        prior=re.search(r'<evidence>[^<]+</evidence>',message).group()+re.search(r'<answer>[^<]+</answer>',message).group()
        attempts=[]
        for seed in (17001,18001):
            payload=dict(model='qwen3-small',messages=[dict(role='user',content=r['prompt']),dict(role='assistant',content=prior),dict(role='user',content=FORMAT)],temperature=0,seed=seed,max_tokens=4096,chat_template_kwargs=dict(enable_thinking=False))
            req=urllib.request.Request('https://ellm.nrp-nautilus.io/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
            for j in range(3):
                try:
                    with op.open(req,timeout=480) as f: obj=json.load(f)
                    break
                except (TimeoutError,ConnectionError,urllib.error.URLError):
                    if j==2:raise
                    time.sleep(10)
            c=obj['choices'][0];body=c['message']['content'].rsplit('</think>',1)[-1].strip()
            # Extract the teacher's contiguous, fully matched derivation only.
            candidates=re.findall(r'I locate [^\n<>]{1,100}? at decimal offset \d+\.\s*I read \d+ bytes in file order:\s*[0-9a-f]+\.\s*Decoding [0-9a-f]+ as an unsigned big-endian integer gives \d+\.',body,re.I)
            valid=[t for t in candidates if checked(t,r)]
            attempts.append(dict(seed=seed,model=obj['model'],stop=c['finish_reason'],text=body))
            if valid and c['finish_reason']=='stop' and obj['model']==good[0]['model']:
                save(p,dict(id=r['id'],admitted=True,reason=valid[-1],attempts=attempts));break
            time.sleep(6)
        if not p.exists():save(p,dict(id=r['id'],admitted=False,attempts=attempts))
        print(i,json.loads(p.read_text())['admitted'],flush=True)
        time.sleep(6)
if __name__=='__main__':main()
