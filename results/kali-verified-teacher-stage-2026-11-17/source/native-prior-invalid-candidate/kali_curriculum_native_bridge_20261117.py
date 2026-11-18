"""Real native Worker dispatch gate, fresh training and host-only grading."""
import base64,gzip,hashlib,json,threading
from pathlib import Path
from prepare_kali_verified_curriculum_20261117 import ROOT,OUT
from kali_curriculum_sft_jobs_20261117 import STAGE,run,name_for
from kali_execution_jobs_20261114 import k,OUT as JOBS
S=STAGE
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def baseline():
    d=json.loads((STAGE/'runs/pair/score-private.json').read_text());chosen=max([cid for cid,r in d['results'].items() if r['eligible']],key=lambda cid:d['results'][cid]['score']);score=d['results'][chosen]['score']
    training=json.loads((STAGE/'paired-training-private.json').read_text());receipt=None if chosen=='E0' else json.loads((STAGE/'runs/pair'/chosen/'receipt.json').read_text())
    pointer={'schema':'kali.verified-teacher.v1','candidate_id':chosen,'model_id':'Qwen/Qwen3-8B','model_revision':training['model_protocol']['model_revision'],'adapter_sha256':None if chosen=='E0' else receipt['adapter_sha256'],'optimizer_steps':0 if chosen=='E0' else receipt['updates'],'protocol_sha256':sha(STAGE/'evaluation-protocol.json')}
    return {'candidate_id':chosen,'score':score,'pointer':pointer,'scores':d['results']}
class Broker:
    def __init__(self,driver):
        self.driver=driver;self.baseline=baseline();self.lock=threading.Lock();self.states={};self.started=[];self.threads=[];self.current=None;self.recipes={};self.manifest_sha256=sha(driver.OUT/'task/training_manifest.json');self.updates=json.loads((STAGE/'paired-training-private.json').read_text())['protocol']['optimizer_updates_per_arm']
        self.grading_proxy_sha256=hashlib.sha256(json.loads((driver.OUT/'task/setup_payload.json').read_text())['score_py'].encode()).hexdigest()
    def train(self,cid,lr):
        try:
            dest=run(cid,lr);r=json.loads((dest/'reasoning/receipt.json').read_text());trace=json.loads((dest/'reasoning/trace.json').read_text());pred=json.loads((dest/'reasoning-predictions.json').read_text());cfg=json.loads((dest/'launch-freeze-private.json').read_text())['config']
            original=json.loads((STAGE/'paired-training-private.json').read_text());original['protocol']['learning_rate']=lr;expected=hashlib.sha256((json.dumps(original)+'\n').encode()).hexdigest()
            assert r['data_sha256']==expected and r['updates']==len(trace)==self.updates and r['learning_rate']==lr and all(x['gradient_norm']>0 for x in trace) and pred['reload_audit']['trained_vs_reloaded_probe_identical']
            assert r['initial_adapter_sha256']==json.loads((STAGE/'runs/pair/reasoning/receipt.json').read_text())['initial_adapter_sha256'],'Fresh adapter initialization differs'
            pointer={'schema':'kali.verified-teacher.v1','candidate_id':cid,'model_id':'Qwen/Qwen3-8B','model_revision':r['model_revision'],'adapter_sha256':r['adapter_sha256'],'optimizer_steps':r['updates'],'protocol_sha256':sha(STAGE/'evaluation-protocol.json')}
            (dest/'adapter-pointer-private.json').write_text(json.dumps({'pointer':pointer,'cache_adapter':cfg['durable_output']+'/reasoning/adapter'},indent=2)+'\n')
            receipt={'optimizer_steps':r['updates'],'nonzero_gradient_steps':sum(x['gradient_norm']>0 for x in trace),'learning_rate':lr,'reload_probe_identical':True,'adapter_sha256':r['adapter_sha256'],'training_data_sha256':r['data_sha256'],'new_optimizer_steps_this_run':r['updates']}
            state={'status':'REAL_GPU_TRAINING_COMPLETE','candidate_id':cid,'pointer':pointer,'training_receipt':receipt,'training_provenance':{'execution':'FRESH_NATIVE_GPU_TRAINING','new_optimizer_steps_this_run':r['updates'],'reused_candidate_training':False}}
        except BaseException as e:state={'status':'FAILED','candidate_id':cid,'error_type':type(e).__name__,'detail':str(e)[:220]}
        with self.lock:self.states[cid]=state;self.current=None
        (self.driver.OUT/(cid+'-backend-private.json')).write_text(json.dumps(state,indent=2)+'\n')
    def call(self,req):
        action=req.get('action')
        if action=='health' and set(req)=={'action'}:return {'status':'READY','allowed_candidates':['A1','A2'],'learning_rates':[5e-6,1e-5,2e-5],'max_parallel_GPU':1,'official_TEST_rows':0}
        if action=='train_data' and set(req)=={'action','manifest_sha256'}:
            assert req['manifest_sha256']==self.manifest_sha256
            raw=(self.driver.OUT/'training-encoded-host-private.json').read_bytes();manifest=json.loads((self.driver.OUT/'task/training_manifest.json').read_text());assert hashlib.sha256(raw).hexdigest()==manifest['train_encoded_sha256']
            return {'status':'TRAIN_ONLY','train_gzip_base64':base64.b64encode(gzip.compress(raw)).decode(),'DEV_rows':0}
        if action=='submit' and set(req)=={'action','candidate_id','learning_rate','manifest_sha256'}:
            cid=req['candidate_id'];lr=req['learning_rate'];assert cid in ['A1','A2'] and lr in [5e-6,1e-5,2e-5] and req['manifest_sha256']==self.manifest_sha256
            with self.lock:
                assert self.current is None and cid not in self.started and len(self.started)<2 and lr not in self.recipes.values() and not (STAGE/'runs'/cid).exists(),'No parallel, duplicate or reused candidates'
                journal=self.driver.collect_journal();assert any(a['target'].endswith('/setup_1') and a['output'].get('failed') is False for a in journal['actions']);active=set(journal['started_actions'])-{a['target'] for a in journal['actions']};assert any('/worker_' in x for x in active),'Actual native Worker must be active'
                assert journal.get('grading_proxy_sha256')==self.grading_proxy_sha256,'Do not dispatch GPU work with a modified or unverified native grading proxy'
                self.started.append(cid);self.recipes[cid]=lr;self.current=cid;self.states[cid]={'status':'IN_PROGRESS','candidate_id':cid};(self.driver.OUT/(cid+'-native-dispatch-private.json')).write_text(json.dumps({'run_id':journal['run_id'],'active_actions':sorted(active),'request':req},indent=2)+'\n')
                t=threading.Thread(target=self.train,args=(cid,lr),daemon=True);self.threads.append(t);t.start()
            return {'status':'SUBMITTED','candidate_id':cid,'new_updates_budget':self.updates}
        if action=='status' and set(req)=={'action','candidate_id'}:
            assert req['candidate_id'] in self.started;return self.states[req['candidate_id']]
        if action=='score' and set(req)=={'action','pointer'}:
            p=req['pointer'];cid=p['candidate_id']
            if p==self.baseline['pointer']:score=self.baseline['score']
            else:
                assert cid in self.started and self.states[cid]['status']=='REAL_GPU_TRAINING_COMPLETE' and p==self.states[cid]['pointer'];score=json.loads((STAGE/'runs'/cid/'score-private.json').read_text())['grade']['score']
            return {'score':score,'components':{'optimizer_steps':p['optimizer_steps'],'official_TEST_rows':0}}
        raise ValueError('Invalid broker schema')
    def abort_running(self):
        if not self.current:return
        name=name_for(self.current);p=JOBS/name/'host.json'
        if not p.exists():return
        host=json.loads(p.read_text());actual=k('get','job',name,'-o','json',check=False)
        if actual.returncode==0:
            assert json.loads(actual.stdout)['metadata']['uid']==host['uid']
            k('delete','job',name,'--wait=true','--timeout=30s');k('delete','configmap',name,'--wait=true','--timeout=20s')
def bridge(driver,stop):
    # Reuse the audited SSH mailbox loop; replace only its experiment-specific broker.
    import kali_qwen_native_bridge_20261115 as transport
    transport.Broker=Broker
    return transport.bridge(driver,stop)
