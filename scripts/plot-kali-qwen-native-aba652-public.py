#!/usr/bin/env python3
"""Plot aggregate-only matched SFT accuracy; no private row content required."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-native-aba652-2026-11-02"


def main():
    d = json.loads((OUT / "aggregate.json").read_text())
    names = ["validation16", "old_dev64", "utility_primary36", "utility_all108"]
    labels = ["Family holdout\n(n=16)", "Old domain\n(n=64)",
              "Utility primary\n(n=36)", "Utility all\n(n=108)"]
    control = [d["sets"][n]["control"]["strict_correct"] / d["sets"][n]["control"]["rows"] * 100 for n in names]
    treatment = [d["sets"][n]["treatment"]["strict_correct"] / d["sets"][n]["treatment"]["rows"] * 100 for n in names]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.80, bottom=0.23)
    fig.patch.set_facecolor("white")
    width = 0.35
    blue, orange = "#3769A5", "#D07831"
    left = ax.bar(x - width / 2, control, width, color=blue, label="Control: publisher TRAIN repeats")
    right = ax.bar(x + width / 2, treatment, width, color=orange, label="Treatment: native ABA data")
    for bars, arm in ((left, "control"), (right, "treatment")):
        for bar, name in zip(bars, names):
            row = d["sets"][name][arm]
            ax.annotate(f'{row["strict_correct"]}/{row["rows"]}',
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 76)
    ax.set_ylabel("Strict correctness (%)")
    fig.text(0.09, 0.94, "Native ABA TRAIN data: matched Qwen3-8B SFT", fontsize=14, weight="bold")
    fig.text(0.09, 0.89, "Exposed development diagnostics · no official benchmark or blind gold score",
             fontsize=9, color="#555555")
    fig.legend(handles=[left.patches[0], right.patches[0]], labels=["Control: publisher TRAIN repeats", "Treatment: native ABA data"],
               loc="lower left", frameon=False, ncol=2, bbox_to_anchor=(0.09, 0.045))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    ax.set_axisbelow(True)
    svg = OUT / "strict-accuracy.svg"
    fig.savefig(svg)
    # Matplotlib's path serialization leaves whitespace before line breaks;
    # normalize it so the committed figure passes git diff --check.
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(OUT / "strict-accuracy.png", dpi=160)
    plt.close(fig)
    print(OUT / "strict-accuracy.png")


if __name__ == "__main__":
    main()
