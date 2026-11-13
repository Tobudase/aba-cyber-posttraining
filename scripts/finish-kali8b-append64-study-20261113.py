#!/usr/bin/env python3
"""Wait for this bounded experiment, verify actual receipts, then publish aggregates."""
import datetime,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'data/benchkit/kali-8b-append64-study-2026-11-13';PUB=ROOT.parent/'github-publication/aba-cyber-posttraining';R=PUB/'results/kali-8b-append64-study-2026-11-13'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def cmd(a):return subprocess.run(list(map(str,a)),cwd=PUB,text=True,capture_output=True,check=True).stdout.strip()
def main():
 initial=cmd(['git','rev-parse','HEAD']);assert not cmd(['git','status','--porcelain']);until=time.monotonic()+100800
 if shutil.which('caffeinate'):subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())])
 last=None
 while True:
  host=read(S/'host-private.json');state={c:read(S/c/'run/host-private.json')['status'] if (S/c/'run/host-private.json').exists() else 'NOT_STARTED' for c in ['A15','A16','A17','A18']}
  if state!=last:print(json.dumps({'study':host['status'],'arms':state}),flush=True);last=state
  if host['status'] in ['COMPLETE','FAILED']:break
  assert time.monotonic()<until,'Publication wait expired; no fabricated completion'
  time.sleep(30)
 assert cmd(['git','rev-parse','HEAD'])==initial and not cmd(['git','status','--porcelain']),'Concurrent public edits'
 lock=read(S/'freeze.json');assert sha(ROOT/'scripts/run-kali8b-append64-study-20261113.py')==lock['controller_sha256'];assert sha(ROOT/'scripts/kali8b_study_grade.py')==lock['DEV_grading_module_sha256'];assert sha(S/'worker.py')==lock['worker_sha256']
 result={'status':host['status'],'arms':{},'official_TEST_rows':0,'final64_queries':0,'scope':'Operator append-versus-replay diagnosis on exposed DEV;not native ABA or independent validation.','model_promotion_allowed':False};bases=[]
 for cid,status in state.items():
  if status!='COLLECTED':result['arms'][cid]={'status':status};continue
  run=S/cid/'run';receipt=read(run/'receipt-private.json');assert receipt['optimizer_steps']==receipt['nonzero_gradient_steps']==797 and receipt['supervised_token_presentations']==19065 and receipt['protocol_sha256']==lock['protocol_sha256'][cid];assert sha(run/'adapter-bundle-private/adapter/adapter_model.safetensors')==receipt['adapter_sha256'] and receipt['adapter_reload_max_logit_delta']<=1e-4
  assert not read(run/'host-private.json')['cleanup_errors'];bases.append(read(run/'base-predictions-private.json'));result['arms'][cid]={'status':status,'score':read(run/'scores-private.json'),'receipt':receipt,'adapter_export':read(run/'adapter-export-private.json')}
  result['arms'][cid]['receipt']={k:v for k,v in receipt.items() if k not in ['trace','epoch_order']}
 if host['status']=='COMPLETE':
  assert len(bases)==4 and all(b==bases[0] for b in bases);result['paired_effects']={}
  for control,treat in [('A15','A16'),('A17','A18')]:
   a=result['arms'][control];b=result['arms'][treat];assert a['receipt']['initial_lora_sha256']==b['receipt']['initial_lora_sha256'];p=a['score']['summary']['candidate']['combined'];q=b['score']['summary']['candidate']['combined'];result['paired_effects'][treat+'-minus-'+control]={'native_delta':q['native_total_mean']-p['native_total_mean'],'strict_count_delta':q['strict_correct']-p['strict_correct']}
  result['total_successful_worker_hours']=sum(a['receipt']['wall_seconds'] for a in result['arms'].values())/3600
 # A failed study is published as failed, not automatically retrained or promoted.
 (R/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(R/'status.json').write_text(json.dumps({'status':host['status'],'arms':state,'official_TEST_rows':0,'final64_queries':0,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
 lines=['# 追加数据与重放对照：实际结果','',result['scope'],'','| 组别 | 状态 | strict/128 | native×100 | 格式错误 | 截断 | 保留门槛 |','| --- | --- | ---: | ---: | ---: | ---: | --- |']
 for cid,a in result['arms'].items():
  if a['status']!='COLLECTED':lines.append(f'| {cid} | {a["status"]} | — | — | — | — | — |');continue
  p=a['score']['summary']['candidate']['combined'];lines.append(f'| {cid} | COLLECTED | {p["strict_correct"]} | {100*p["native_total_mean"]:.3f} | {p["format_errors"]} | {p["truncations"]} | {a["score"]["passes_all_gates"]} |')
 for pair,e in result.get('paired_effects',{}).items():lines+=['',f'{pair}: native变化 {100*e["native_delta"]:+.3f}分，strict变化 {e["strict_count_delta"]:+d}题。']
 lines+=['','这是保留原始数据后的新增内容与原数据重放对照，两个种子只提供方向诊断，不证明稳定增益。与旧733步结果跨实验比较还混入更新次数和数据顺序变化，不能单独称作删除旧数据的因果效应。所有128题已暴露；没有独立确认或官方成绩，不晋升模型。','', '[完整汇总](summary.json) · [冻结设计](DESIGN_ZH.md)','']
 (R/'RESULT_ZH.md').write_text('\n'.join(lines));p=PUB/'README.md';t=p.read_text();anchor='[Submission status](results/kali-8b-append64-study-2026-11-13/status.json).';assert anchor in t;t=t.replace(anchor,anchor+' Final recorded state: **'+host['status']+'**. [Actual results](results/kali-8b-append64-study-2026-11-13/RESULT_ZH.md).',1);p.write_text(t)
 shutil.copy2(Path(__file__),PUB/'scripts'/Path(__file__).name)
 files=['README.md','scripts/'+Path(__file__).name]+[str((R/n).relative_to(PUB)) for n in ['summary.json','status.json','RESULT_ZH.md']]
 key=(ROOT/'.secrets/nrp_api_key').read_bytes().strip()
 for name in files:
  blob=(PUB/name).read_bytes();assert key not in blob and not re.search(rb'\bsk-[A-Za-z0-9_-]{24,}',blob)
 cmd(['git','add','--',*files]);cmd(['git','diff','--cached','--check']);assert set(cmd(['git','diff','--cached','--name-only']).splitlines())<=set(files);cmd(['git','commit','-m','Publish actual append-versus-replay diagnostic receipts and outcomes']);cmd(['git','push','origin','main']);head=cmd(['git','rev-parse','HEAD']);assert cmd(['git','ls-remote','origin','refs/heads/main']).split()[0]==head
 final={'status':'ACTUAL_OUTCOME_PUSHED','study_status':host['status'],'commit':head};(S/'publication-private.json').write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final),flush=True)
if __name__=='__main__':main()
