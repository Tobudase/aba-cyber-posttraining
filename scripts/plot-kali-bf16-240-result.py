#!/usr/bin/env python3
"""Plot separate TRAIN, new authored DEV and historical retention readouts."""
import json
import os
from pathlib import Path

os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/kali-results-matplotlib')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results/kali-bf16-240-sft-2026-10-26'


def main():
    s = json.loads((D / 'summary.json').read_text())
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'text.color': '#24354B', 'svg.hashsalt': 'kali-bf16-240-20261026'})
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 6.7))
    fig.subplots_adjust(left=.07, right=.98, top=.71, bottom=.30, wspace=.35)
    fig.suptitle('BF16 SFT | 240 TRAIN rows, one fixed candidate', x=.025, y=.96,
                 ha='left', fontsize=21, weight='bold')
    fig.text(.025, .885, 'RedSage-K ~8B | 480 updates | Same-card BF16 before/after | Greedy batch4 inference', fontsize=12)
    for ax, (field, title, count, metric) in zip(axes, [
        ('TRAIN_diagnostic', 'A  Selected TRAIN diagnostic', 16, 'correct'),
        ('DEV', 'B  New authored DEV (12 groups)', 72, 'correct'),
        ('retention', 'C  Historical retention sentinel', 24, 'strict_correct')]):
        vals = [s[field][arm][metric] for arm in ['base', 'sft']]
        ax.bar([0, 1], [100 * v / count for v in vals], width=.56, color=['#2463A6', '#27806D'])
        for i, v in enumerate(vals):
            ax.text(i, 100 * v / count + 3, f'{v}/{count}', ha='center', fontsize=13, weight='bold')
        ax.set_xticks([0, 1], ['Original base', 'After SFT'])
        ax.set_ylim(0, 113)
        ax.set_yticks([0, 25, 50, 75, 100], ['0%', '25%', '50%', '75%', '100%'])
        ax.set_title(title, loc='left', fontsize=12, weight='bold', pad=16)
        ax.set_ylabel('Verified correctness' if field != 'retention' else 'Strict diagnostic correctness')
        ax.grid(axis='y', color='#E2E8EF')
        ax.set_axisbelow(True)
        for edge in ['top', 'right']:
            ax.spines[edge].set_visible(False)
    gate = s['development_gate']
    fig.text(.025, .205, f"Predeclared development gate: {'PASS' if gate['passes_development_gate'] else 'FAIL'} | Conservative DEV gain lower bound: {gate['conservative_DEV_gain_lower_bound']:+d} rows", fontsize=12, weight='bold')
    fig.text(.025, .145, f"DEV unknown syntax not executed: base {s['DEV']['base']['unsupported']}, SFT {s['DEV']['sft']['unsupported']}. Candidate truncated outputs: {s['formats']['sft']['truncated']}/112.", fontsize=10.5)
    fig.text(.025, .09, 'DEV and TRAIN have disjoint intent groups but shared synthetic generators/fixtures; retention was previously exposed. No official scores.', fontsize=10)
    fig.text(.025, .04, 'One seed and correlated variants; no significance or independent-source generalization claim. Original base remains the formal default.', fontsize=10)
    for suffix in ['png', 'svg']:
        path = D / ('before-after.' + suffix)
        fig.savefig(path, dpi=180, facecolor='white', metadata={'Date': None} if suffix == 'svg' else None)
        if suffix == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(fig)
    print('RENDERED_BF16_240_READOUTS')


if __name__ == '__main__':
    main()
