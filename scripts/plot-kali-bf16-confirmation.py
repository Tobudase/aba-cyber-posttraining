#!/usr/bin/env python3
"""Plot only completed aggregate confirmation counts."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'results/kali-bf16-confirmation-2026-10-26'
def main():
 s=json.loads((D/'summary.json').read_text());fig,axs=plt.subplots(1,2,figsize=(9,4),layout='constrained')
 for ax,key,title,n,metric in zip(axs,['CONFIRMATION','retention'],['Held-out synthetic confirmation','Exposed historical retention'],[72,24],['correct','strict_correct']):
  values=[s[key][arm][metric] for arm in ['base','sft']]
  bars=ax.bar(['Original base','Saved SFT adapter'],values,color=['#607890','#178a78'],width=.58)
  ax.set_ylim(0,n*1.16);ax.set_ylabel('Verified correct' if key=='CONFIRMATION' else 'Strict diagnostic correct');ax.set_title(title,fontsize=11)
  for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,v+n*.025,f'{v}/{n}',ha='center',fontweight='bold')
  ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.yaxis.grid(alpha=.15)
 fig.suptitle('Same-card BF16 • exact existing adapter • zero new training',fontsize=12)
 fig.text(.5,-.035,'Same generator family; 6 correlated variants per group. Not official KaliBench or independent-source proof.',ha='center',fontsize=8)
 for ext in ['png','svg']:fig.savefig(D/('before-after.'+ext),dpi=180,bbox_inches='tight')
 plt.close(fig)
if __name__=='__main__':main()
