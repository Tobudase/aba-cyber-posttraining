"""Draw main-panel outcome counts using the published per-file verdicts."""
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

def render(records, destination):
    cases=[r for r in records if r['split']=='holdout']
    colors=['#2e7564','#52769a','#d8ad65','#dce0e5']
    labels=['Correct triple','Wrong triple','Ended without valid JSON','No recorded EOS']
    arms=['base','answer','reason']
    fig,ax=plt.subplots(figsize=(7.2,2.8),layout='constrained')
    for y,arm in enumerate(arms):
        outcomes=[r['arms'][arm] for r in cases]
        counts=[sum(z['numeric']=='pass' for z in outcomes),sum(z['numeric']=='fail' for z in outcomes),
                sum(z['numeric']=='unknown' and z['ended'] for z in outcomes),sum(not z['ended'] for z in outcomes)]
        assert sum(counts)==len(cases)
        start=0
        for n,color in zip(counts,colors):
            ax.barh(y,n,left=start,color=color,height=.63)
            if n:
                ax.text(start+n/2,y,str(n),va='center',ha='center',fontsize=10,
                        color='white' if color in colors[:2] else '#26313c')
            start+=n
    ax.set_yticks(range(3),['Qwen3-8B','Answer SFT','Evidence SFT'])
    ax.invert_yaxis();ax.set_xlim(0,len(cases));ax.set_xticks([0,6,12,18,24])
    ax.set_xlabel('Held-out files');ax.set_title('SQLite field extraction on 24 new files',loc='left',fontweight='bold')
    ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0)
    ax.legend(handles=[Patch(color=c,label=l) for c,l in zip(colors,labels)],ncol=2,loc='upper left',
              frameon=False,bbox_to_anchor=(0,-.30),fontsize=8,borderaxespad=0)
    fig.savefig(destination,dpi=180,bbox_inches='tight');plt.close(fig)
if __name__=='__main__':
    directory=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    render(json.loads((directory/'paired-file-verdicts.json').read_text()),directory/'new-file-outcomes.png')
