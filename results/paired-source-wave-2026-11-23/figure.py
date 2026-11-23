"""Render study results from two public receipts, keeping original and reverse probes separate."""
from collections import Counter
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = Path(__file__).resolve().parent
screen = json.loads((folder / "screening.json").read_text())
reverse = json.loads((folder / "reverse-directions.json").read_text())["sources"]
rows = screen["rows"]
histogram = Counter(sum(r["final"] == "pass" for r in s["draws"].values()) for s in rows.values())
figure, (left, right) = plt.subplots(1, 2, figsize=(9.2, 4.2), layout="constrained",
                                     gridspec_kw={"width_ratios": [1, 1.4]})
left.bar(range(4), [histogram[i] for i in range(4)], color="#287771", width=.63)
for i in range(4):
    left.text(i, histogram[i] + .25, str(histogram[i]), ha="center")
left.set_xticks(range(4), ["0/3", "1/3", "2/3", "3/3"])
left.set_ylim(0, max(histogram.values()) * 1.18 + 1)
left.set_yticks(range(0, 21, 4))
left.set_ylabel("Number of new sources")
left.set_xlabel("Student successes per source")
left.set_title("Original TRAIN prompts", loc="left", fontweight="bold")
for index, (model, color) in enumerate([("Student", "#287771"), ("Qwen teacher", "#607eac"), ("DeepSeek teacher", "#c58b38")]):
    values = []
    for k in ("6118", "6137", "7293"):
        record = reverse[k]
        if model == "Student":
            draws = list(record["student"].values())
        else:
            prefix = model.split()[0].lower() + "-"
            draws = [a for s, a in record["teachers"].items() if s.startswith(prefix)]
        values.append(sum(r["strict"] for r in draws))
    bars = right.bar([i + (index-1)*.24 for i in range(3)], values, width=.22, label=model, color=color)
    right.bar_label(bars, padding=2, fontsize=9)
right.set_xticks(range(3), ["JSON export", "Schema defaults", "Module list"])
right.set_ylabel("Successful draws out of 3")
right.set_ylim(0, 3.7)
right.set_yticks(range(4))
right.set_title("Reversed requests on historical sources", loc="left", fontweight="bold")
right.legend(loc="lower center", bbox_to_anchor=(.49, -.28), ncol=3, frameon=False, fontsize=8)
for axis in (left, right):
    axis.spines[["top","right"]].set_visible(False)
figure.savefig(folder / "screening-results.png", dpi=170, bbox_inches="tight")
