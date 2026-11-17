"""Plot aggregate fixed-pilot results, never raw prompts or responses."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 p=argparse.ArgumentParser();p.add_argument('--result-dir',type=Path,default=Path('results/kali-rationale-sft-results-2026-11-17'));a=p.parse_args();d=json.loads((a.result_dir/'summary.json').read_text())
 arms=['base','base_nonthinking','answer_only','reasoning'];names=['Base\n(thinking)','Base\n(no thinking)*','Answer-only\nSFT','Brief-rationale\nSFT'];colors=['#64748b','#b5beca','#287d8e','#c47d3e'];metrics={**d['summary'],'base_nonthinking':d['nonthinking_control']['summary']}
 fig,axs=plt.subplots(2,2,figsize=(12,8));fig.suptitle('Qwen3-8B: fixed answer-only vs brief-rationale SFT pilot',fontsize=17)
 for ax,panel,title in [(axs[0,0],'development24','Development: strict reference correctness (n=24)'),(axs[0,1],'old64','Previously exposed retention panel (n=64)')]:
  vals=[100*metrics[k][panel]['strict']/metrics[k][panel]['n'] for k in arms]
  ax.bar(names,vals,color=colors);ax.set_ylim(0,30);ax.set_ylabel('Strict correctness (%)');ax.set_title(title,fontsize=11)
  for i,k in enumerate(arms):s=metrics[k][panel];ax.text(i,vals[i]+2,f"{s['strict']}/{s['n']} ({vals[i]:.1f}%)",ha='center',fontsize=10)
 vals=[sum(metrics[k][p]['truncated'] for p in ['development24','old64']) for k in arms];ax=axs[1,0];ax.bar(names,vals,color=colors);ax.set_ylim(0,96);ax.set_ylabel('Truncated answers / 88');ax.set_title('Output reliability at the frozen 1,024-token cap',fontsize=11)
 for i,v in enumerate(vals):ax.text(i,v+2,str(v),ha='center')
 vals=[sum(metrics[k][p]['tokens'] for p in ['development24','old64'])/88 for k in arms];ax=axs[1,1];ax.bar(names,vals,color=colors);ax.set_ylim(0,1150);ax.set_ylabel('Mean generated tokens');ax.set_title('Generation length (includes visible thinking)',fontsize=11)
 for i,v in enumerate(vals):ax.text(i,v+20,f'{v:.1f}',ha='center')
 for ax in axs.flat:ax.spines[['top','right']].set_visible(False);ax.tick_params(axis='x',labelsize=9)
 fig.text(.5,.018,'One seed; 48 TRAIN variants / six schemas. Greedy thinking decoding is not the Qwen-recommended setting.\n*Extra prompt-mode control. Rationale DEV: 1/24 frozen; 2/24 after one verified alias (post hoc).',ha='center',fontsize=10)
 fig.tight_layout(rect=[0,.075,1,.95]);fig.savefig(a.result_dir/'comparison.png',dpi=160);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(11,4.5));fig.suptitle('Training diagnostics — same 48 updates, different target-token exposure')
 for arm,name,color in zip(arms[2:],['Answer-only SFT','Brief-rationale SFT'],colors[2:]):
  for ax,key in zip(axs,['epoch_mean_loss','epoch_mean_command_loss']):ax.plot(range(1,5),d['training'][arm][key],marker='o',label=name,color=color)
 axs[0].set_title('Full supervised-target loss');axs[1].set_title('Answer-segment loss (output tags + command + EOS)')
 for ax in axs:ax.set_xlabel('Epoch');ax.set_ylabel('Mean token cross-entropy');ax.set_xticks(range(1,5));ax.legend();ax.spines[['top','right']].set_visible(False)
 fig.text(.5,.015,'Targets and teacher-forced contexts differ; absolute losses across arms do not directly measure relative ability.',ha='center',fontsize=9)
 fig.tight_layout(rect=[0,.05,1,.93]);fig.savefig(a.result_dir/'training.png',dpi=160);plt.close(fig)
if __name__=='__main__':main()
