"""Plot historical prompt interventions separately from prospective fixed-checkpoint transfer."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from recount import HERE,TAGS,combine,load,summarize

def main():
    rows=combine()
    history=load(HERE/'prompt-results.json')
    fig,(left,right)=plt.subplots(1,2,figsize=(10.6,4.5),layout='constrained',gridspec_kw={'width_ratios':[1,1.25]})
    conditions=['Original','Neutral note','Checklist','Teacher hint']
    values=[sum(v['native'] for arms in history.values() for v in arms[a].values()) for a in 'abcd']
    bars=left.barh(conditions,values,color=['#6a777d','#9ba6ab','#287771','#bd8546'])
    left.bar_label(bars,labels=[str(n)+'/9' for n in values],padding=3)
    left.invert_yaxis();left.set_xlim(0,10.3);left.set_xticks([0,3,6,9]);left.set_xlabel('Correct draws on 3 historical prompts')
    left.set_title('Inference-time intervention',loc='left',fontweight='bold')
    left.spines[['right','top','left']].set_visible(False)
    labels=['Original 8B','Answer SFT','Qwen trace SFT','DeepSeek trace SFT']
    for i,(g,c) in enumerate([('previous_prospective','#95adbf'),('new_prospective','#287771')]):
        sel={k:v for k,v in rows.items() if v[0]==g}
        n=len(sel)*3;s=summarize(sel);vs=[s[t]/n for t in TAGS]
        b=right.barh([j+(i-.5)*.36 for j in range(4)],vs,height=.33,color=c,label=f'{len(sel)} '+('earlier' if i==0 else 'new')+' sources')
        right.bar_label(b,labels=[f'{s[t]}/{n}' for t in TAGS],padding=3,fontsize=8)
    right.set_yticks(range(4),labels);right.invert_yaxis();right.set_xlim(0,1.22);right.set_xticks([0,.25,.5,.75,1],['0','25','50','75','100'])
    right.set_xlabel('Correct draws (%)');right.set_title('Transfer to prospective TRAIN sources',loc='left',fontweight='bold')
    right.spines[['right','top','left']].set_visible(False)
    right.legend(loc='upper center',bbox_to_anchor=(.5,-.17),ncol=2,frameon=False,fontsize=9)
    fig.savefig(HERE/'comparison.png',dpi=170,bbox_inches='tight')
if __name__=='__main__':main()
