#!/usr/bin/env python3
"""Plot sanitized exploratory utility results from aggregate counts only."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/kali-qwen-utility-retention-2026-10-31"


def main():
    data = json.loads((RUN / "aggregate.json").read_text())
    assert data["status"] == "EXPLORATORY_SELF_AUTHORED_UTILITY_RETENTION_ONLY"
    keys = ["primary_dev_confirm36", "secondary_dev_search72", "all108"]
    labels = ["Confirm (36, 6 families)", "Search (72, 12 families)", "All (108, 18 families)"]
    sets = [data["sets"][key] for key in keys]
    x = np.arange(3)
    width = 0.35
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), constrained_layout=True)
    base_color, tuned_color = "#64748b", "#bf4b37"
    for ax, field_base, field_post, title, ylabel in [
        (axes[0], "strict_baseline", "strict_post_sft", "Strict command correctness", "Correct (%)"),
        (axes[1], "native_total_baseline", "native_total_post_sft", "Native scorer total", "Score (0–100)"),
    ]:
        baseline = [d[field_base] / d["rows"] * 100 if field_base == "strict_baseline" else d[field_base]
                    for d in sets]
        tuned = [d[field_post] / d["rows"] * 100 if field_post == "strict_post_sft" else d[field_post]
                 for d in sets]
        left = ax.bar(x - width / 2, baseline, width, label="Base Qwen3-8B", color=base_color)
        right = ax.bar(x + width / 2, tuned, width, label="After 638-row SFT", color=tuned_color)
        ax.bar_label(left, fmt="%.1f", padding=2, fontsize=8)
        ax.bar_label(right, fmt="%.1f", padding=2, fontsize=8)
        ax.set_xticks(x, labels, rotation=15, ha="right", fontsize=8)
        ax.set_ylim(0, 110)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(loc="upper left", frameon=False, fontsize=8)
    fig.suptitle("Exploratory, self-authored CLI utility retention (not official KaliBench)", fontsize=11)
    fig.text(0.5, -0.03, "Six correlated filename variants per family; baseline/post SFT use matched prompts and decoding.",
             ha="center", fontsize=8, color="#475569")
    for extension in ("svg", "png"):
        fig.savefig(RUN / ("before-after." + extension), dpi=180, bbox_inches="tight")
    svg = RUN / "before-after.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    print(str(RUN / "before-after.svg"))


if __name__ == "__main__":
    main()
