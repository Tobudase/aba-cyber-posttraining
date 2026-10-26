#!/usr/bin/env python3
"""Draw the full TRAIN-only precision matrix from published aggregates."""
import json
import os
from pathlib import Path

os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/kali-results-matplotlib')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results/kali-matched-precision-2026-10-26'


def main():
    summary = json.loads((D / 'summary.json').read_text())
    matrix = [[summary['sets'][key] for key in keys] for keys in [
        ['base_NF4', 'base_BF16'], ['NF4_training_NF4', 'NF4_training_BF16'],
        ['BF16_training_NF4', 'BF16_training_BF16']]]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'text.color': '#24354B', 'svg.hashsalt': 'kali-precision-20261026'})
    fig, ax = plt.subplots(figsize=(12.5, 8.5))
    fig.subplots_adjust(left=.24, right=.97, top=.71, bottom=.23)
    fig.suptitle('TRAIN-only precision control | Matched modes both fit 8/8',
                 x=.035, y=.96, ha='left', fontsize=20, weight='bold')
    fig.text(.035, .895, 'RedSage-K ~8B | Same 8 selected TRAIN rows | 128 updates per arm | One NVIDIA L4', fontsize=12)
    fig.text(.035, .85, 'Shared initial LoRA state and data order; fixed batch4 greedy inference; experimental same-text BPE targets.', fontsize=10.5)
    ax.imshow([[cell['correct'] / 8 for cell in row] for row in matrix],
              cmap='Blues', vmin=0, vmax=1, aspect='auto', interpolation='nearest')
    ax.set_xticks([0, 1], ['NF4 inference', 'BF16 inference'])
    ax.xaxis.tick_top()
    ax.tick_params(axis='x', length=0, pad=12)
    ax.set_yticks([0, 1, 2], ['Original base', 'NF4-trained adapter', 'BF16-trained adapter'])
    ax.tick_params(axis='y', length=0, pad=12)
    for i, row in enumerate(matrix):
        for j, cell in enumerate(row):
            color = 'white' if cell['correct'] >= 6 else '#24354B'
            ax.text(j, i - .13, f"{cell['correct']}/8 correct", color=color,
                    ha='center', va='center', fontsize=21, weight='bold')
            ax.text(j, i + .16, f"Output {cell['format_complete']}/8 | Close {cell['think_closed']}/8 | Truncated {cell['truncated']}",
                    color=color, ha='center', va='center', fontsize=10)
            if (i, j) in [(1, 0), (2, 1)]:
                ax.add_patch(Rectangle((j - .48, i - .47), .96, .94,
                                      fill=False, edgecolor='#2CB888', linewidth=3))
    ax.set_xticks([-.5, .5, 1.5], minor=True)
    ax.set_yticks([-.5, .5, 1.5, 2.5], minor=True)
    ax.grid(which='minor', color='white', linewidth=3)
    ax.tick_params(which='minor', bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(.035, .16, 'Green outline: predeclared matched-diagonal gates PASS. All four trained-model cells have zero truncation.', fontsize=11, weight='bold')
    fig.text(.035, .105, 'These are training examples, not held-out gains. Keep the original base pending DEV and retention checks.', fontsize=11)
    fig.text(.035, .055, 'Older cross-precision gate remains FAILED. BF16 base is freshly measured at 3/8; do not compare it as a gain over prior batch1 results.', fontsize=9.5)
    for suffix in ['png', 'svg']:
        path = D / ('precision-matrix.' + suffix)
        fig.savefig(path, dpi=180, facecolor='white', metadata={'Date': None} if suffix == 'svg' else None)
        if suffix == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(fig)
    print('RENDERED_TRAIN_ONLY_PRECISION_MATRIX')


if __name__ == '__main__':
    main()
