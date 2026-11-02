#!/usr/bin/env python3
"""Plot public in-family aggregate without private questions or predictions."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-native-infamily16-2026-11-02"


def main():
    d = json.loads((OUT / "aggregate.json").read_text())
    arms = ["base", "control", "treatment"]
    labels = ["Original base", "Matched control", "ABA-data treatment"]
    strict = [d["frozen_strict"][arm]["strict_correct"] for arm in arms]
    behavior = [d["posthoc_expanded_safe_linux_execution"][arm]["passed"] for arm in arms]
    x = np.arange(3)
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    fig.subplots_adjust(left=0.11, right=0.97, top=0.78, bottom=0.23)
    fig.patch.set_facecolor("white")
    a = ax.bar(x-width/2, strict, width, color="#3769A5", label="Frozen strict")
    b = ax.bar(x+width/2, behavior, width, color="#D07831", label="Posthoc Linux fixture")
    for bars in (a,b):
        for bar in bars:
            ax.annotate(f"{int(bar.get_height())}/16", (bar.get_x()+bar.get_width()/2,bar.get_height()),
                        xytext=(0,4),textcoords="offset points",ha="center",va="bottom",fontsize=10)
    ax.set_xticks(x, labels)
    ax.set_ylim(0,18)
    ax.set_ylabel("Correct out of 16")
    ax.grid(axis="y",color="#dddddd",linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top","right"]].set_visible(False)
    fig.text(0.11,0.93,"New-filename diagnostic: strict score vs fixture behavior",fontsize=13,weight="bold")
    fig.text(0.11,0.86,"Adaptive same-family tasks · posthoc execution policy · no official benchmark score",
             fontsize=9,color="#555555")
    fig.legend(handles=[a.patches[0],b.patches[0]],labels=["Frozen strict","Posthoc Linux fixture"],
               loc="lower left",frameon=False,ncol=2,bbox_to_anchor=(0.11,0.05))
    svg=OUT/"strict-vs-fixture.svg"
    fig.savefig(svg)
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines())+"\n")
    fig.savefig(OUT/"strict-vs-fixture.png",dpi=160)
    plt.close(fig)
    print(OUT/"strict-vs-fixture.png")


if __name__=="__main__":
    main()
