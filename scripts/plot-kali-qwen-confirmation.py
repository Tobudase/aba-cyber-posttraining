#!/usr/bin/env python3
"""Plot published aggregate Qwen results; no private examples are read."""

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/kali-qwen-matplotlib")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "results/kali-qwen-official-executed-pilot-2026-10-28/cycle-summary.json"
CONFIRM = ROOT / "results/kali-qwen-confirmation-2026-10-28/summary.json"
TRIAGE = ROOT / "results/kali-qwen-confirmation-2026-10-28/mechanical-triage.json"
OUT = CONFIRM.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    pilot = json.loads(PILOT.read_text())
    confirm = json.loads(CONFIRM.read_text())
    triage = json.loads(TRIAGE.read_text())
    assert pilot["model_id"] == confirm["model_id"] == "Qwen/Qwen3-8B"
    assert pilot["saved_adapter_sha256"] == confirm["prior_adapter_sha256"]
    assert pilot["optimizer_steps"] == 512 and confirm["optimizer_steps_this_run"] == 0
    assert pilot["official_TEST_rows_opened"] == confirm["official_TEST_rows_opened"] == 0
    assert triage["case_counts"] == {"gained": 9, "lost": 1, "both_wrong_truncated": 3}

    primary = confirm["sets"]["primary87"]
    unseen = confirm["sets"]["primary_tool_absent_from_train22"]
    rows = [
        ("Initial DEV\n128 rows", 128, pilot["strict_correct_counts"]["baseline"],
         pilot["strict_correct_counts"]["post_sft"]),
        ("Unqueried primary\n87 rows", primary["rows"], primary["baseline"]["strict_correct_count"],
         primary["post_sft"]["strict_correct_count"]),
        ("TRAIN-unseen tools\n22 rows", unseen["rows"], unseen["baseline"]["strict_correct_count"],
         unseen["post_sft"]["strict_correct_count"]),
    ]
    assert rows == [
        ("Initial DEV\n128 rows", 128, 29, 43),
        ("Unqueried primary\n87 rows", 87, 18, 26),
        ("TRAIN-unseen tools\n22 rows", 22, 5, 5),
    ]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5,
                         "text.color": "#20334B", "axes.labelcolor": "#20334B",
                         "svg.hashsalt": "kali-qwen-confirmation-20261028"})
    fig = plt.figure(figsize=(14, 7), facecolor="white")
    grid = fig.add_gridspec(1, 2, left=.07, right=.97, top=.73, bottom=.31,
                            width_ratios=[1.5, 1], wspace=.25)
    ax = fig.add_subplot(grid[0, 0])
    bx = fig.add_subplot(grid[0, 1])
    fig.suptitle("Qwen3-8B fixed SFT | KaliBench internal holdouts", x=.07, y=.96,
                 ha="left", fontsize=20, weight="bold")
    fig.text(.07, .905, "512 publisher-verified TRAIN rows  |  512 QLoRA updates  |  paired base vs saved adapter  |  one seed",
             fontsize=11)
    fig.text(.07, .855, "Strict tool + option-value correctness; percentages within each separately defined set",
             fontsize=10.5, color="#516377")

    before_color, after_color = "#285F9B", "#238472"
    for i, (label, n, before, after) in enumerate(rows):
        for pos, value, color in ((i - .19, before, before_color), (i + .19, after, after_color)):
            ax.bar(pos, 100 * value / n, width=.35, color=color, zorder=3)
            ax.text(pos, 100 * value / n + 1.6, f"{value}/{n}", ha="center", va="bottom",
                    fontsize=10, weight="bold")
    ax.set_xticks(range(3), [x[0] for x in rows])
    ax.set_ylim(0, 43)
    ax.set_yticks([0, 10, 20, 30, 40], ["0%", "10%", "20%", "30%", "40%"])
    ax.set_ylabel("Strict correctness")
    ax.set_title("A  Before and after SFT", loc="left", weight="bold", pad=12)
    ax.grid(axis="y", color="#E2E8EF", zorder=0)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=before_color),
               plt.Rectangle((0, 0), 1, 1, color=after_color)],
              ["Original Qwen3-8B", "After fixed SFT"], frameon=False,
              loc="upper left", ncol=2, bbox_to_anchor=(0, 1.01))

    paired = primary["paired"]["strict"]
    categories = [
        ("Gained", paired["gained"], after_color),
        ("Lost", paired["lost"], "#B75C4D"),
        ("Correct in both", paired["both_correct"], before_color),
        ("Wrong in both", paired["both_wrong"], "#AAB7C6"),
    ]
    assert sum(v for _, v, _ in categories) == 87
    for y, (name, value, color) in enumerate(categories):
        bx.barh(y, value, height=.57, color=color, zorder=3)
        bx.text(value + .8, y, str(value), va="center", weight="bold", fontsize=11)
    bx.set_yticks(range(4), [x[0] for x in categories])
    bx.invert_yaxis()
    bx.set_xlim(0, 67)
    bx.set_xlabel("Rows in the unqueried primary set (n=87)")
    bx.set_title("B  Paired outcomes on 87 rows", loc="left", weight="bold", pad=12)
    bx.grid(axis="x", color="#E2E8EF", zorder=0)
    for axis in (ax, bx):
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)

    fig.text(.07, .175, "Reliability: 0/93 -> 3/93 outputs hit the 512-token cap after SFT; all three remained wrong.",
             fontsize=11, weight="bold", color="#983E37")
    fig.text(.07, .12, "The 22 unseen-tool rows are a subset of the 87; they show no net strict gain (5/22 -> 5/22).",
             fontsize=10.5)
    fig.text(.07, .072, "Official TRAIN internal splits, publisher silver labels. No official TEST, external blind validation, or ABA search.",
             fontsize=10, color="#516377")
    fig.text(.07, .037, "This is a diagnostic, not an official leaderboard score. The original formal base remains unchanged.",
             fontsize=10, color="#516377")

    files = {}
    for ext in ("png", "svg"):
        path = OUT / f"before-after.{ext}"
        kwargs = {"dpi": 180, "facecolor": "white"}
        if ext == "svg":
            kwargs["metadata"] = {"Date": None}
        fig.savefig(path, **kwargs)
        if ext == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
        files[path.name] = sha(path)
    plt.close(fig)
    manifest = {"status": "RENDERED_FROM_PUBLIC_AGGREGATES", "matplotlib_version": plt.matplotlib.__version__,
                "source_sha256": {p.name: sha(p) for p in (PILOT, CONFIRM, TRIAGE)},
                "figure_sha256": files, "official_TEST_rows": 0}
    (OUT / "figure-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("RENDERED_QWEN_CONFIRMATION_FIGURE")


if __name__ == "__main__":
    main()
