import threading, concurrent.futures, json, re, ssl, time, urllib.request, urllib.error
from pathlib import Path
from fixture import DATA, TEACHER, save, digest

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def answer(content):
    matches=re.findall(r'<answer>\s*(.*?)\s*</answer>',content,re.S)
    if len(matches)!=1:return None
    try: obj=json.loads(matches[0])
    except ValueError:return None
    if not isinstance(obj,dict) or set(obj)!={'offset','width','value'} or any(type(x)!=int for x in obj.values()):return None
    return obj

def collect():
    token=(DATA.parents[1]/'.secrets/nrp_api_key').read_text().strip()
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile='/etc/ssl/cert.pem')))
    freeze=json.loads((DATA/'freeze.json').read_text())
    assert digest((DATA/'train.json').read_bytes())==freeze['hashes']['train']
    rows=json.loads((DATA/'train.json').read_text())
    dest=DATA/'teacher';dest.mkdir(exist_ok=True)
    lock=threading.Lock(); next_start=[0.]
    def one(item):
            repeat,i,r=item
            path=dest/f"{i}-{repeat}.json"
            if path.exists():return
            payload=dict(model='qwen3-small',messages=[dict(role='system',content=TEACHER),dict(role='user',content=r['prompt'])],
                         seed=8407+1000*repeat+i,max_tokens=6144,temperature=.6,top_p=.95,chat_template_kwargs=dict(enable_thinking=False))
            with lock:
                time.sleep(max(0,next_start[0]-time.monotonic()));next_start[0]=time.monotonic()+6
            req=urllib.request.Request('https://ellm.nrp-nautilus.io/v1/chat/completions',data=json.dumps(payload).encode(),
                     headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            for attempt in range(4):
                try:
                    with opener.open(req,timeout=480) as res: body=json.load(res)
                    break
                except urllib.error.HTTPError as exc:
                    print('HTTP',exc.code,flush=True)
                    if exc.code not in [429,500,502,503,504] or attempt==3:raise
                    time.sleep(10*(attempt+1))
                except (TimeoutError,ConnectionError,urllib.error.URLError) as exc:
                    print('transport retry',i,repeat,type(exc).__name__,flush=True)
                    if attempt==3:raise
                    time.sleep(3*(attempt+1))
            c=body['choices'][0];msg=(c['message'].get('content') or '').rsplit('</think>',1)[-1]
            ev=re.findall(r'<evidence>(.*?)</evidence>',msg,re.S)
            cert=c['finish_reason']=='stop' and answer(msg)==r['answer'] and len(ev)==1 and ev[0].strip().lower()==r['evidence']
            save(path,dict(id=r['id'],seed=payload['seed'],model=body['model'],content=msg,stop=c['finish_reason'],cert=cert))
            print(i,repeat,body['model'],cert,flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one,((repeat,i,r) for repeat in range(3) for i,r in enumerate(rows))))
if __name__=='__main__':collect()
