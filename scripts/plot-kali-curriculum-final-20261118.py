"""Recreate the final scientific figure using ONLY public aggregate JSON.

No questions, answers, model weights, predictions, API keys or GPU are used.
"""
import argparse,json
from pathlib import Path


def plot_results(result,output):
    names=['E0','answer_only','reasoning','A1','A2'];labels=['Base','Answer SFT','Reasoning SFT','ABA A1','ABA A2']
    scores=result['scores']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    colors=['#64748b','#e5a236','#3386c0','#4caa87','#8f72b1']
    for ax,panel,title,n in [(axes[0,0],'development24','Exposed development: thinking',24),(axes[0,1],'old64','Historical capability: thinking',64)]:
        vals=[scores[c]['summary']['thinking'][panel]['mean_correct_per_seed']/n*100 for c in names]
        perseed=[[scores[c]['per_seed'][str(seed)]['thinking'][panel]['correct']/n*100 for seed in result['inference_seeds']] for c in names]
        ax.bar(labels,vals,color=colors)
        for i,(v,rr) in enumerate(zip(vals,perseed)):
            ax.scatter(np.linspace(i-.07,i+.07,len(rr)),rr,s=20,color='black',zorder=3)
            ax.annotate(f'{v:.1f}%',(i,max([v]+rr)),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
        ax.set_ylim(0,min(100,max(vals+[v for rr in perseed for v in rr])+20));ax.set_ylabel('Strict reference correctness (%)');ax.set_title(title);ax.tick_params(axis='x',labelrotation=12)
    conf=result['confirmation'];aliases=conf['aliases'];states=['E0','fixed_answer_only','fixed_reasoning','native_selected'];cnames=['Base','Answer SFT','Reasoning SFT','Native selected']
    ax=axes[1,0]
    values=[conf['summary'][aliases.get(c,c)]['thinking']['mean_correct_per_seed']/24*100 for c in states]
    confirmation_seed_values=[[conf['summary'][aliases.get(c,c)]['thinking']['per_seed'][str(seed)]['correct']/24*100
                              for seed in result['inference_seeds']] for c in states]
    confirmation_colors=colors[:3]+[colors[names.index(result['native']['native_selected_candidate'])]]
    ax.bar(cnames,values,color=confirmation_colors)
    for i,(v,rr) in enumerate(zip(values,confirmation_seed_values)):
        ax.scatter(np.linspace(i-.07,i+.07,len(rr)),rr,s=20,color='black',zorder=3)
        ax.annotate(f'{v:.1f}%',(i,max([v]+rr)),xytext=(0,6),textcoords='offset points',ha='center')
    ax.set_title('Once-frozen confirmation: thinking (24 tasks)');ax.set_ylabel('Strict reference correctness (%)');ax.set_ylim(0,min(100,max(values+[v for rr in confirmation_seed_values for v in rr])+20));ax.tick_params(axis='x',labelrotation=12)
    ax=axes[1,1]
    for cid,color in zip(names[1:],colors[1:]):
        traces=result['conditional_command_CE_traces'][cid]
        ax.plot([r['step'] for r in traces],[r['command_loss_monitor'] for r in traces],label=labels[names.index(cid)],color=color,alpha=.85)
    ax.set_title('Teacher-forced command CE\n(different prefix conditions)');ax.set_xlabel('Optimizer updates');ax.set_ylabel('Conditional command/format CE');ax.legend(fontsize=8)
    fig.suptitle('Verified-teacher pilot: internal diagnostics, not official KaliBench accuracy\n23 independent traces + 6 replay rows; one training seed; 3 inference seeds\nDEV/old and confirmation: original A6000 device type; exact TRAIN reload probes retained.',fontsize=12)
    fig.savefig(Path(output),dpi=180);plt.close(fig)
    return Path(output)


def main():
    default=Path(__file__).resolve().parents[1]/'results/kali-verified-teacher-stage-2026-11-17'
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,default=default/'final-results.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=json.loads(args.results.read_text())
    assert result['status']=='FULL_INTERNAL_STUDY_AUDITED'
    plot_results(result,args.output)
    print('PUBLIC_AGGREGATE_FIGURE_RECREATED_NO_PRIVATE_INPUTS')

if __name__=='__main__':main()
