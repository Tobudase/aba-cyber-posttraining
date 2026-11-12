#!/usr/bin/env python3
"""Plot only collected fixed controls; never impute pending ABA results."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
def main():
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=json.loads(a.summary.read_text());assert x['official_TEST_rows']==0
 arms=x['arms'];assert all(arms[c]['status']=='COLLECTED' for c in ['P11','P12']);b=arms['P11']['score']['summary']['base'];assert b==arms['P12']['score']['summary']['base'];series={'E0':b,**{c:arms[c]['score']['summary']['candidate'] for c in ['P11','P12']}};colors=['#64748b','#2563eb','#0f9d8a'];names=['Original E0','Publisher P11','Mixed P12'];fig,axes=plt.subplots(1,3,figsize=(13,4.9));fig.suptitle('Verified 8B fixed controls: internal exposed DEV, not an official benchmark score',fontsize=13,fontweight='bold',y=.975)
 for j in [0,1]:
  ax=axes[j];values=[100*s['combined']['native_total_mean'] if j==0 else 100*s['combined']['strict_correct']/128 for s in series.values()];bars=ax.bar(names,values,color=colors,width=.62)
  for bar,s,val in zip(bars,series.values(),values):ax.text(bar.get_x()+bar.get_width()/2,val+1.5,f'{val:.2f}' if j==0 else f'{s["combined"]["strict_correct"]}/128',ha='center',fontsize=10)
  ax.set_ylim(0,100);ax.set_title('Native mean ×100' if j==0 else 'Strict correctness (%)',fontsize=11)
 ax=axes[2];loc=np.arange(2);w=.32
 for c,color,offset in [('P11',colors[1],-.5),('P12',colors[2],.5)]:
  s=series[c];vals=[100*(s[t]['native_total_mean']-b[t]['native_total_mean']) for t in ['dev1','dev2']];bars=ax.bar(loc+offset*w,vals,width=w,label=c,color=color)
  for bar,val in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,val+(.25 if val>=0 else -.25),f'{val:+.2f}',ha='center',va='bottom' if val>=0 else 'top',fontsize=9)
 ax.axhline(0,color='#64748b',linewidth=.8);ax.axhline(-2,color='#dc2626',linestyle='--',linewidth=1,label='Retention floor');ax.set_xticks(loc,['DEV1 (64)','DEV2 (64)']);ax.set_ylim(-6,8);ax.set_title('Native change from E0 (points)',fontsize=11);ax.legend(frameon=False,fontsize=8,loc='upper right')
 for ax in axes:ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.18);ax.tick_params(axis='x',labelsize=9)
 fig.text(.5,.035,'733 updates and 17,439 supervised tokens per SFT arm; 64 new silver rows replace 64 publisher records.\nBoth controls fail frozen gates. P13/P14 native ABA and sealed64 results are not shown or imputed.',ha='center',fontsize=9,color='#475569');fig.tight_layout(rect=(0,.13,1,.92));a.output.parent.mkdir(parents=True,exist_ok=True)
 for ext in ['png','svg']:fig.savefig(a.output.with_suffix('.'+ext),dpi=180)
 plt.close(fig);print('VERIFIED_FIXED_CONTROL_FIGURE_WRITTEN')
if __name__=='__main__':main()
