#!/usr/bin/env python3
"""Plot the sanitized matched-arm exploratory result from public counts only."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/kali-qwen-targeted-650-2026-10-31"


def main():
    data = json.loads((RUN / "summary.json").read_text())
    assert data["status"] == "COMPLETE_EXPLORATORY_MATCHED_650_ARMS_GATE_FAILED"
    assert data["gate_passed"] is False and data["official_KaliBench_TEST_rows"] == 0
    keys = ["domain_internal_dev64", "utility_primary_confirm36", "utility_secondary_search72"]
    labels = ["Domain DEV64", "CLI primary36", "CLI secondary72"]
    sets = [data["sets"][key] for key in keys]
    x = np.arange(3)
    width = 0.35
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.25), constrained_layout=True)
    for ax, field, title, ylabel in [
        (axes[0], "strict_correct", "Strict correctness", "Correct (%)"),
        (axes[1], "native_total", "Native scorer total", "Score (0–100)"),
    ]:
        def value(row, arm):
            v = row[arm][field]
            return v / row["rows"] * 100 if field == "strict_correct" else v

        control = [value(row, "control") for row in sets]
        treatment = [value(row, "treatment") for row in sets]
        left = ax.bar(x - width / 2, control, width, color="#64748b", label="Control: +12 domain")
        right = ax.bar(x + width / 2, treatment, width, color="#bf4b37", label="Treatment: +12 CLI")
        ax.bar_label(left, fmt="%.1f", padding=2, fontsize=8)
        ax.bar_label(right, fmt="%.1f", padding=2, fontsize=8)
        ax.set_xticks(x, labels, rotation=12, ha="right", fontsize=8)
        ax.set_ylim(0, 110)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("Qwen3-8B matched 650-step SFT: exploratory, exposed development sets", fontsize=11)
    fig.text(0.5, -0.03, "One seed; no official TEST; 12 targeted CLI rows did not pass the predeclared gate.",
             ha="center", fontsize=8, color="#475569")
    for extension in ("svg", "png"):
        fig.savefig(RUN / ("control-treatment." + extension), dpi=180, bbox_inches="tight")
    svg = RUN / "control-treatment.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    print(str(svg))


if __name__ == "__main__":
    main()
