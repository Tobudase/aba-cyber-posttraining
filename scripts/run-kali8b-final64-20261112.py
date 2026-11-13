#!/usr/bin/env python3
"""Freeze native selection, query sealed64 once, and score without further tuning."""
import base64,gzip,hashlib,json,os,sys,time
from pathlib import Path
from kali8b_study_jobs import ROOT,S,k,protocol,labels,placement_pool
from benchkit import native_kali,strict_option_values
F=ROOT/'data/benchkit/kali-redsage-aba-final64-2026-11-10';OUT=S/'confirmation';NAME='miw113-kali8b-v64-confirm';WORKER=ROOT/'scripts/kali8b_final64_worker.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
 implementation=json.loads((S/'confirmation-implementation-lock-private.json').read_text());assert sha(WORKER)==implementation['worker_sha256'] and sha(Path(__file__))==implementation['runner_sha256'],'Confirmation implementation changed after freeze'
 selection=json.loads((S/'native-selection-private.json').read_text());assert selection['status']=='NATIVE_SEARCH_COMPLETE_SELECTION_FROZEN' and not selection['final64_used'];native=json.loads((ROOT/'docs/verification/kali8b-native-v64-20261112/host-private.json').read_text());assert native['native_completed'] and native['status']=='COMPLETE_VERIFIED_NATIVE_8B_STUDY'
 frozen_native=json.loads((ROOT/'docs/verification/kali8b-native-v64-20261112/native-task-freeze-private.json').read_text());assert sha(S/'placement-amendment-private.json')==frozen_native['placement_amendment_sha256'];assert json.loads((S/'four-arm-consistency-aggregate.json').read_text())['status']=='PASS_REAL_FOUR_ARM_CONSISTENCY'
 manifest=json.loads((F/'freeze-manifest-private.json').read_text());assert sha(F/'inputs-private.json.gz')==manifest['inputs_gzip_sha256'] and sha(F/'references-private.json')==manifest['references_sha256']
 final_ids={r['id'] for r in json.loads(gzip.decompress((F/'inputs-private.json.gz').read_bytes()))['holdout']};assert len(final_ids)==64
 for cid in ('P11','P12','P13','P14'):
  payload=json.loads(gzip.decompress((S/cid/'payload-private.json.gz').read_bytes()));assert not final_ids & {r['id'] for r in payload['train_rows']+payload['dev1']+payload['dev2']};assert json.loads((S/cid/'run/host-private.json').read_text())['status']=='COLLECTED'
 cids=list(dict.fromkeys(['P11','P12',selection['native_selected_candidate']]));adapters={}
 for cid in cids:
  r=json.loads((S/cid/'run/receipt-private.json').read_text());p=S/cid/'run/adapter-bundle-private/adapter';assert sha(p/'adapter_model.safetensors')==r['adapter_sha256'] and sha(p/'adapter_config.json')==r['adapter_config_sha256'];adapters[cid]={'weights_sha256':r['adapter_sha256'],'config_sha256':r['adapter_config_sha256']}
 anchors=json.loads(gzip.decompress((S/'P11/payload-private.json.gz').read_bytes()))['anchors'];expected=json.loads((S/'P11/run/base-anchor-audit-private.json').read_text());assert len(anchors)==len(expected)==4
 return {'status':'FINAL64_QUERY_FROZEN_AFTER_SELECTION','model_protocol':protocol('P11'),'adapters':adapters,'preselected_candidate':selection['candidate_id'],'native_selected_candidate':selection['native_selected_candidate'],'selection_sha256':sha(S/'native-selection-private.json'),'final64_inputs_gzip_sha256':sha(F/'inputs-private.json.gz'),'references_sha256':sha(F/'references-private.json'),'worker_sha256':sha(WORKER),'anchors':[{k:r[k] for k in ['id','native_messages']} for r in anchors],'expected_anchor_responses':{r['id']:r['response'] for r in expected},'no_further_training':True,'placement_policy':placement_pool(),'official_TEST_rows':0}
def objects(cfg):
 p=cfg['model_protocol'];cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':NAME,'labels':labels('P11')},'data':{'worker.py':WORKER.read_text(),'config.json':json.dumps(cfg,indent=2)+'\n'}};secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':NAME+'-input','labels':labels('P11')},'type':'Opaque','data':{'inputs.json.gz':base64.b64encode((F/'inputs-private.json.gz').read_bytes()).decode()}}
 node=json.loads((S/'hardware-lock-private.json').read_text())['hostname_label'];resources=dict(p['resource_request']);resources.update((cfg.get('placement_policy') or {}).get('resource_request_overrides',{}))
 pod={'restartPolicy':'Never','activeDeadlineSeconds':7200,'automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/hostname':node},'containers':[{'name':'evaluate','image':json.loads((ROOT/'configs/gpu-runtime-image.lock.json').read_text())['image'],'command':['python','-u','/input/worker.py'],'env':[{'name':'HF_HUB_OFFLINE','value':'1'},{'name':'OMP_NUM_THREADS','value':'2'},{'name':'CUBLAS_WORKSPACE_CONFIG','value':':4096:8'}],'resources':{'requests':resources,'limits':resources},'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True},{'name':'cache','mountPath':'/cache','readOnly':True},{'name':'scratch','mountPath':'/scratch'}]}],'volumes':[{'name':'input','projected':{'defaultMode':256,'sources':[{'configMap':{'name':NAME}},{'secret':{'name':NAME+'-input'}}]}},{'name':'cache','persistentVolumeClaim':{'claimName':'miw113-kali-cuda-cache','readOnly':True}},{'name':'scratch','emptyDir':{'sizeLimit':'24Gi'}}]}
 pool=cfg.get('placement_policy')
 if pool:
  pod['nodeSelector']={'kubernetes.io/arch':'amd64'};pod['affinity']={'nodeAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':pool['allowed_hostnames']},{'key':'nvidia.com/gpu.product','operator':'In','values':[pool['GPU_product']]},{'key':'nvidia.com/cuda.driver-version.full','operator':'In','values':pool.get('allowed_driver_full',[pool['driver_full']])}]}]}}}
 job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':NAME,'labels':labels('P11')},'spec':{'activeDeadlineSeconds':21600,'backoffLimit':0,'ttlSecondsAfterFinished':3600,'template':{'metadata':{'labels':labels('P11')},'spec':pod}}};return cm,secret,job
def score(cfg,outputs):
 refs={r['custom_id']:r for r in json.loads((F/'references-private.json').read_text())};assert len(refs)==64;scorer=native_kali();summary={};detail={}
 for cid,rows in outputs.items():
  assert len(rows)==64 and len({r['id'] for r in rows})==64 and {r['id'] for r in rows}==set(refs);d={}
  for r in rows:
   v=scorer.score_one(refs[r['id']],r['response']);d[r['id']]={'native':v['total_score'],'strict':bool(not r['truncated'] and strict_option_values(refs[r['id']],r['response'],scorer)),'format_error':bool(v['format_error']),'truncated':r['truncated']}
  detail[cid]=d;summary[cid]={'rows':64,'native_mean':sum(x['native'] for x in d.values())/64,'strict_correct':sum(x['strict'] for x in d.values()),'format_errors':sum(x['format_error'] for x in d.values()),'truncations':sum(x['truncated'] for x in d.values())}
 best=cfg['preselected_candidate'];b=summary['E0'];c=summary[best];gates={'native_improved':c['native_mean']>b['native_mean'],'strict_retained':c['strict_correct']>=b['strict_correct'],'format_retained':c['format_errors']<=b['format_errors'],'truncation_retained':c['truncations']<=b['truncations']}
 paired={cid:{'gained':sum(not detail['E0'][i]['strict'] and d[i]['strict'] for i in refs),'lost':sum(detail['E0'][i]['strict'] and not d[i]['strict'] for i in refs)} for cid,d in detail.items() if cid!='E0'}
 result={'status':'FROZEN64_CONFIRMATION_COMPLETE','preselected_candidate':best,'summary':summary,'preselected_retention_gates':gates,'preselected_passed':all(gates.values()),'paired_strict':paired,'no_candidate_selection_using_confirmation':True,'official_TEST_rows':0,'scope':'Previously unqueried TRAIN-derived internal confirmation;publisher-verified silver,not expert gold,not source-separated,not an official benchmark score. Internal gate passing alone does not establish public leaderboard gains or model deployment readiness.'}
 (OUT/'score-detail-private.json').write_text(json.dumps(detail,indent=2)+'\n');(OUT/'scores-private.json').write_text(json.dumps(result,indent=2)+'\n');return result
def main():
 assert not OUT.exists(),'Never re-query sealed confirmation or overwrite an attempt';cfg=freeze();OUT.mkdir(mode=0o700);(OUT/'query-freeze-private.json').write_text(json.dumps(cfg,indent=2)+'\n');record={'status':'STARTING','cleanup_errors':[],'official_TEST_rows':0};made=[]
 try:
  for obj in objects(cfg):k('create','--dry-run=server','-f','-',payload=json.dumps(obj))
  for obj in objects(cfg):k('create','-f','-',payload=json.dumps(obj));made.append((obj['kind'].lower(),obj['metadata']['name']))
  deadline=time.monotonic()+21690;last=None
  while time.monotonic()<deadline:
   j=json.loads(k('get','job',NAME,'-o','json').stdout);pods=json.loads(k('get','pods','-l','job-name='+NAME,'-o','json').stdout)['items'];phase=pods[0]['status'].get('phase') if pods else 'QUEUED'
   if phase!=last:print('CONFIRMATION '+str(phase),flush=True);last=phase
   if j.get('status',{}).get('succeeded') or j.get('status',{}).get('failed'):break
   time.sleep(30)
  logs=k('logs','job/'+NAME,check=False).stdout;(OUT/'worker-log-private.txt').write_text(logs);assert j.get('status',{}).get('succeeded'),'Confirmation GPU job failed; recover existing outputs,do not silently query again'
  def marker(name):
   values=[r.split('=',1)[1] for r in logs.splitlines() if r.startswith(name+'=')];assert len(values)==1;return values[0]
  receipt=json.loads(marker('FINAL64_RECEIPT'));assert receipt['status']=='COMPLETE_FROZEN64_EVAL_ONLY' and receipt['optimizer_steps']==0 and receipt['worker_sha256']==sha(WORKER) and receipt['selection_sha256']==cfg['selection_sha256'] and receipt['config_sha256']==sha(OUT/'query-freeze-private.json')
  outputs=json.loads(gzip.decompress(base64.b64decode(marker('FINAL64_PREDICTIONS'),validate=True)));assert set(outputs)=={'E0',*cfg['adapters']};(OUT/'predictions-private.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n');(OUT/'receipt-private.json').write_text(json.dumps(receipt,indent=2)+'\n');result=score(cfg,outputs);record.update(status='COMPLETE',preselected_candidate=cfg['preselected_candidate'],preselected_passed=result['preselected_passed'])
 except BaseException as e:record.update(status='FAILED',error_type=type(e).__name__,error=str(e)[:300]);raise
 finally:
  for kind,name in reversed(made):
   r=k('delete',kind,name,'--ignore-not-found=true','--wait=true','--timeout=60s',check=False)
   if r.returncode:record['cleanup_errors'].append(kind+':'+r.stderr[-200:])
  (OUT/'host-private.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
if __name__=='__main__':main()
