"""Plot completed diagnostic results; no inference, selection, or score changes."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]/'results/kali-mode-repair-2026-11-16'
COLORS = ['#3670a0', '#c16a36']
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})


def bars(ax, labels, values, totals, title):
    rates = [100*v/n for v, n in zip(values, totals)]
    ax.bar(labels, rates, color=COLORS[:len(labels)], width=.58)
    ax.set_ylim(0, 116)
    ax.set_title(title, loc='left', fontweight='bold')
    ax.set_ylabel('Confirmed success (%)')
    ax.set_yticks([0, 25, 50, 75, 100])
    for i, (rate, value, total) in enumerate(zip(rates, values, totals)):
        ax.text(i, rate+3, f'{value}/{total}', ha='center', fontweight='bold')
    ax.grid(axis='y', alpha=.15)
    ax.set_axisbelow(True)


if (ROOT/'v11-analysis.json').exists():
    a = json.loads((ROOT/'v11-analysis.json').read_text())
    rows = [a['results'][k] for k in ['conditional_KL', 'direct_command_CE']]
    labels = ['Conditional KL', 'Direct CE']
    fig, axes = plt.subplots(2, 3, figsize=(13, 8))
    for ax, key, title in zip(axes.flat, ['train384','legacy64','new_dev32','shifted_dev64'],
                             ['Full TRAIN fit', 'Legacy fixtures', 'Exposed development', 'Shifted exposed development']):
        bars(ax, labels, [r[key]['pass'] for r in rows], [r[key]['n'] for r in rows], title)
    bars(axes[1,1], labels, [r['old_retained'] for r in rows], [r['old_base_correct'] for r in rows], 'Old strict-correct retention')
    axes[1,1].set_ylabel('Strict-correct retention (%)')
    modes = list(rows[0]['new_delta_PyI64_modes'])
    ax = axes[1,2]
    for j, r in enumerate(rows):
        ax.bar([i+(j-.5)*.36 for i in range(4)], [r['new_delta_PyI64_modes'][m]['pass'] for m in modes],
               width=.36, color=COLORS[j], label=labels[j])
    ax.set_xticks(range(4), [m.replace('_','\n') for m in modes]);ax.set_ylim(0,21);ax.set_yticks([0,4,8,12,16])
    ax.set_ylabel('Functional PASS / 16');ax.set_title('Balanced new PyInstaller modes',loc='left',fontweight='bold');ax.legend(fontsize=8)
    fig.suptitle('Same-source, same-order, 192-step objective comparison',fontweight='bold',fontsize=15)
    fig.text(.5,.015,'One seed; continued RedSage R120. TRAIN and exposed DEV only. UNKNOWN is not counted as PASS. No independent-test gain claim.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,.95]);fig.savefig(ROOT/'objective-comparison.png',dpi=180);plt.close(fig)

if (ROOT/'v12-analysis.json').exists():
    a = json.loads((ROOT/'v12-analysis.json').read_text())
    fig, axes = plt.subplots(2,2,figsize=(11,7))
    names = ['observed_DEV','matched_TRAIN_root','matched_length_0','matched_length_1']
    labels = ['DEV root','v9 TRAIN root','Matched-length A','Matched-length B']
    for ax, (arm, r) in zip(axes.flat, a['arms'].items()):
        p = [sum(x['verdicts'][n]=='fixture_pass' for x in r['pairs']) for n in names]
        u = [sum(x['verdicts'][n].startswith('unknown') for x in r['pairs']) for n in names]
        f = [12-pp-uu for pp,uu in zip(p,u)]
        ax.bar(labels,p,color='#3670a0',label='PASS')
        ax.bar(labels,f,bottom=p,color='#c16a36',label='Non-PASS, decided')
        ax.bar(labels,u,bottom=[pp+ff for pp,ff in zip(p,f)],color='#b9bdc2',label='UNKNOWN')
        ax.set_ylim(0,14);ax.set_ylabel('12 diagnostic pairs');ax.set_title(arm)
        ax.tick_params(axis='x',labelsize=8)
        for i,n in enumerate(p):ax.text(i,12.3,str(n)+'/12 PASS',ha='center',fontsize=8)
    handles,labels_legend = axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels_legend,loc='lower center',ncol=3,bbox_to_anchor=(.5,.025))
    fig.suptitle('Directory substitution diagnosis: source R120, no training',fontweight='bold')
    fig.text(.5,.008,'12 selected pairs share 6 templates; paired v9 TRAIN rows were not in R120 TRAIN. Sensitivity diagnosis, not a benchmark score.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.09,1,.95]);fig.savefig(ROOT/'path-invariance.png',dpi=180);plt.close(fig)

if (ROOT/'v13-analysis.json').exists():
    a = json.loads((ROOT/'v13-analysis.json').read_text())
    rows = [a['results'][k] for k in ['existing_intents','missing_intents']]
    labels = ['Existing replay','Missing-intent replay']
    fig, axes = plt.subplots(2,3,figsize=(13,8))
    for ax,key,title in zip(axes.flat,['train384','legacy64','newDEV32','shiftedDEV64'],
                            ['Full TRAIN fit','Legacy fixtures','Exposed development','Shifted exposed development']):
        bars(ax,labels,[r[key]['pass'] for r in rows],[r[key]['n'] for r in rows],title)
    bars(axes[1,1],labels,[r['old_base_retained'] for r in rows],[r['old_base_correct'] for r in rows],'Old strict-correct retention')
    axes[1,1].set_ylabel('Strict-correct retention (%)')
    aux=a['auxiliary24_training_fit_only']
    bars(axes[1,2],labels,[aux[r['label']]['source_parser_contract_matches'] for r in rows],[24,24],'New auxiliary TRAIN parser fit')
    source=json.loads((ROOT/'v11-analysis.json').read_text())['results']['direct_command_CE']
    source_counts=[(source[key]['pass'],source[key]['n']) for key in ['train384','legacy64','new_dev32','shifted_dev64']]
    source_counts += [(source['old_retained'],source['old_base_correct']),(aux['W0']['source_parser_contract_matches'],24)]
    for ax,(value,total) in zip(axes.flat,source_counts):
        ax.axhline(100*value/total,color='#30343b',linestyle='--',linewidth=1.2)
        for annotation in ax.texts:
            x,y=annotation.get_position()
            annotation.set_position((x,max(y,100*value/total+3)))
    fig.suptitle('Replay-content comparison: same source, 96 updates per arm',fontweight='bold',fontsize=15)
    fig.text(.5,.035,'Dashed lines: frozen CE source. Confirmed PASS excludes UNKNOWN; unresolved counts are reported in the accompanying table.',ha='center',fontsize=9)
    fig.text(.5,.015,'Single-seed adaptive DEV comparison. Auxiliary24 is TRAIN fit; old64 uses native/strict scoring, not runtime behavior. No independent-test claim.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,.95]);fig.savefig(ROOT/'replay-content-comparison.png',dpi=180);plt.close(fig)
