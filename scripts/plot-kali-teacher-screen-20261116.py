"""Figure from saved scores; pending student arms are never plotted as zero."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'results/kali-teacher-screen-2026-11-16'
s=json.loads((D/'aggregate.json').read_text())
labels={'qwen3-small':'Qwen3.8 27B\nFP8 teacher','gemma-small':'Gemma 4 12B\nQAT teacher','student_nonthinking':'Qwen3 8B\nnon-thinking','student_thinking':'Qwen3 8B\nthinking'}
arms=list(s['arms']);fig,axes=plt.subplots(1,2,figsize=(10.5,4.8))
for ax,metric,title,color in zip(axes,['strict','truncated'],['Reference strict matches','Output truncations'],['#297f99','#d47736']):
    values=[s['arms'][a][metric] for a in arms]
    ax.bar(range(len(arms)),values,color=color,width=.58)
    for i,v in enumerate(values):ax.text(i,v+1,f'{v}/67',ha='center',fontsize=11)
    ax.set_xticks(range(len(arms)),[labels[a] for a in arms],fontsize=10)
    ax.set_ylim(0,67);ax.set_ylabel('Cases (67 requested per arm)');ax.set_title(title)
    ax.spines[['right','top']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('Isolated TRAIN screening — no SFT or official TEST',fontsize=14)
pending='Student baselines pending GPU allocation; not measured, not zero.' if 'student_thinking' not in s['arms'] else 'One seeded sample per mode; reference matches are not functional correctness.'
fig.text(.5,.05,pending,ha='center',fontsize=10)
fig.text(.5,.015,'Selected offline-analysis subset; 4,096-token budget. Zero reasoning traces admitted to SFT.',ha='center',fontsize=9,color='#444444')
fig.tight_layout(rect=[0,.11,1,.94]);fig.savefig(D/'screening.png',dpi=180);plt.close(fig)
print(D/'screening.png')
