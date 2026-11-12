#!/usr/bin/env python3
"""Plot public aggregates; refuse an incomplete experiment or missing arm."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main():
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=json.loads(a.summary.read_text());assert x['research_experiment_complete'] and x['official_TEST_rows']==0
 dev={'E0':x['arms']['P11']['score']['summary']['base']['combined']};dev.update({c:v['score']['summary']['candidate']['combined'] for c,v in x['arms'].items()});final=x['confirmation']['summary'];retained=x['selection']['candidate_id'];native=x['selection']['native_selected_candidate'];colors={'E0':'#64748b','P11':'#2563eb','P12':'#0f9d8a','P13':'#d97706','P14':'#9333ea'};labels={'E0':'Original E0','P11':'Fixed publisher','P12':'Fixed +verified64','P13':'ABA P13','P14':'ABA P14'}
 fig,axes=plt.subplots(2,2,figsize=(13.8,8.5));fig.suptitle('KaliBench internal TRAIN-derived study: fixed SFT and bounded native ABA',fontsize=15,fontweight='bold',y=.975)
 for row,(panel,title,nativekey) in enumerate([(dev,'Exposed DEV (128 rows)','native_total_mean'),(final,'Previously unqueried confirmation (64 rows)','native_mean')]):
  ids=list(panel);n=next(iter(panel.values()))['rows'];names=[labels[c]+(' *' if c==retained else '') for c in ids]
  for col in range(2):
   ax=axes[row,col];values=[100*panel[c][nativekey] if col==0 else 100*panel[c]['strict_correct']/n for c in ids];bars=ax.bar(names,values,color=[colors[c] for c in ids],width=.65,edgecolor=['#111827' if c==retained else 'white' for c in ids],linewidth=2)
   for c,bar,val in zip(ids,bars,values):ax.text(bar.get_x()+bar.get_width()/2,val+1.2,f'{val:.2f}' if col==0 else f'{panel[c]["strict_correct"]}/{n}',ha='center',va='bottom',fontsize=9)
   ax.set_ylim(0,105);ax.set_ylabel('Native score ×100' if col==0 else 'Strict correctness (%)');ax.set_title(title+' — '+('native' if col==0 else 'strict'),fontsize=11);ax.tick_params(axis='x',labelsize=8.5);ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.18)
 fig.text(.5,.032,'* Model retained from DEV before confirmation. Native ABA winner: '+native+'. All SFT arms:733 updates;ABA search:2 candidates.\nPublisher/silver internal data;no official TEST score or independent expert-gold claim.',ha='center',fontsize=9,color='#475569');fig.tight_layout(rect=(0,.08,1,.94));a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output.with_suffix('.png'),dpi=180);fig.savefig(a.output.with_suffix('.svg'));svg=a.output.with_suffix('.svg');svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n');plt.close(fig);print(json.dumps({'status':'VERIFIED_STUDY_FIGURE_WRITTEN','png':str(a.output.with_suffix('.png'))}))
if __name__=='__main__':main()
