"""Show single-source observations without implying independent-source accuracy."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
root=Path(__file__).resolve().parent
def main():
    s=json.loads((root/'single-aligned-results.json').read_text());r=s['details']
    keys=['base']+[a+str(k) for a in 'ABC' for k in (16,32,64)]
    grid=np.array([[2 if r[tag+'-'+q]['strict'] else 1 if r[tag+'-'+q]['behavior'] else 0 for q in ('train','fresh','contrast')] for tag in keys])
    fig,ax=plt.subplots(figsize=(8.0,6.1))
    ax.imshow(grid,cmap=ListedColormap(['#edf0f2','#f4ce89','#247768']),vmin=0,vmax=2,aspect='auto')
    ax.set_xticks(range(3),['Training prompt','New file + wording','Reversed requirement']);ax.xaxis.tick_top()
    ax.set_yticks(range(len(keys)),['Base Qwen3-8B']+[label+' · '+str(k) for label in ('Answer only','Qwen trace','DeepSeek trace') for k in (16,32,64)])
    for y in range(len(keys)):
        for x in range(3):ax.text(x,y,['Fail','Behavior only','Pass'][grid[y,x]],ha='center',va='center',color='white' if grid[y,x]==2 else '#273542',fontsize=10)
    for y in (0.5,3.5,6.5):ax.axhline(y,color='white',lw=3)
    ax.tick_params(length=0,pad=7);ax.spines[:].set_visible(False)
    fig.suptitle('Can a student learn one verified teacher demonstration?',fontweight='bold',fontsize=16,y=.98)
    fig.text(.5,.905,'Qwen3-8B · matched JSON supervision · one training seed · NVIDIA A10',ha='center',fontsize=10)
    fig.text(.5,.043,'One official TRAIN source, three prompts. Each behavior check uses three synthetic databases.',ha='center',fontsize=9)
    fig.subplots_adjust(left=.28,right=.98,top=.82,bottom=.09)
    fig.savefig(root/'matched-checkpoints.png',dpi=180,bbox_inches='tight');plt.close(fig)
if __name__=='__main__':main()
