"""Recount the released outcomes without model weights or a GPU."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def check_explanations(audit):
    assert set(audit["summary"]) == {"base", "A64", "B64", "C64"}
    assert len(audit["rows"]) == 60
    for model, summary in audit["summary"].items():
        rows = [r for r in audit["rows"] if r["arm"] == model]
        assert len(rows) == len({(r["source"], r["seed"]) for r in rows}) == 15
        assert Counter(r["label"] for r in rows) == summary["labels"]
        for metric in ("strict", "recoverable_behavior"):
            assert sum(r[metric] for r in rows) == summary[metric]
        assert sum(r["strict"] and r["label"] == "supported" for r in rows) == summary["strict_and_supported"]


def check_screen(ledger):
    records = [r for r in ledger["new_results"].values() if r["calibrated"]]
    counts = ledger["source_screen"]
    assert len(records) == counts["new"] == 8
    assert all(len(r["grades"]) == 3 for r in records)
    grades = [grade for r in records for grade in r["grades"].values()]
    assert len(grades) == counts["new_draws"] == 24
    assert grades.count("pass") == counts["new_student_passes"] == 23
    assert counts["old"] + len(records) == counts["cumulative"] == 64
    assert len(set(counts["prior_qualified"] + counts["new_qualified"])) == counts["total_qualified"] == 3


def check_replication(fit):
    groups = {"original": ["original"], "reverse": ["reverse", "reverse_reworded"],
              "distractor": ["distractor"], "new_sources": ["7476", "7545"]}
    checkpoints = fit["checkpoints"]
    assert set(checkpoints) == {"A", "B", "C"}
    assert all(set(steps) == {"16", "32", "64"} for steps in checkpoints.values())
    assert len({v["weights"] for steps in checkpoints.values() for v in steps.values()}) == 9
    rows = fit["draws"]
    assert len(rows) == len({(r["model"], r["source"], r["seed"]) for r in rows}) == 54
    for model in ("base", "A64", "B64", "C64"):
        for group, probes in groups.items():
            subset = [r for r in rows if r["model"] == model and r["source"] in probes]
            assert len(subset) == 2 * len(probes)
            assert fit["primary"][model][group] == [sum(r["strict"] for r in subset), len(subset)]
    for teacher in ("B", "C"):
        recall = [r for r in rows if r["model"] == teacher + "64" and r["source"] == "original"]
        assert sum(r["trace_matches"][teacher] for r in recall) == 2
    assert sum(r["model"] == "C64" and r["tokens"] == 4096 and not r["ended"] for r in rows) == 4


if __name__ == "__main__":
    ledger = read("evidence.json")
    check_explanations(ledger["explanations"])
    check_screen(ledger)
    check_replication(read("second-source-sft.json"))
    print("Verified 60 explanation reviews, 24 screening draws, 54 replication draws and 9 checkpoint hashes.")
