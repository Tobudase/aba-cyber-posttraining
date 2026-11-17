"""Preparation counts, not model performance."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path(__file__).resolve().parents[1]/'results/kali-rationale-sft-prep-2026-11-17'
s=json.loads((D/'summary.json').read_text());names={'relocations':'Relocations','packer_format':'Packer formats','scanner_defaults':'Scanner defaults','imports_exports':'Imports/exports','optional_directories':'Header/directories','defined_symbols':'Defined symbols'}
fig,axes=plt.subplots(1,2,figsize=(10.5,4.7),gridspec_kw={'width_ratios':[1.2,1]})
keys=list(s['data_review']['families']);counts=[s['data_review']['families'][k] for k in keys]
axes[0].barh([names[k] for k in keys],counts,color='#377d8e');axes[0].set_xlim(0,10);axes[0].set_xlabel('Verified TRAIN variants');axes[0].set_title('48 variants across six schemas')
for i,c in enumerate(counts):axes[0].text(c+.15,i,str(c),va='center')
values=[s['encoding'][a]['supervised_tokens_per_epoch'] for a in ['answer_only','reasoning']]
axes[1].bar(['Answer-only','Brief rationale'],values,color=['#377d8e','#c47b41']);axes[1].set_ylim(0,6000);axes[1].set_ylabel('Supervised tokens per epoch');axes[1].set_title('Same rows; unequal token exposure')
for i,c in enumerate(values):axes[1].text(i,c+100,f'{c:,}',ha='center')
for ax in axes:ax.spines[['top','right']].set_visible(False)
fig.suptitle('Prepared SFT comparison — no student training yet',fontsize=14)
fig.text(.5,.025,'48 positive + 48 negative controls checked; narrow AI-reviewed pilot, not independent performance evidence.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.07,1,.93]);fig.savefig(D/'preparation.png',dpi=180);plt.close(fig)
