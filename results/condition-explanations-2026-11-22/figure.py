"""Plot the paired diagnostic by decoding seed. Each column pair comes from one TRAIN source."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.patches import Patch
import numpy as np

def draw(data, destination):
    views=[('same','Omit defaults'),('opposite','Retain defaults'),('distractor','Retain + distraction')]
    arms=['base','A16','A64','B64','C64']
    labels=['Original Qwen3-8B','Answer only · 16 steps','Answer only · 64 steps',
            'Qwen trajectory · 64 steps','DeepSeek trajectory · 64 steps']
    codes=[]; marks=[]
    for arm in arms:
        grid=[];text=[]
        for name,_ in views:
            for seed in ('11341','11351'):
                r=data[arm][seed][name]
                if r['strict']:value,label=3,'Pass'
                elif r['behavior']:value,label=2,'JSON'
                elif r['issue']=='truncated':value,label=1,'Cap'
                else:value,label=0,{'native-error':'Tool','different-output':'Output','no-unambiguous-command':'Parse','unreviewed':'Other'}.get(r['issue'],'Fail')
                if label=='Tool':label='Tool error'
                if label=='Output':label='Wrong output' if r['format'] else 'Output + JSON'
                grid.append(value);text.append(label)
        codes.append(grid);marks.append(text)
    colors=['#f1d9c6','#f5edc9','#d9e6f3','#c2dfda']
    fig,ax=plt.subplots(figsize=(10.2,4.8));fig.subplots_adjust(left=.25,right=.98,top=.75,bottom=.18)
    ax.imshow(np.array(codes),aspect='auto',cmap=ListedColormap(colors),norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4))
    ax.set_yticks(range(len(arms)),labels);ax.set_xticks(range(6),['11341','11351']*3)
    ax.tick_params(length=0,pad=6)
    for col,(_,name) in enumerate(views):
        ax.text(2*col+.5,-.72,name,ha='center',va='center',fontsize=11,fontweight='bold')
    for y,row in enumerate(marks):
        for x,s in enumerate(row):ax.text(x,y,s,ha='center',va='center',fontsize=10,color='#1c3036')
    for x in range(1,6):ax.axvline(x-.5,color='white',lw=4 if x%2==0 else 1)
    for y in range(1,5):ax.axhline(y-.5,color='white',lw=2)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.05,.94,'Does the student follow a change in one schema requirement?',weight='bold',fontsize=16)
    fig.text(.05,.875,'Same filename on every prompt. Two decoding seeds. Each response checked against three synthetic databases.',fontsize=10)
    fig.legend(handles=[Patch(color=colors[3],label='Passed format and execution checks'),
                        Patch(color=colors[0],label='Failed execution checks')],
               loc='lower center',ncol=2,frameon=False,fontsize=9)
    fig.savefig(destination,dpi=170,facecolor='white')
    plt.close(fig)
if __name__=='__main__':
    root=Path(__file__).resolve().parent
    draw(json.loads((root/'adapter-grades.json').read_text()),root/'same-file-pairs.png')
