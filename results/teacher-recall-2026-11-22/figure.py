"""Plot per-source strict passes without pooling heterogeneous checks."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

HERE = Path(__file__).resolve().parent


def main():
    x = json.loads((HERE/'transfer.json').read_text())
    tags = ['base', 'A64', 'B64', 'C64']
    sources = ['sample_7293', 'sample_6118']
    seeds = [str(s) for s in x['seeds']]
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3), sharey=True)
    for p, source, label in zip(ax, sources, ['List LLVM functions', 'Export database records']):
        grades = x['sources'][source]
        grid = [[int(grades[t][s]['strict_pass']) for s in seeds] for t in tags]
        p.imshow(grid, vmin=0, vmax=1, cmap=ListedColormap(['#f0e6da', '#91d1bc']), aspect='auto')
        for i, values in enumerate(grid):
            for j, value in enumerate(values):
                p.text(j, i, 'Pass' if value else 'Miss', ha='center',va='center',color='#1f3438')
        p.set_xticks(range(len(seeds)), seeds)
        p.set_yticks(range(len(tags)), ['Base Qwen3-8B','Answer only','Qwen trajectory','DeepSeek trajectory'])
        p.tick_params(length=0, pad=5)
        p.set_xlabel('Decoding seed')
        p.set_title(label, fontsize=12)
        for spine in p.spines.values():
            spine.set_visible(False)
    fig.suptitle('Transfer from one schema training example', fontsize=14,weight='bold')
    fig.text(.5,.022,'Two previously screened TRAIN sources. Each cell is one generation scored on two fixtures.',
             ha='center', fontsize=9)
    fig.subplots_adjust(left=.21, right=.98, top=.77, bottom=.24, wspace=.10)
    fig.savefig(HERE/'transfer.png',dpi=170,facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    main()
