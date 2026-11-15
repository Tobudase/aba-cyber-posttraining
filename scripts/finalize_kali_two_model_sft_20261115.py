"""Verify actual artifacts and generate a public report only after completion."""
import gzip,hashlib,json,math,shutil
from pathlib import Path
from kali_execution_jobs_20261114 import ROOT,OUT,k,write
DATA=ROOT/'data/benchkit/kali-two-model-sft-2026-11-15'
PUBLIC=ROOT.parent/'github-publication/aba-cyber-posttraining'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finalize():
 r=json.loads((DATA/'receipt.json').read_text());payload=json.loads(gzip.decompress((DATA/'gpu-inputs.json.gz').read_bytes()));pred=json.loads((DATA/'predictions-private.json').read_text());scores=json.loads((DATA/'native-summary.json').read_text());behavior=json.loads((DATA/'behavior-summary.json').read_text());paired=json.loads((DATA/'paired-retention-private.json').read_text());export=json.loads((DATA/'export-audit.json').read_text());audit=json.loads((DATA/'behavior-audit.json').read_text());freeze=json.loads((DATA/'launch-freeze.json').read_text())
 assert r['status']=='TWO_MODEL_SFT_COMPUTE_COMPLETE' and export['all_four_adapter_hashes_verified'] and audit['network_isolation_verified'] and audit['all_preview_regression_controls_passed']
 assert r['inputs_sha256']==sha(DATA/'gpu-inputs.json.gz')==freeze['config']['inputs_sha256']
 assert freeze['config']['protocol_sha256']==sha(DATA/'protocol.json')
 assert all(sha(ROOT/'scripts'/n)==h for n,h in freeze['config']['evaluation_sha256'].items())
 for model in ['redsage','qwen']:
  m=r['models'][model];trace=m['training_trace'];train=payload['encoded'][model];expected=[order[i:i+4] for order in payload['epoch_orders'] for i in range(0,256,4)]
  assert len(trace)==len(expected)==m['optimizer_steps']==m['nonzero_gradient_steps']==256
  for step,(t,ii) in enumerate(zip(trace,expected),1):
   assert t['step']==step and t['ids']==[train[i]['id'] for i in ii] and t['target_tokens']==sum(train[i]['target_tokens'] for i in ii)
   assert math.isfinite(t['grad_norm_before_clip']) and t['grad_norm_before_clip']>0 and math.isfinite(t['ce_mean'])
  assert sum(t['target_tokens'] for t in trace)==m['supervised_tokens'] and m['reload_complete_responses_identical'] and m['initial_zero_B_probe_difference']==0
  for label,cp in m['checkpoints'].items():
   path=DATA/'adapters-private'/cp['adapter_relative_path'];assert sha(path/'adapter_model.safetensors')==cp['weights_sha256'] and sha(path/'adapter_config.json')==cp['config_sha256'] and cp['changed_tensors']==144
  for label in [model+'_base',model+'_step128',model+'_step256']:assert len(pred[label])==128 and set(scores[label])==set(payload['panels'])
  assert pred[model+'_before_reload']==pred[model+'_after_reload']
 assert r['models']['redsage']['order_sha256']==r['models']['qwen']['order_sha256']
 assert sha(ROOT/'scripts/kali_two_model_sft_worker_20261115.py')==r['worker_sha256']
 # Exact names only: other conversations may legitimately own other GPU jobs.
 names=['miw113-kali-two-model-sft-r3-1115','miw113-kali-two-model-sft-r3-1115-export','miw113-kali-two-model-v6-score-1115']
 for name in names:
  for kind in ['job','configmap']:
   probe=k('get',kind,name,'-o','name',check=False);assert probe.returncode and 'NotFound' in probe.stderr,(kind,name)
 models={name:{key:val for key,val in m.items() if key!='training_trace'} for name,m in r['models'].items()}
 retention={name:{key:val for key,val in values.items() if not key.endswith('_ids')} for name,values in paired.items()}
 result={'status':'COMPLETE_VERIFIED_NO_MODEL_PROMOTION','scope':'One-seed four-tool adaptive development SFT pilot; original released models, model-specific templates; no native ABA or official benchmark gain claim','models':models,'GPU':r['GPU'],'native_scores':scores,'behavior':behavior,'paired_retention':retention,'actual_optimizer_steps':512,'primary_fixed_checkpoint':256,'all_512_trace_steps_verified':True,'actual_generations':sum(map(len,pred.values())),'official_TEST_queries':0,'previous_final64_requeries':0,'independent_confirmation_queries':0,'model_promotion':False,'this_pilot_resources_cleaned':True,'oracle_v6':audit,'protocol_sha256':sha(DATA/'protocol.json'),'receipt_sha256':sha(DATA/'receipt.json'),'prediction_sha256':sha(DATA/'predictions-private.json'),'limitations':['Different original model and serialization recipes; not an architecture-only causal ablation','Same data/row exposure, different target token counts and compute','One seed and four tools from a shared fixture generator','Old64 and newDEV32 are exposed adaptive development sets','Original E0 is task-specialized; its prior pretraining contamination is not audited','Old64 partial/strict outcomes are not behaviorally certified','All unknown commands remain unknown']}
 proof=OUT/'miw113-kali-two-model-sft-1115/storage-failure-proof.json'
 if proof.exists():
  failed=json.loads(proof.read_text())
  result['resource_attempts']={'initial':'GPU reserved on a node, container never started due to shared RWO Multi-Attach; cancelled, zero training/model calls. Queue and reserved idle time are not counted as zero cost.','failure_proof_sha256':sha(proof),'numerical_protocol_unchanged':True,'dedicated_cache_stage':json.loads((DATA/'dedicated-cache-stage-audit.json').read_text())}
 startup=OUT/'miw113-kali-two-model-sft-r2-1115/zero-training-startup-error.json'
 if startup.exists():
  result.setdefault('resource_attempts',{})['r2_startup_failure']={'details':json.loads(startup.read_text()),'proof_sha256':sha(startup),'fix':'Create missing parent directories on a fresh dedicated cache, retaining no-overwrite behavior; regression test passed.'}
 result['this_pilot_resources_cleaned']='All pilot Job/Pod/ConfigMap and scoring NetworkPolicy resources cleaned; dedicated cache storage retained separately.'
 result['retained_storage']={'claim':'miw113-kali-two-model-cache-1115','capacity':'8Gi','purpose':'Pinned runtime and private experimental artifacts; no running GPU. Existing shared40Gi cache untouched.'}
 result['paired_behavior_delta_bounds']={}
 result['strict_metric']='Project strict_option_values parameter matching, not an assertion of identical official leaderboard Exact Correct.'
 result['runtime_template_audits']={}
 for model in ['redsage','qwen']:
  template_audit=json.loads((DATA/('runtime-'+model+'-template-audit.json')).read_text())
  assert template_audit['all_equal'] and template_audit['runtime_training_vs_inference_prompt_checks']==32 and template_audit['model_forward_calls']==0
  result['runtime_template_audits'][model]=template_audit
  for step in [128,256]:
   label=model+'_step'+str(step);base=behavior[model+'_base']['new_dev32'];candidate=behavior[label]['new_dev32']
   result['paired_behavior_delta_bounds'][label]={'confirmed_PASS_delta':candidate['lower']-base['lower'],'conservative_lower':candidate['lower']-base['upper'],'conservative_upper':candidate['upper']-base['lower'],'interpretation':'Deterministic UNKNOWN bounds, not a statistical confidence interval. A positive lower bound supports gain even if every baseline UNKNOWN were successful.'}
 dest=PUBLIC/'results/kali-two-model-sft-2026-11-15';dest.mkdir(exist_ok=True);write(dest/'summary.json',result)
 write(DATA/'status.json',{'status':'COMPLETE_VERIFIED_NO_MODEL_PROMOTION','actual_optimizer_steps':512,'official_TEST_queries':0,'this_pilot_resources_cleaned':True})
 write(dest/'status.json',json.loads((DATA/'status.json').read_text()))
 shutil.copy2(DATA/'protocol.json',dest/'protocol.json');shutil.copy2(DATA/'data-preflight.json',dest/'data-preflight.json')
 oldbase={model:scores[model+'_base']['old64']['native_points'] for model in ['redsage','qwen']};lines=[]
 for model in ['redsage','qwen']:
  for label in [model+'_base',model+'_step128',model+'_step256']:
   old=scores[label]['old64'];b=behavior[label]['new_dev32'];fit=behavior[label]['train_probe32'];ret=retention.get(label,{'old_retained':old['strict'],'old_base_correct':old['strict']})
   lines.append(f"| {label} | {b['lower']}–{b['upper']}/32 | {fit['lower']}–{fit['upper']}/32 | {old['native_points']:.3f} | {old['strict']}/64 | {ret['old_retained']}/{ret['old_base_correct']} |")
 raw_lines=[]
 for model in ['redsage','qwen']:
  for label in [model+'_base',model+'_base_raw',model+'_step256',model+'_final_raw']:
   x=scores[label]['new_dev32'];b=behavior[label]['new_dev32'];raw_lines.append(f"| {label} | {b['lower']}–{b['upper']}/32 | {x['strict']}/32 | {x['complete']}/32 | {x['truncated']} |")
 report='''# 原始 RedSage 与 Qwen3-8B：小规模SFT对照

两组从固定发布权重与全新FP32零B LoRA开始；未加载F22或历史适配器。同一张GPU上顺序运行，同样256条TRAIN、同样四轮样本顺序，每组256次实际更新。公开所有固定128/256步checkpoint结果，不事后挑最优。

| 模型 | 新DEV32行为确认范围 | TRAINprobe32行为范围 | 旧64原生分 | 旧64严格正确 | 保留基线原正确题 |
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(lines)+'''

行为范围下界为确认PASS，上界为PASS+UNKNOWN，不是统计置信区间。TRAINprobe来自训练集，不能当泛化成绩。原生分是部分匹配分，不是命令执行成功率；旧64未执行认证。严格匹配使用项目strict_option_values参数值检查，不宣称与官方排行榜Exact Correct完全相同。

![同一GPU上的两模型固定SFT对照](comparison.png)

## 原始解码与统一guard对照：新DEV32

| 模型/协议 | 行为范围 | 严格匹配 | 单个完整output块 | 截断 |
|---|---:|---:|---:|---:|
'''+ '\n'.join(raw_lines)+'''

带raw后缀的行不加ngram guard；其余行使用统一guard。这里是固定诊断，不据此重新挑选checkpoint或改写训练方案。

## 方法与边界

RedSage使用原始RISys-Lab/RedSage-K-SFT-GRPO，保留其推理prefill，并明确沿用BPE空think目标格式；Qwen使用原始Qwen/Qwen3-8B官方非思考模板与直接output目标。两者都是新LoRA，r16/alpha32、q/v、LR2e-5、AdamW、microbatch1/accum4、四轮，未用KL。

主要推理对所有基线和候选统一应用命令块ngram8规则；另完整报告新DEV32不加guard的基线/最终诊断。训练格式不同且监督token数不同，因此这是实际训练配方的对照，不是纯架构或等FLOPs实验。应比较各自相对同机基线的变化，不能将不同任务/协议下的历史分数拼接比较。

执行评分在联网隔离后使用固定v6验收器，正例、替代解与错误反例全部通过预检。hardlink dry-run必须有预期链接计数且文件未改变；另以独立临时目录的shadow执行检验提出的分组，仅移除dry-run标志，不修正工具、选项、路径或值。shadow是验收证据，不能写成模型实际完成了真实链接任务。UNKNOWN未计为错误。

已核验512步完整顺序/监督token/有限非零梯度、固定源模型文件哈希、144个适配器张量变化、四个导出checkpoint哈希与重载后的四题完整回答一致。作业和CPU评分/导出资源已清理，只检查本轮名称，未干预其他会话任务。

这是四工具、一个种子的开发实验。旧DEV64和新DEV32均已用于开发；未查询官方TEST、之前使用过的final64或新的确认面板。没有据此晋升模型，也没有将人工设定SFT称为新的ABA搜索。后续选择须同时看新增任务、旧能力逐题损失和计算开销，再做独立验证与ABA对照。

[完整聚合](summary.json) · [预先冻结协议](protocol.json) · [数据预检](data-preflight.json)
'''
 (dest/'RESULT_ZH.md').write_text(report)
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(11,4.5));colors={'redsage':'#2563eb','qwen':'#0d9488'}
 for index,model in enumerate(['redsage','qwen']):
  base=behavior[model+'_base']['new_dev32']['lower'];trained=behavior[model+'_step256']['new_dev32']['lower'];xs=[index*3,index*3+1]
  upper=[behavior[model+'_base']['new_dev32']['upper'],behavior[model+'_step256']['new_dev32']['upper']]
  axes[0].bar(xs,[base,trained],color=colors[model],alpha=.8)
  axes[0].bar(xs,[u-v for u,v in zip(upper,[base,trained])],bottom=[base,trained],color='white',edgecolor=colors[model],hatch='///',linewidth=1)
  for x,y,u in zip(xs,[base,trained],upper):axes[0].text(x,u+.5,(str(y) if y==u else str(y)+'–'+str(u))+'/32',ha='center',fontsize=9)
  old=[scores[model+'_base']['old64']['native_points'],scores[model+'_step256']['old64']['native_points']];axes[1].bar(xs,old,color=colors[model],alpha=.8)
  for x,y in zip(xs,old):axes[1].text(x,y+1,f'{y:.2f}',ha='center',fontsize=9)
 labels=['RedSage base','RedSage SFT','Qwen base','Qwen SFT']
 for ax in axes:ax.set_xticks([0,1,3,4],labels,rotation=18);ax.spines[['top','right']].set_visible(False)
 from matplotlib.patches import Patch
 axes[0].legend(handles=[Patch(facecolor='#64748b',label='Confirmed PASS'),Patch(facecolor='white',edgecolor='#64748b',hatch='///',label='UNKNOWN')],loc='upper left',fontsize=8,ncol=2,frameon=False)
 axes[0].set_ylim(0,40);axes[0].set_ylabel('Fixture count: confirmed + unresolved');axes[0].set_title('Exposed DEV32: behavioral verification')
 axes[1].set_ylim(0,105);axes[1].set_ylabel('Native partial score (0-100)');axes[1].set_title('Exposed old64: partial matching score')
 fig.suptitle('Original RedSage-K 8B versus Qwen3-8B: fixed 256-update SFT')
 fig.text(.5,.035,'Hatched UNKNOWN is unresolved, not failure or a statistical confidence interval. See report for per-case retention.',ha='center',fontsize=8)
 fig.text(.5,.01,'One seed / four tools / same GPU and row exposure / model-specific serialization / no official TEST or model promotion',ha='center',fontsize=8)
 fig.tight_layout(rect=[0,.07,1,.94]);fig.savefig(dest/'comparison.png',dpi=180);fig.savefig(dest/'comparison.svg');plt.close(fig)
 svg=dest/'comparison.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
 write(DATA/'completion-audit.json',{'status':'COMPLETE_ARTIFACTS_VERIFIED','public_summary_sha256':sha(dest/'summary.json'),'512_steps_checked':True,'all_four_adapters_verified':True,'same_GPU':r['GPU'],'this_pilot_resources_cleaned':True,'needs_visual_figure_inspection_before_push':True})
 print(json.dumps({'completed':True,'public_result_directory':str(dest),'models':list(models),'actual_updates':512},indent=2))
if __name__=='__main__':finalize()
