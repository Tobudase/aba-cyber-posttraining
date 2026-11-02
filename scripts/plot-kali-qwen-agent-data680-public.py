#!/usr/bin/env python3
"""Plot aggregate-only exploratory results; no question or prediction text."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-qwen-agent-data680-2026-11-02"


def main():
    data = json.loads((OUT / "aggregate.json").read_text())
    assert data["status"] == "SCORED_AGENT_DATA_MATCHED_SFT_EXPLORATORY"
    assert data["official_TEST_rows"] == 0 and data["model_promotion"] is False
    groups = [("Family holdout\n16", "validation16"), ("Old domain\n64", "old_dev64"),
              ("Exposed utility\n108", "utility_all108")]
    control = [data["sets"][name]["control"]["strict_correct"] for _, name in groups]
    treatment = [data["sets"][name]["treatment"]["strict_correct"] for _, name in groups]
    assert control == treatment == [10, 22, 72]
    base = data["sets"]["validation16"]["base"]["strict_correct"]
    assert base == 8
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(7.2, 4.1), dpi=160)
    width = 0.26
    left = ax.bar(x - 0.18, control, width, label="Matched control SFT", color="#8197aa")
    right = ax.bar(x + 0.18, treatment, width, label="Model paraphrase SFT", color="#2a768f")
    for bars in (left, right):
        for bar in bars:
            ax.annotate(f"{bar.get_height():.0f}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
    ax.annotate("Base: 8/16", (x[0], 20), ha="center", fontsize=9)
    ax.set_xticks(x, [label for label, _ in groups])
    ax.set_ylim(0, 85)
    ax.set_ylabel("Strict correct count")
    ax.set_title("Qwen3-8B model-paraphrase pilot: no strict-score gain")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.5, 0.02, "Exploratory, same-source family holdout; not official KaliBench or native ABA",
             ha="center", fontsize=7.5, color="#555555")
    fig.tight_layout(rect=(0, 0.055, 1, 1))
    fig.savefig(OUT / "strict-counts.png", bbox_inches="tight")
    fig.savefig(OUT / "strict-counts.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
