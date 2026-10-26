#!/usr/bin/env python3
"""Render aggregate-only research figures; no inference, GPU or private inputs.

Requires matplotlib==3.10.7. Run from any directory. Data are read directly
from published JSON receipts, never entered manually as chart values.
"""
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/kali-results-matplotlib")
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kali-results-figures-2026-10-26"
SOURCES = {
    "history": "results/kali-seed43-replication-2026-10-25/summary.json",
    "initial": "results/kali-cuda-2026-10-24/comparison.json",
    "newline": "results/kali-causal-findings-2026-10-25/summary.json",
    "resegmentation": "results/kali-prefix-control-2026-10-26/same-text-resegmentation.json",
    "loss_weight": "results/kali-prefix-control-2026-10-26/matched-control.json",
}
BLUE, ORANGE, GREEN, INK = "#2463A6", "#D47A22", "#27806D", "#24354B"


def read(name):
    return json.loads((ROOT / SOURCES[name]).read_text())


def style(ax):
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(PercentFormatter(100))
    ax.grid(axis="x", color="#E2E8EF", linewidth=0.8)
    ax.set_axisbelow(True)
    for edge in ["top", "right", "left"]:
        ax.spines[edge].set_visible(False)
    ax.spines["bottom"].set_color("#CFD8E3")
    ax.tick_params(axis="y", length=0, pad=8)
    ax.set_xlabel("Strict correctness")


def save(fig, stem):
    for suffix in ["png", "svg"]:
        metadata = {"Date": None} if suffix == "svg" else None
        path = OUT / f"{stem}.{suffix}"
        fig.savefig(path, dpi=180, facecolor="white", metadata=metadata)
        if suffix == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


def label(ax, value, denominator, y):
    percentage = 100 * value / denominator
    ax.text(percentage + 1.4, y, f"{value}/{denominator}", va="center",
            fontsize=10, color=INK)


def grouped(axes, sets, conditions, metrics):
    for ax, (metric, title) in zip(axes, metrics):
        style(ax)
        ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=15)
        for i, (key, _) in enumerate(conditions):
            for precision, color, offset, hatch in [
                ("NF4_TRAIN", BLUE, -0.18, None),
                ("BF16", ORANGE, 0.18, "//"),
            ]:
                record = sets[f"{key}_{precision}"]
                assert record["rows"] == 8 and 0 <= record[metric] <= 8
                y = i + offset
                ax.barh(y, record[metric] / 8 * 100, height=0.30,
                        color=color, hatch=hatch, edgecolor="white")
                label(ax, record[metric], 8, y)
        ax.set_yticks(range(len(conditions)), [x[1] for x in conditions])
        ax.invert_yaxis()
        ax.set_xlabel("Fraction of the same 8 TRAIN examples")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "text.color": INK, "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK,
                         "svg.hashsalt": "kali-results-2026-10-26"})
    history, initial, newline = read("history"), read("initial"), read("newline")
    # Cross-check the earlier cycle and seed42 repair against original records.
    for group in ["domain", "retention"]:
        for hkey, ikey in [("base", "baseline"), ("seed42_compact", "post")]:
            h = history["scores"][hkey][group]
            old = initial["comparisons"][group]
            assert h["rows"] == old["rows"]
            assert abs(h["strict_correct"] / h["rows"] * 100
                       - old[ikey]["strict_option_value_correct"]) < 1e-10
        assert history["scores"]["seed42_newline"][group]["strict_correct"] == newline["scores"]["target_newline"][group]["strict_correct"]
    assert history["decision"]["formal_default_remains_original_base"]
    conditions = [("base", "Original base"), ("seed42_compact", "Compact target / seed 42"),
                  ("seed42_newline", "Newline target / seed 42"),
                  ("seed43_compact", "Compact target / seed 43"),
                  ("seed43_newline", "Newline target / seed 43")]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))
    fig.subplots_adjust(left=.155, right=.98, top=.70, bottom=.26, wspace=.62)
    fig.suptitle("KaliBench project | Earlier development and transfer checks", x=.025,
                 y=.97, ha="left", fontsize=20, weight="bold")
    fig.text(.025, .88, "RedSage-K ~8B | Historical NF4 final-only protocol | Self-authored diagnostics, not official benchmark scores", fontsize=12)
    for ax, (group, title) in zip(axes, [("domain", "A  Domain DEV (36 rows)"),
                              ("retention", "B  Retention DEV (72 rows)"),
                              ("transfer", "C  Transfer panel (24 rows)")]):
        style(ax)
        ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=15)
        for i, (key, _) in enumerate(conditions):
            record = history["scores"][key][group]
            ax.barh(i, 100 * record["strict_correct"] / record["rows"], height=.55,
                    color=BLUE if key == "base" else GREEN if "newline" in key else ORANGE)
            label(ax, record["strict_correct"], record["rows"], i)
        ax.set_yticks(range(len(conditions)), [x[1] for x in conditions])
        ax.invert_yaxis()
    fig.text(.025, .14, "Observed: newline targets recover the exposed retention drop across two seeds; the transfer panel does not improve over the base.", fontsize=12, weight="bold")
    fig.text(.025, .085, "DEV was used during investigation; rows include correlated variants. Transfer was frozen before calls, but authored after failures were known.", fontsize=10)
    fig.text(.025, .045, "Two seeds are descriptive, not a statistical significance claim. Strict correctness is an additional diagnostic, not the official native Total Score.", fontsize=10)
    save(fig, "01-development-and-transfer")

    reseg = read("resegmentation")
    assert not reseg["training_sanity_gate_passed"] and reseg["selected_arm"] is None
    assert reseg["sets"]["resegmented_BF16"]["truncated"] == 1
    conditions = [("base", "Original base"), ("canonical", "Canonical target SFT"),
                  ("resegmented", "BPE target SFT (experimental)")]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))
    fig.subplots_adjust(left=.18, right=.98, top=.70, bottom=.29, wspace=.72)
    fig.suptitle("Latest TRAIN-only control | Same target text, different token segmentation",
                 x=.025, y=.97, ha="left", fontsize=19, weight="bold")
    fig.text(.025, .88, "RTX 3090 | Both SFT arms trained in NF4, 128 updates each | Same 8 selected TRAIN examples in every panel", fontsize=12)
    grouped(axes, reseg["sets"], conditions, [("correct", "A  Strict correctness"),
            ("format_complete", "B  Complete output block"), ("think_closed", "C  Closing think tag")])
    fig.legend(handles=[Patch(facecolor=BLUE, label="NF4 inference"),
                        Patch(facecolor=ORANGE, hatch="//", label="BF16 inference (cross-precision)")],
               loc="upper left", bbox_to_anchor=(.025, .84), frameon=False, ncol=2)
    fig.text(.025, .17, "Full predeclared reliability gate: FAILED. The BPE-target adapter has 1 truncated BF16 response (1024-token cap).", fontsize=12, weight="bold", color="#9C3F23")
    fig.text(.025, .105, "NF4 fitting/output recovery is local to these 8 TRAIN rows. BF16 consistency, held-out improvement and production readiness are not established.", fontsize=10)
    fig.text(.025, .055, "Only training-target segmentation changed; decoded text and inference tokenizer/prompt stayed fixed. Supervised tokens: 240 -> 248.", fontsize=10)
    save(fig, "02-train-segmentation-control")

    weight = read("loss_weight")
    assert not weight["training_sanity_gate_passed"]
    fig, ax = plt.subplots(figsize=(11, 5.7))
    fig.subplots_adjust(left=.26, right=.95, top=.66, bottom=.28)
    fig.suptitle("Critical-prefix loss weighting | Negative control result", x=.025,
                 y=.96, ha="left", fontsize=18, weight="bold")
    fig.text(.025, .86, "NVIDIA L4 | Both SFT arms trained in NF4, 128 updates each | 8 selected TRAIN rows", fontsize=11)
    grouped([ax], weight["sets"], [("base", "Original base"), ("uniform", "Uniform loss (weight 1)"),
            ("prefix8", "Critical-token weight 8")], [("correct", "Strict correctness by inference precision")])
    fig.legend(handles=[Patch(facecolor=BLUE, label="NF4 inference"),
                        Patch(facecolor=ORANGE, hatch="//", label="BF16 inference")],
               loc="upper left", bbox_to_anchor=(.025, .82), frameon=False, ncol=2)
    fig.text(.025, .15, "Neither arm passed the frozen sanity gate; weighting alone did not recover NF4 output generation.", fontsize=11, weight="bold")
    fig.text(.025, .08, "This is a separate same-card experiment from the RTX 3090 segmentation control; do not pool scores across studies.", fontsize=10)
    save(fig, "03-critical-prefix-loss-control")

    data = {"as_of": "2026-10-26", "model": "RISys-Lab/RedSage-K-SFT-GRPO",
            "model_revision": history["model_revision"], "matplotlib_version": matplotlib.__version__,
            "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES.values()},
            "history": {k: history["scores"][k] for k, _ in [
                ("base", ""), ("seed42_compact", ""), ("seed42_newline", ""),
                ("seed43_compact", ""), ("seed43_newline", "")]},
            "segmentation_TRAIN_sets": reseg["sets"], "loss_weight_TRAIN_sets": weight["sets"],
            "full_segmentation_gate_passed": False, "formal_default": "original_base",
            "new_model_calls_or_training_steps": 0,
            "scope": "Previously published aggregate diagnostics; no official scores or independent generalization claim."}
    (OUT / "plotted-data.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"status": "FIGURES_RENDERED", "figures": 3, "formats": ["png", "svg"],
                      "source_files": len(SOURCES), "new_model_calls": 0}))


if __name__ == "__main__":
    main()
