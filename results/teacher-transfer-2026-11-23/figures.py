"""Draw both study figures from the published per-response records."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

HERE = Path(__file__).resolve().parent
MODELS = {
    "base": "Original Qwen3-8B",
    "A64": "Answer-only SFT",
    "B64": "Qwen trajectory SFT",
    "C64": "DeepSeek trajectory SFT",
}


def draw_transfer():
    prompts = {
        "original": "Training\nprompt",
        "distractor": "Irrelevant\nnote",
        "reverse": "Reversed\nrequest",
        "reverse_reworded": "Reversed,\nreworded",
        "7476": "Partition\nbitcode",
        "7545": "Verify\nuse order",
    }
    draws = json.loads((HERE / "second-source-sft.json").read_text())["draws"]
    values = []
    for model in MODELS:
        counts = []
        for prompt in prompts:
            group = [r for r in draws if r["model"] == model and r["source"] == prompt]
            assert {r["seed"] for r in group} == {"11341", "11351"} and len(group) == 2
            counts.append(sum(r["strict"] for r in group))
        values.append(counts)

    fig, ax = plt.subplots(figsize=(9.3, 3.6), layout="constrained")
    ax.imshow(values, cmap=ListedColormap(["#f1f3f2", "#acccc8", "#236965"]),
              vmin=0, vmax=2, aspect="auto")
    for i, row in enumerate(values):
        for j, count in enumerate(row):
            ax.text(j, i, f"{count}/2", ha="center", va="center", fontsize=12,
                    color="white" if count == 2 else "#172b2b")
    ax.axvline(3.5, color="white", lw=5)
    ax.set_xticks(range(len(prompts)), labels=prompts.values())
    ax.set_yticks(range(len(MODELS)), labels=MODELS.values())
    ax.tick_params(length=0, pad=8)
    ax.set_title("Strict task success after training on one function-listing example",
                 loc="left", fontweight="bold", pad=14)
    ax.set_xlabel("First four columns share the training source. Last two are separate TRAIN sources.", labelpad=10)
    ax.spines[:].set_visible(False)
    fig.savefig(HERE / "second-source-transfer.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def draw_explanations():
    rows = json.loads((HERE / "evidence.json").read_text())["explanations"]["rows"]
    measures = [
        ("Strict task success", "#334f6d", lambda r: r["strict"]),
        ("Behavior after replay", "#22847c", lambda r: r["recoverable_behavior"]),
        ("Explanation meets rubric", "#ab6b20", lambda r: r["label"] == "supported"),
    ]
    fig, ax = plt.subplots(figsize=(8.2, 4.3), layout="constrained")
    for i, (label, color, passed) in enumerate(measures):
        values = []
        for model in MODELS:
            group = [r for r in rows if r["arm"] == model]
            assert len(group) == 15
            values.append(sum(passed(r) for r in group))
        bars = ax.barh([j + (i-1)*0.23 for j in range(4)], values,
                       height=0.20, label=label, color=color)
        ax.bar_label(bars, padding=3, fontsize=9)
    ax.set_yticks(range(len(MODELS)), labels=MODELS.values())
    ax.invert_yaxis()
    ax.set_xlim(0, 16.3)
    ax.set_xticks([0, 3, 6, 9, 12, 15])
    ax.set_xlabel("Passing responses out of 15 per model")
    ax.set_title("Task execution and explanation quality on five sources",
                 loc="left", fontweight="bold", pad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False, fontsize=8.5)
    fig.savefig(HERE / "execution-and-explanations.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    draw_transfer()
    draw_explanations()
