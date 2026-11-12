#!/usr/bin/env python3
"""Frozen synthetic dev scorer; standard library only."""
import argparse
import json
import math
from pathlib import Path

def evaluate(model_path):
    root = Path(__file__).resolve().parent
    model = json.loads((Path(model_path) / "model.json").read_text())
    base = json.loads((root / "base_model.json").read_text())
    assert model["format"] == "synthetic-bigram-v1" and model["vocab_size"] == 8
    w = model["weights"]
    assert len(w) == 8 and all(len(row) == 8 for row in w)
    assert all(isinstance(x, (float, int)) and math.isfinite(x) for row in w for x in row)
    steps = model["optimizer_steps"]
    assert isinstance(steps, int) and 0 <= steps <= 16384
    loss = 0.0
    correct = 0
    rows = [json.loads(line) for line in (root / "dev.jsonl").read_text().splitlines()]
    for record in rows:
        logits = w[record["context"]]
        top = max(logits)
        loss += top + math.log(sum(math.exp(x - top) for x in logits)) - logits[record["target"]]
        correct += max(range(8), key=lambda j: logits[j]) == record["target"]
    nll = loss / len(rows)
    change = sum(abs(w[i][j] - base["weights"][i][j]) for i in range(8) for j in range(8))
    return {"score": -nll, "dev_nll": nll, "accuracy": correct / len(rows), "parameter_l1_change": change, "optimizer_steps": steps}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model-path", required=True)
    a = p.parse_args()
    print(json.dumps(evaluate(a.model_path)))
