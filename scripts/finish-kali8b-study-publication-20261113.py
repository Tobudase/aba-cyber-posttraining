#!/usr/bin/env python3
"""One-shot dependent publication,only after real native/confirmation completion.
No training,inference,confirmation retries or fake results. A finite local
pipeline continuation,not a scheduled alert. Refuse concurrent repository edits.
"""
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12'
NATIVE=ROOT/'docs/verification/kali8b-native-v64-20261112'
RESULT=Path('results/kali-8b-verified64-study-2026-11-12')
REPORT=Path('docs/KALI_VERIFIED64_8B_RESULT_2026-11-12_ZH.md')
def read(p):return json.loads(p.read_text())
def run(args,**kw):return subprocess.run(list(map(str,args)),check=True,text=True,capture_output=True,**kw)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def completed():
 h=read(NATIVE/'host-private.json')
 if h['status']=='FAILED':raise RuntimeError('Native failed;no publication or confirmation retry permitted')
 c=S/'confirmation/host-private.json'
 if c.exists() and read(c)['status']=='FAILED':raise RuntimeError('Confirmation failed;preserve existing attempt,never silently re-query')
 return h['status']=='COMPLETE_VERIFIED_NATIVE_8B_STUDY' and not h['cleanup_errors'] and c.exists() and read(c)['status']=='COMPLETE' and not read(c)['cleanup_errors']
def documents(x):
 assert x['research_experiment_complete'] and x['status']=='COMPLETE_BOUNDED_8B_STUDY'
 base=x['arms']['P11']['score']['summary']['base'];sel=x['selection'];winner=sel['native_selected_candidate'];retained=sel['candidate_id'];confirm=x['confirmation'];passed=confirm['preselected_passed'];lines=['# 8B验证数据与受限原生ABA：完整实验结果','', '本次四组受限对照、原生选择和一次内部64题确认均已完成。实验流程完成与取得可靠增益是两回事；以下不是官方排行榜成绩。','', '| 模型 | DEV128 strict | native×100 | DEV1 native×100 | DEV2 native×100 | 预定门槛 |','| --- | ---: | ---: | ---: | ---: | --- |']
 panels={'E0':base};panels.update({c:a['score']['summary']['candidate'] for c,a in x['arms'].items()})
 for cid,p in panels.items():
  gate='原始基线' if cid=='E0' else ('通过' if x['arms'][cid]['score']['passes_all_gates'] else '未通过')
  lines.append(f"| {cid} | {p['combined']['strict_correct']}/128 | {100*p['combined']['native_total_mean']:.3f} | {100*p['dev1']['native_total_mean']:.3f} | {100*p['dev2']['native_total_mean']:.3f} | {gate} |")
 lines+=['',f'原生ABA在P13/P14中选择 **{winner}**；宿主按预先固定的保留规则，与固定对照冠军/原始E0比较后，预选 **{retained}**。原生搜索不会自动把Setup基线纳入候选，因此两种选择必须分开记录。确认集未参与这次选择。','', '![完整受限实验：已暴露DEV与一次内部确认](../results/kali-8b-verified64-study-2026-11-12/study-results.png)','', '## 一次内部64题确认','', '| 模型 | strict | native×100 | 与E0差值（分） | 格式错误 | 截断 |','| --- | ---: | ---: | ---: | ---: | ---: |']
 b=confirm['summary']['E0']
 for cid,p in confirm['summary'].items():lines.append(f"| {cid} | {p['strict_correct']}/64 | {100*p['native_mean']:.3f} | {100*(p['native_mean']-b['native_mean']):+.3f} | {p['format_errors']} | {p['truncations']} |")
 if retained=='E0':conclusion='没有训练候选通过全部预定DEV门槛，继续保留原始E0；本轮未建立可靠的后训练增益。'
 elif passed:conclusion=f'预选{retained}通过本次内部确认的预定增益/保留门槛。这是小样本内部结果，仍不足以建立官方测试提升、统计稳定性或正式模型发布依据。'
 else:conclusion=f'预选{retained}未通过内部确认的全部门槛，不晋升该候选；继续保留原始E0。'
 lines+=['',conclusion+' 不按确认题成绩重新选择模型，也不再使用本次确认题调参。','', '## 可核对的实现与边界','', '- 每个完成的SFT组实际完成733次非零梯度更新、17,439个监督token，四组有效训练合计2,932次更新；另有一次P13中断至少执行704次更新但没有完整适配器，已弃用、从原始权重重跑。旧任务与重跑在截至704步的全部23个已打印损失/梯度记录点完全相同；这是稀疏进度核验，不是所有步骤或硬件完全等价的证明。这部分失败成本单独披露，不能把2,932称为全部尝试总更新数。有效LoRA文件已回收到宿主并核对哈希。确认任务没有优化器更新或梯度。','- 所有新鲜E0 DEV128输出逐字一致；seed42初始化一致，seed43不同；P12/P14首次更新前的损失/梯度/token记录一致，P11/P12替换前14步记录一致。它们是本次运行的实现一致性证据，不是独立复制实验或统计稳定性保证。','- P11/P12为原SDSC节点、广告驱动615.71.09、CPU2；P13/P14及确认允许同型号A100的13主机池、广告驱动615.71.09/.10，恢复CPU2。此次预算和资源修订发生在固定对照结果及一次弃用的部分P13训练之后、任何训练后候选DEV输出之前；不能声称完全相同硬件。所有新鲜E0、初始化及首步梯度检查仍须通过，实际主机与Pod资源在汇总中保留。','- 新64条仅覆盖4种工具、32个相关任务族，为本地行为验证的AI银标。P12替换了64条原数据；这是替换策略效果，不能单独归因于数据质量。单项可执行不等于组合技能或未见题迁移有效。','- DEV128此前已暴露并用于开发；final64是此前未查询过的同一发布方TRAIN衍生银标，既非独立专家金标，也非官方TEST或来源隔离测试。官方TEST使用量仍为0。','- ABA搜索2个预注册方案，而每个固定对照只有1个方案；不作等搜索预算优越性声明。编排使用NRP托管模型，实际被训练的仍为RedSage-K 8B。','',f"成功训练worker耗时合计约 **{x['training_GPU_worker_hours']:.3f} GPU小时**，确认worker约 **{x['confirmation_GPU_worker_hours']:.3f} GPU小时**；另有弃用P13的观测分配时间窗口约 **{x.get('discarded_approximate_GPU_allocation_window_hours',0):.3f} GPU小时**。成功worker含模型搬运、训练和推理，未含失败尝试；失败窗口从分配至日志结束估算，非精确释放时间。两者均非FLOP或计费测量。",'', '[完整数值与回执](../results/kali-8b-verified64-study-2026-11-12/summary.json) · [协议与资源修订](../results/kali-8b-verified64-study-2026-11-12/protocol.json) · [四组一致性](../results/kali-8b-verified64-study-2026-11-12/four-arm-consistency.json) · [旧中断/重跑日志核对](../results/kali-8b-verified64-study-2026-11-12/discarded-vs-fresh-log-comparison.json) · [实验设计](KALI_VERIFIED64_8B_STUDY_2026-11-12_ZH.md)','']
 strict=base['combined']['strict_correct'];short=f"Completed four real 8B SFT arms (733 nonzero-gradient updates each),two native ABA candidates,and one frozen 64-example internal confirmation. Native winner: **{winner}**;DEV-preselected model: **{retained}**. Confirmation gate: **{'passed' if passed else 'not passed'}**. Official TEST queries: **0**. This completes the bounded experiment;it does not by itself establish reliable improvement or an official benchmark gain."
 section='## November 12, 2026 — completed bounded 8B study\n\n'+short+'\n\n![Complete bounded study](results/kali-8b-verified64-study-2026-11-12/study-results.png)\n\n[Detailed results and limitations](docs/KALI_VERIFIED64_8B_RESULT_2026-11-12_ZH.md) · [Machine-readable results](results/kali-8b-verified64-study-2026-11-12/summary.json). Resource amendment and controller recovery remain disclosed in the frozen protocol.\n\n'
 return '\n'.join(lines),section

def main():
 p=argparse.ArgumentParser();p.add_argument('--publication-root',type=Path,required=True);p.add_argument('--expected-run-id',required=True);p.add_argument('--wait',action='store_true');a=p.parse_args();pub=a.publication_root.resolve();log=NATIVE/'publication-continuation-private.json';record={'status':'WAITING_ACTUAL_COMPLETION','started_at_utc':utc(),'expected_run_id':a.expected_run_id};write=lambda:log.write_text(json.dumps(record,indent=2)+'\n')
 if shutil.which('caffeinate'):subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  assert run(['git','branch','--show-current'],cwd=pub).stdout.strip()=='main'
  assert run(['git','remote','get-url','origin'],cwd=pub).stdout.strip() in ['https://github.com/Tobudase/aba-cyber-posttraining.git','https://github.com/Tobudase/aba-cyber-posttraining']
  assert not run(['git','status','--porcelain'],cwd=pub).stdout.strip(),'Concurrent public edits;refuse automatic publication'
  initial=run(['git','rev-parse','HEAD'],cwd=pub).stdout.strip();record['initial_public_HEAD']=initial;write();until=time.monotonic()+25*3600
  while True:
   journal=NATIVE/'journal-private.json'
   if journal.exists():assert read(journal)['run_id']==a.expected_run_id,'Native attempt changed;do not publish a different run'
   if completed():break
   if not a.wait:record.update(status='NOT_COMPLETE_NO_PUBLIC_WRITES',checked_at_utc=utc());write();print(json.dumps(record));return 3
   assert time.monotonic()<until,'Finite publication wait expired'
   time.sleep(30)
  assert run(['git','rev-parse','HEAD'],cwd=pub).stdout.strip()==initial and not run(['git','status','--porcelain'],cwd=pub).stdout.strip(),'Concurrent edits;review before publication'
  assert read(NATIVE/'journal-private.json')['run_id']==a.expected_run_id
  run([sys.executable,ROOT/'scripts/publish-kali8b-study-snapshot-20261112.py','--publication-root',pub,'--require-complete'],cwd=ROOT)
  shutil.copy2(S/'four-arm-consistency-aggregate.json',pub/RESULT/'four-arm-consistency.json')
  run([sys.executable,ROOT/'scripts/verify-kali8b-completed-study.py','--root',pub],cwd=ROOT)
  x=read(pub/RESULT/'summary.json');report,section=documents(x);(pub/REPORT).write_text(report)
  readme=(pub/'README.md').read_text();start=readme.index('## November 12, 2026 — matched 8B study running');end=readme.index('## November 12, 2026 — behavior-verified TRAIN supplement',start);(pub/'README.md').write_text(readme[:start]+section+readme[end:])
  env=os.environ.copy();env['MPLCONFIGDIR']=str(ROOT/'.tools/matplotlib-cache');run([ROOT/'.tools/results-plot-venv/bin/python',ROOT/'scripts/plot-kali8b-verified64-study.py','--summary',pub/RESULT/'summary.json','--output',pub/RESULT/'study-results'],cwd=ROOT,env=env)
  # Programmatic image checks only;do not claim a human visual review.
  run([ROOT/'.tools/results-plot-venv/bin/python','-c',"from PIL import Image,ImageStat;import sys;p=Image.open(sys.argv[1]).convert('RGB');assert p.width>1500 and p.height>1000 and sum(ImageStat.Stat(p).var)>100;print('NONBLANK_FIGURE_DIMENSIONS_PASS')",pub/RESULT/'study-results.png'])
  shutil.copy2(Path(__file__),pub/'scripts'/Path(__file__).name)
  files=['README.md',str(REPORT),str(RESULT/'summary.json'),str(RESULT/'four-arm-consistency.json'),str(RESULT/'study-results.png'),str(RESULT/'study-results.svg'),'scripts/'+Path(__file__).name]
  key=(ROOT/'.secrets/nrp_api_key').read_bytes().strip()
  for name in files:
   blob=(pub/name).read_bytes();assert key not in blob and not re.search(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{20,}',blob)
   if not name.endswith('.png'):assert not re.search(rb'\bsk-[A-Za-z0-9_-]{24,}',blob),name
  run(['git','add','--',*files],cwd=pub);run(['git','diff','--cached','--check'],cwd=pub)
  # Refuse to include preexisting staged changes or unrelated files.
  staged=set(run(['git','diff','--cached','--name-only'],cwd=pub).stdout.splitlines());assert staged<=set(files) and str(RESULT/'summary.json') in staged
  run(['git','commit','-m','Complete verified64 8B native ABA study and frozen confirmation'],cwd=pub);head=run(['git','rev-parse','HEAD'],cwd=pub).stdout.strip();record.update(status='VERIFIED_LOCAL_COMMIT_READY',commit=head);write()
  run(['git','push','origin','main'],cwd=pub,timeout=120);remote=run(['git','ls-remote','origin','refs/heads/main'],cwd=pub,timeout=60).stdout.split()[0];assert remote==head
  record.update(status='COMPLETE_VERIFIED_AND_PUSHED',finished_at_utc=utc(),retained_candidate=x['selection']['candidate_id'],confirmation_gate_passed=x['confirmation']['preselected_passed'],official_TEST_rows=0,figure_QA='Programmatic dimension/nonblank check;no claimed human visual inspection');write();print(json.dumps(record),flush=True);return 0
 except BaseException as e:
  record.update(status='STOPPED_WITHOUT_CLAIMING_COMPLETION',error_type=type(e).__name__,error=str(e)[:400],checked_at_utc=utc());write();print(json.dumps(record),flush=True);raise
if __name__=='__main__':raise SystemExit(main())
