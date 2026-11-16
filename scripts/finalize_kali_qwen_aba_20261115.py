"""Verify genuine native artifacts, recompute frozen scores, and report paired results."""
import collections,hashlib,json,math,os,subprocess,sys
from pathlib import Path
from kali_qwen_aba_jobs_20261115 import DATA,ROOT,FIXED,native,sha
from kali_execution_jobs_20261114 import OUT
from kali_qwen_aba_grade_20261115 import grade
PUBLIC=ROOT.parent/'github-publication/aba-cyber-posttraining'
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def verify():
 h=json.loads((DATA/'native-controller/host-private.json').read_text());assert h['native_completed'] and h['status']=='COMPLETE_VERIFIED_NATIVE_QWEN_ABA' and not h['cleanup_errors'] and h['cleanup_pending'] is False
 freeze=json.loads((DATA/'native-controller/native-task-freeze-private.json').read_text());assert all(sha(ROOT/'scripts'/n)==digest for n,digest in freeze['runtime_source_sha256'].items());assert sha(DATA/'native-controller/config.json')==freeze['config_sha256']
 journal=json.loads((DATA/'native-controller/journal-private.json').read_text());assert journal['head']['result']=='completed' and not journal['failures'];assert journal['task_hashes']==freeze['task_sha256'];assert h['native_run_id']==journal['run_id']
 meta=json.loads((DATA/'grading-metadata-private.json').read_text());baseline_native=json.loads((DATA/'controls/native-details-private.json').read_text())['qwen_base'];baseline_behavior=json.loads((DATA/'paired-controls-behavior-private.json').read_text())['details']['qwen_base'];allrows={};new_queries=0;updates=0;model_receipts={}
 for cid in ['controls','A1','A2']:
  pred=json.loads((DATA/cid/'predictions-private.json').read_text());details=json.loads((DATA/cid/'native-details-private.json').read_text());assert native(pred)==details;new_queries+=sum(len(rr) for rr in pred.values());behavior=json.loads((DATA/(('paired-controls' if cid=='controls' else cid.lower())+'-behavior-private.json')).read_text());assert all(all(v.values()) for v in behavior['controls'].values()) and len(behavior['controls'])==46 and all(behavior['preview_controls'].values());saved=json.loads((DATA/cid/'score.json').read_text())
  recalculated={a:grade(meta,d,behavior['details'][a],baseline_native,baseline_behavior) for a,d in details.items() if a in behavior['details']};assert saved==recalculated
  labels=['qwen_base','qwen_fixed'] if cid=='controls' else ['qwen_step128']
  for label in labels:
   public_label={'qwen_base':'E0','qwen_fixed':'fixedSFT256','qwen_step128':cid}[label];g=saved[label];verdicts=behavior['details'][label];groups=collections.defaultdict(list)
   for ident,m in meta['new46'].items():groups[m['group']].append(verdicts[ident])
   upper=math.fsum(sum(x=='fixture_pass' or x.startswith('unknown') for x in vv)/len(vv) for vv in groups.values())/len(groups)*100
   toolcounts={t:dict(collections.Counter(verdicts[i] for i,m in meta['new46'].items() if m['tool']==t)) for t in sorted({v['tool'] for v in meta['new46'].values()})};counts=dict(collections.Counter(verdicts.values()));allrows[public_label]={**g,'utility_upper_points':upper,'behavior_counts':counts,'behavior_by_tool':toolcounts,'new_native_points':math.fsum(details[label][i]['native'] for i in meta['new46'])/46*100,'new_strict':sum(details[label][i]['strict'] for i in meta['new46']),'optimizer_steps':0 if public_label=='E0' else 256 if public_label=='fixedSFT256' else 128}
  for label in labels:
   public_label={'qwen_base':'E0','qwen_fixed':'fixedSFT256','qwen_step128':cid}[label];panel_counts={'new46':sum(bool(r['truncated']) for r in pred[label] if r['id'] in meta['new46']),'old64':sum(bool(r['truncated']) for r in pred[label] if r['id'] in meta['old64_ids'])};assert sum(panel_counts.values())==allrows[public_label]['truncated'];allrows[public_label]['truncated_by_panel']=panel_counts
  r=json.loads((DATA/cid/'receipt.json').read_text());jobdir=OUT/('miw113-qwen-aba-'+cid.lower()+'-1115');cmtext=json.loads((jobdir/'objects.json').read_text())[0]['data']['config.json'];assert hashlib.sha256(cmtext.encode()).hexdigest()==r['config_sha256'] and json.loads(cmtext)==json.loads((DATA/cid/'gpu-freeze.json').read_text())['config'];assert json.loads((jobdir/'host.json').read_text())['resources_cleaned'];model_receipts[cid]={'GPU':r['GPU'],'wall_seconds':r['wall_seconds'],'worker_sha256':r['worker_sha256'],'config_sha256':r['config_sha256'],'inputs_sha256':r['inputs_sha256']}
  if cid!='controls':
   q=r['models']['qwen'];trace=q['training_trace'];assert q['optimizer_steps']==q['nonzero_gradient_steps']==len(trace)==128 and q['reload_complete_responses_identical'] and q['initial_zero_B_probe_difference']==0;assert all(t['step']==i+1 and math.isfinite(t['ce_mean']) and t['grad_norm_before_clip']>0 for i,t in enumerate(trace));assert [t['ids'] for t in trace]==[t['ids'] for t in json.loads((FIXED/'receipt.json').read_text())['models']['qwen']['training_trace'][:128]];updates+=128
   dispatch=json.loads((DATA/'native-controller'/(cid+'-native-dispatch-private.json')).read_text());assert dispatch['run_id']==journal['run_id'] and any('/worker_' in a for a in dispatch['active_actions']);assert r['learning_rate']==dispatch['request']['learning_rate'];model_receipts[cid].update(learning_rate=r['learning_rate'],optimizer_steps=128,supervised_tokens=q['supervised_tokens'],optimizer_seconds=math.fsum(t['window_seconds'] for t in trace),initial_adapter_sha256=q['initial_adapter_sha256'],reload_complete_responses_identical=True)
 assert updates==256 and len({r['GPU'] for r in model_receipts.values()})==1
 assert sum(model_receipts[c]['supervised_tokens'] for c in ['A1','A2'])==json.loads((FIXED/'receipt.json').read_text())['models']['qwen']['supervised_tokens']==31100
 assert len({r['inputs_sha256'] for r in model_receipts.values()})==1 and len({r['worker_sha256'] for r in model_receipts.values()})==1
 configurations=[json.loads((DATA/c/'gpu-freeze.json').read_text())['config'] for c in ['controls','A1','A2']];assert all(c['module_sha256']==configurations[0]['module_sha256'] and c['model_protocols']==configurations[0]['model_protocols'] for c in configurations)
 selection=json.loads((DATA/'native-selection-private.json').read_text());assert selection['new_optimizer_steps_total']==256 and selection['confirmation_used'] is False;nativecid=selection['native_selected_candidate'];assert allrows[nativecid]['score']==max(allrows[c]['score'] for c in ['A1','A2']);assert selection['native_selected_DEV_score']==allrows[nativecid]['score'];assert selection['DEV_score']==allrows[selection['candidate_id']]['score'];assert selection['DEV_score']>=allrows['E0']['score']
 export=json.loads((DATA/'export-audit.json').read_text());assert export['two_actual_adapters_exported_hash_verified'] and export['CPU_exporter_deleted']
 for cid in ['A1','A2']:
  cp=json.loads((DATA/cid/'receipt.json').read_text())['models']['qwen']['checkpoints']['qwen_step128'];assert cp['weights_sha256']==export['digests'][cid]['weights_sha256'];assert sha(DATA/cid/'adapters-private/qwen_step128/adapter/adapter_model.safetensors')==cp['weights_sha256']
 summary={'status':'VERIFIED_REAL_NATIVE_ABA_VS_FIXED_SFT','scope':'Internal adaptive DEV46(26groups,9tools)+old64;not official TEST,expert gold or full KaliBench score.','model':'Qwen/Qwen3-8B','revision':'b968826d9c46dd6066d109eabc6255188de91218','native_run_id':journal['run_id'],'native_framework_commit':'c8bd734cafd5a7cd609efb5f561594bde4107d5b','scores':allrows,'receipts':model_receipts,'native_selected':nativecid,'host_retained':selection['candidate_id'],'new_optimizer_updates_total':updates,'fixed_historical_updates':256,'new_model_responses_total_including_repeated_E0_and_reload':new_queries,'official_TEST_queries':0,'old_final64_requeries':0,'confirmation_queries_in_this_development_stage':0,'hashes':{'protocol':sha(DATA/'protocol.json'),'native_task_freeze':sha(DATA/'native-controller/native-task-freeze-private.json'),'journal':sha(DATA/'native-controller/journal-private.json')},'verification':{'all46_controls_and_counterexamples_passed':True,'predictions_native_rescored':True,'grades_recomputed_identical':True,'real_native_worker_active_at_GPU_dispatch':True,'all256_updates_have_finite_nonzero_gradients':True,'both_adapters_exported_hash_verified':True,'both_reload_response_checks_identical':True,'GPU_payload_trainer_modules_and_pinned_model_identical':True,'common_GPU_product_for_all_new_evaluations_and_ABA_training':True,'prior_fixed_training_was_RTX3090':True,'native_finalizer_exact_fourfile_copy':True,'no_priority_quota_taint_bypass':True,'native_CPU_VM_cleaned':True},'limitations':['One seed,two fresh128-update candidates versus one cached256-update fixed SFT;equal total updates,not selected steps or end-to-end wall/FLOPs.','Prior fixed adapter was trained on RTX3090;all current evaluations and new candidates share the GPU product in receipts.','Data unchanged,restricted LR search:agent orchestrated bounded post-training,not autonomous novel-data synthesis.','UNKNOWN has no certified utility and is reported as unresolved;baseline UNKNOWN is not proven semantic failure.','Adaptive DEV and convenience old64 cannot establish independent generalization;auxiliary tasks have sparse coverage.']}
 write(DATA/'verified-summary.json',summary);return summary

def report(summary):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 dest=PUBLIC/'results/kali-qwen-native-aba-2026-11-15';dest.mkdir(parents=True,exist_ok=True);write(dest/'summary.json',summary);write(dest/'protocol.json',json.loads((DATA/'protocol.json').read_text()));write(dest/'verification.json',summary['verification'])
 labels=['E0','fixedSFT256','A1','A2'];rows=summary['scores'];colors=['#98a2b3','#2e90fa','#f79009','#12b76a'];fig,axes=plt.subplots(1,3,figsize=(13.8,4.6));fig.suptitle('Qwen3-8B: fixed SFT vs bounded native ABA',fontsize=15)
 fig.text(.5,.90,'No adapter passed all frozen gates; all three had one truncated output. Original retained.',ha='center',fontsize=10,color='#b42318')
 for ax in axes:ax.spines[['top','right']].set_visible(False);ax.set_xticks(range(4),['Original','Fixed SFT\n256 steps','ABA A1\n128 steps','ABA A2\n128 steps'],fontsize=9);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
 low=[rows[l]['utility_points'] for l in labels];unknown=[rows[l]['utility_upper_points']-rows[l]['utility_points'] for l in labels];axes[0].bar(range(4),low,color=colors);axes[0].bar(range(4),unknown,bottom=low,facecolor='none',edgecolor='#667085',hatch='///');axes[0].set_ylim(0,112);axes[0].set_title('DEV46: confirmed task-group utility');axes[0].set_ylabel('Points (26 groups)')
 for i,v in enumerate(low):axes[0].text(i,v+2,f'{v:.1f}',ha='center',fontsize=9)
 old=[rows[l]['old_native_points'] for l in labels];axes[1].bar(range(4),old,color=colors);axes[1].axhline(rows['E0']['old_native_points']-2,color='#d92d20',linestyle='--',linewidth=1);axes[1].set_ylim(0,100);axes[1].set_title('Old64: native partial score')
 for i,v in enumerate(old):axes[1].text(i,v+2,f'{v:.2f}',ha='center',fontsize=9)
 retention=[rows[l]['paired_E0_retained'] for l in labels];denom=rows['E0']['paired_E0_correct_count'];axes[2].bar(range(4),retention,color=colors);axes[2].axhline(math.ceil(.8*denom),color='#d92d20',linestyle='--',linewidth=1);axes[2].set_ylim(0,denom+1.8);axes[2].set_title('Paired E0 correct: retained')
 for i,v in enumerate(retention):axes[2].text(i,v+.25,f'{v}/{denom}',ha='center',fontsize=9)
 fig.text(.5,.015,'Internal adaptive panels; not official TEST. Hatched utility is unresolved UNKNOWN, not demonstrated failure. Red lines: frozen retention floors.',ha='center',fontsize=9);fig.tight_layout(rect=[0,.055,1,.93]);fig.savefig(dest/'comparison.png',dpi=180);fig.savefig(dest/'comparison.svg');plt.close(fig)
 table='|模型|新DEV46原生分|新DEV46严格匹配|行为PASS / FAIL / UNKNOWN / 无效|组宏平均确认效用|旧64原生分|旧64严格匹配|历史13题保留|本次E0答对题保留|准入|选择分|\n|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|\n'
 for label in labels:
  r=rows[label];c=r['behavior_counts'];u=sum(n for k,n in c.items() if k.startswith('unknown'));table+=f"|{label}|{r['new_native_points']:.2f}|{r['new_strict']}/46|{c.get('fixture_pass',0)} / {c.get('fixture_fail',0)} / {u} / {c.get('invalid_output',0)}|{r['utility_points']:.2f}–{r['utility_upper_points']:.2f}|{r['old_native_points']:.2f}|{r['strict_total']}/64|{r['historical_retained']}/13|{r['paired_E0_retained']}/{r['paired_E0_correct_count']}|{'通过' if r['eligible'] else '未通过'}|{r['score']:.3f}|\n"
 selected=summary['native_selected'];retained=summary['host_retained'];difference=rows[selected]['score']-rows['fixedSFT256']['score'];outcome=('原生胜者未通过准入，选择分差不能解释为优于固定SFT' if not rows[selected]['eligible'] else '原生胜者通过准入，而固定SFT未通过；两者的域内效用和旧能力应分开比较' if not rows['fixedSFT256']['eligible'] else '在冻结选择目标下高于固定SFT' if difference>0 else '在冻结选择目标下未超过固定SFT')
 text=f'''# 原始 Qwen3-8B：原生 ABA 与固定 SFT 对照

状态：**真实原生 ABA 的两候选搜索、训练、评分、Finalizer 与权重恢复均已核验**。原生 ABA 选中 **{selected}**；预先冻结的主机保留规则选择 **{retained}**。原生胜者相对固定 SFT 的选择分差为 **{difference:+.3f}**；{outcome}。分数是本实验的效用与保持目标，不是官方榜单准确率。

![对照结果](comparison.png)

{table}

截断按110题统一检查：固定SFT的一条来自新DEV的`look`题；A1、A2的截断各来自旧64题。较低学习率的A1仍有旧题输出可靠性问题，并非三份适配器都在同一道`look`题上失败。

## 实际执行

固定 SFT 是上轮真实训练256步的已核验适配器，此次重新在相同输入与评分协议下评测，没有冒充新训练。ABA 的 A1、A2 都从原始 `Qwen/Qwen3-8B` 的不可变修订 `{summary['revision']}` 开始，使用相同256条TRAIN（新题128＋发布方重放128），每个候选128次真实非零梯度更新，合计256次新更新、31,100个监督目标token，与固定SFT的总目标token曝光量一致。基座BF16冻结；训练FP32的q/v LoRA（r16、alpha32、dropout0），AdamW、microbatch1/累积4、逐目标token归一化CE、梯度裁剪1。学习率由原生流程在预先允许集合中选择，实际配方与耗时见 summary.json。

真实框架固定到 `{summary['native_framework_commit']}`，原生运行ID `{summary['native_run_id']}`，保留原生 Setup、Verifier/Reviewer、Designer、Worker、Score、Finalizer。主机在验证原生 Worker 正处于运行状态后才执行 GPU 请求；没有把手工循环或缓存权重算作新 ABA 训练。Finalizer 四个文件与原生所选输出字节一致。所有新评测和 ABA 候选训练使用相同 GPU 型号：`{summary['receipts']['controls']['GPU']}`；上轮固定 SFT 的训练 GPU 是 RTX3090。候选权重均恢复到本机并核验SHA256，重新加载后四条完整生成逐字相同。

## 验证与保持规则

新DEV46覆盖9工具、26个声明任务组，由已曝光的四工具DEV32加14条辅助CLI题组成；按组而非逐题宏平均，减少同组变体重复计权。46题的参考答案、等价写法及该版本所提供的错误反例均通过Linux实测；模型命令仅在有限白名单和实际外联阻断后执行。无法审查的替代写法仍记UNKNOWN，没有强行改成错误。

旧能力以旧64题原生部分分、严格匹配总数、历史13道答对题逐题保留，以及本次E0答对题保留率共同衡量。候选必须保持旧分不低于E0−2分，历史至少11/13，且本次E0答对题至少保留80%，110题无截断或过早EOS。选择分为 `新确认效用−E0效用 + 0.25×旧分变化 −10×历史丢失/13`；不达准入门则使用冻结惩罚分。原生候选另与E0、固定SFT竞争，持平保留原模型。

## 解释范围

这是单种子、两个128步候选的有限学习率搜索。其**总更新数**与固定256步SFT相同，但所选候选只有128步；两次新初始化、不同历史训练GPU和实际墙钟开销意味着不能宣称端到端算力严格相等，更不能据此评价ABA普遍优劣。没有在本轮生成新的训练数据。虽然新题与旧重放各128条，但按目标token计每轮是5192与2583，约2:1；不能把等行数误称为等梯度权重。固定SFT与ABA均使用同一配比。

E0在46道新题上的45个UNKNOWN不能算作语义错误；其确认效用0是有限验收器的已确认下界。原生ABA选出候选时使用同一冻结规则，不能把其相对0的确认效用增量直接宣传成真实准确率提升。

14条辅助DEV覆盖5个TRAIN中未见的工具。四种模型在这14题上均没有有限验收器确认的PASS；多数仍是UNKNOWN，不能等同于语义正确率0。现有确认通过都集中于四个已训练工具，尚未建立跨工具改善。

本次旧64输入与上轮逐字相同，但当前旧题从整体110题的第46个位置开始，和历史旧题独立起始的batch组成/左padding不同，GPU也发生变化；历史13道与本次E0的14道答对题分别报告，不能把数值变化单独归因于GPU。当前所有模型共享完全相同的110题输入与batch组成。

这46题属于自适应开发集，旧64题属于便利保持面板；AI银标与正反例检查均不能替代独立专家金标。辅助工具部分只有单题；UNKNOWN只说明未确认，原始模型的UNKNOWN不能解释为零语义能力。这里的严格匹配、原生部分分与行为通过数是不同指标。尚无本阶段独立确认结果，官方TEST查询为0，历史final64未重查。本报告不作全KaliBench、榜单提升或模型推广结论。

所有实际失败与零输出排队尝试保留在私有运行记录中；缺失CPU工具和提交池构造错误在第一条模型输出前修复并加入检查。未绕过配额、优先级、taint或保留节点，也未改动他人的任务。GPU任务、CPU评测与导出器及原生CPU VM都已清理；持久缓存和私有权重保留供复查。
'''
 (dest/'RESULT_ZH.md').write_text(text);print(json.dumps({'report':str(dest),'native_selected':selected,'host_retained':retained,'score_difference_vs_fixed':difference}),flush=True)
if __name__=='__main__':report(verify())
