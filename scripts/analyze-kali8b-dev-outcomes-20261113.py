#!/usr/bin/env python3
"""Describe exposed DEV outcomes only; never read final64 or modify selection.

Reads private per-case scores. Exports aggregates without prompts, responses,
reference commands, or case IDs. These are exploratory diagnostics, not an
independent test or an intervention demonstrating a unique cause.
"""
import hashlib
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "data/benchkit/kali-8b-verified64-study-2026-11-12"


def read(path):
    return json.loads(path.read_text())


def main():
    selection = STUDY / "native-selection-private.json"
    before = hashlib.sha256(selection.read_bytes()).hexdigest()
    result = {
        "status": "POSTHOC_EXPOSED_DEV_UNCERTAINTY_ONLY",
        "selection_changed": False,
        "model_calls": 0,
        "confirmation_used": False,
        "official_TEST_rows": 0,
        "bootstrap_draws": 10000,
        "seed": 20261113,
        "limits": (
            "Paired item bootstrap and unadjusted exact McNemar on exposed DEV "
            "only. Exploratory; sample dependence and prior adaptation prevent "
            "independent generalization or confirmatory significance claims. "
            "No selection or score changes."
        ),
        "arms": {},
    }
    for cid in ["P11", "P12", "P13", "P14"]:
        detail = read(STUDY / cid / "run/score-detail-private.json")
        ids = sorted(detail["base"])
        assert len(ids) == 128 and set(ids) == set(detail["candidate"])
        differences = [
            detail["candidate"][i]["native_total"] - detail["base"][i]["native_total"]
            for i in ids
        ]
        gained = sum(not detail["base"][i]["strict"] and detail["candidate"][i]["strict"] for i in ids)
        lost = sum(detail["base"][i]["strict"] and not detail["candidate"][i]["strict"] for i in ids)
        discordant = gained + lost
        p = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(gained, lost) + 1)) / 2**discordant) if discordant else 1.0
        rng = random.Random(result["seed"])
        bootstrap = sorted(
            sum(differences[rng.randrange(len(ids))] for _ in ids) / len(ids)
            for _ in range(result["bootstrap_draws"])
        )
        score = read(STUDY / cid / "run/scores-private.json")
        assert score["paired_strict"] == {"gained": gained, "lost": lost}
        assert abs(sum(differences) / len(ids) - score["native_delta"]) < 1e-12
        result["arms"][cid] = {
            "rows": len(ids),
            "native_delta": sum(differences) / len(ids),
            "paired_bootstrap_percentile_95_interval": [bootstrap[249], bootstrap[9749]],
            "strict_gained": gained,
            "strict_lost": lost,
            "strict_delta_correct": gained - lost,
            "unadjusted_exact_McNemar_two_sided": p,
        }
    assert hashlib.sha256(selection.read_bytes()).hexdigest() == before
    output = STUDY / "DEV-uncertainty-aggregate.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "arms": result["arms"]}))


if __name__ == "__main__":
    main()
