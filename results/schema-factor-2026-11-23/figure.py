"""Plot raw per-seed strict counts without aggregating model draws as independent tasks."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from recount import HERE,ARMS,load,check_fit,check_screen

def annotate(ax,grid,rows,cols,denom):
    ax.imshow(grid,cmap='BuGn',norm=Normalize(vmin=0,vmax=denom),aspect='auto')
    ax.set_xticks(range(len(cols)),cols)
    ax.set_yticks(range(len(rows)),rows)
    for i,r in enumerate(grid):
        for j,value in enumerate(r):
            ax.text(j,i,f'{value}/{denom}',ha='center',va='center',color='white' if value>denom*.66 else '#132b31')
    ax.tick_params(length=0,pad=5)
    for spine in ax.spines.values():spine.set_visible(False)

def main():
    counts,_=check_fit(load('factor-results.json'))
    screen=check_screen(load('prospective-results.json'))
    fig,axes=plt.subplots(1,2,figsize=(11.3,3.8))
    names=['Answer only','Background','Suppress-defaults cue','Background + copy','Cue + copy']
    annotate(axes[0],[[counts[s][a]['probes'] for s in counts] for a in ARMS],names,list(counts),6)
    axes[0].set_title('Single-source schema probes')
    axes[0].set_xlabel('Training seed')
    arms=['student','A64','B64','C64']
    labels=['Base Qwen3-8B','Answer only','Qwen trajectory','DeepSeek trajectory']
    annotate(axes[1],[[screen['sample_'+s][a] for s in ['6402','7395','7538']] for a in arms],
             labels,['Tags','Assembly table','Statistics'],3)
    axes[1].set_title('Previously trained checkpoints on new sources')
    axes[1].set_xlabel('One TRAIN question per column')
    fig.subplots_adjust(left=.16,right=.99,top=.86,bottom=.23,wspace=.65)
    fig.text(.5,.04,'Left: three prompt variants × two decodes. Right: three decodes per original question. Counts use strict reference scoring.',
             ha='center',fontsize=9)
    fig.savefig(HERE/'diagnostics.png',dpi=160,bbox_inches='tight')
    plt.close(fig)
if __name__=='__main__':main()
