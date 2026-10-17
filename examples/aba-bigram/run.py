#!/usr/bin/env python3
"""Adapt the tiny eight-token bigram model to train.jsonl by plain SGD.

Model: an 8x8 logit matrix weights[context][next_token], read from
DATA_DIR/base_model.json (format "synthetic-bigram-v1", vocab_size 8).
Loss: next-token cross entropy with softmax over the selected context row.
Update: per-example SGD, only the relevant context row is touched.

Reads DATA_DIR and OUTPUT_DIR from the environment (argv fallbacks are
accepted for local runs). Trains on train.jsonl only; it never reads dev
data or the judge evaluator.

Outputs under OUTPUT_DIR:
  final_model/model.json   adapted weights, same schema, positive steps
  train_metrics.json       seed, learning_rate, epochs, steps, train NLLs
  README.md                brief execution notes
  run.py                   byte-for-byte copy of this executed source

Python 3 standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import sys

SEED = 42
LEARNING_RATE = 0.1
EPOCHS = 32
VOCAB_SIZE = 8
FORMAT_NAME = "synthetic-bigram-v1"

# Optional live metrics logging (framework-provided module beside the source).
# run.py works identically without it, so the import is guarded.
aibuildai = None
try:
    import aibuildai as _aibuildai

    _aibuildai.init()
    aibuildai = _aibuildai
except Exception:
    aibuildai = None


def _log(metrics: dict, step: int) -> None:
    if aibuildai is not None:
        try:
            aibuildai.log(metrics, step=step)
        except Exception:
            pass


def _finish() -> None:
    if aibuildai is not None:
        try:
            aibuildai.finish()
        except Exception:
            pass


def resolve_dirs(argv: list[str]) -> tuple[str, str]:
    parser = argparse.ArgumentParser(description="Adapt the bigram model by SGD.")
    parser.add_argument("--data-dir", default=None, help="Directory holding base_model.json and train.jsonl.")
    parser.add_argument("--output-dir", default=None, help="Directory to write results into.")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    output_dir = args.output_dir or os.environ.get("OUTPUT_DIR")
    if not data_dir or not output_dir:
        raise SystemExit("DATA_DIR (env or --data-dir) and OUTPUT_DIR (env or --output-dir) are required.")
    return data_dir, output_dir


def load_model(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        model = json.load(handle)
    if model.get("format") != FORMAT_NAME:
        raise SystemExit(f"unexpected format: {model.get('format')!r}")
    if model.get("vocab_size") != VOCAB_SIZE:
        raise SystemExit("unexpected vocab_size: %r" % (model.get("vocab_size"),))
    weights = model.get("weights")
    if not isinstance(weights, list) or len(weights) != VOCAB_SIZE:
        raise SystemExit("weights is not an 8x8 matrix")
    for row in weights:
        if not isinstance(row, list) or len(row) != VOCAB_SIZE:
            raise SystemExit("weights is not an 8x8 matrix")
        for value in row:
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SystemExit("non-finite weight in base model")
    steps = model.get("optimizer_steps")
    if not isinstance(steps, int) or steps < 0:
        raise SystemExit("optimizer_steps must be a non-negative int")
    return model


def load_examples(path: str) -> list[tuple[int, int]]:
    examples: list[tuple[int, int]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            context = obj["context"]
            target = obj["target"]
            if not isinstance(context, int) or not 0 <= context < VOCAB_SIZE:
                raise SystemExit(f"line {line_number}: bad context {context!r}")
            if not isinstance(target, int) or not 0 <= target < VOCAB_SIZE:
                raise SystemExit(f"line {line_number}: bad target {target!r}")
            examples.append((context, target))
    if not examples:
        raise SystemExit("train.jsonl is empty")
    return examples


def row_loss_and_grads(row: list[float], target: int) -> tuple[float, list[float]]:
    """Stable cross-entropy loss and gradient p_j - 1[j==target] for one row."""
    max_logit = max(row)
    logsum = max_logit + math.log(sum(math.exp(x - max_logit) for x in row))
    loss = logsum - row[target]
    probs = [math.exp(x - logsum) for x in row]
    grads = [probs[j] - (1.0 if j == target else 0.0) for j in range(len(row))]
    return loss, grads


def mean_train_nll(weights: list[list[float]], examples: list[tuple[int, int]]) -> float:
    total = 0.0
    for context, target in examples:
        loss, _ = row_loss_and_grads(weights[context], target)
        total += loss
    return total / len(examples)


def main() -> None:
    data_dir, output_dir = resolve_dirs(sys.argv[1:])
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "final_model"), exist_ok=True)

    base = load_model(os.path.join(data_dir, "base_model.json"))
    examples = load_examples(os.path.join(data_dir, "train.jsonl"))
    n_examples = len(examples)

    # Deep copy into floats; keep the saved step count as the starting point.
    weights = [[float(x) for x in row] for row in base["weights"]]
    optimizer_steps = int(base["optimizer_steps"])

    initial_train_nll = mean_train_nll(weights, examples)
    print(f"examples={n_examples} optimizer_steps_start={optimizer_steps} "
          f"initial_train_nll={initial_train_nll:.6f}")
    _log({"train_nll": initial_train_nll, "loss": initial_train_nll}, step=0)

    rng = random.Random(SEED)
    step_index = 0
    for epoch in range(1, EPOCHS + 1):
        order = list(range(n_examples))
        rng.shuffle(order)
        epoch_loss = 0.0
        for idx in order:
            context, target = examples[idx]
            loss, grads = row_loss_and_grads(weights[context], target)
            row = weights[context]
            for j in range(VOCAB_SIZE):
                row[j] -= LEARNING_RATE * grads[j]
            epoch_loss += loss
            optimizer_steps += 1
            step_index += 1
            _log({"train_loss": loss, "epoch": float(epoch),
                  "running_epoch_nll": epoch_loss / len(order)}, step=step_index)
        print(f"epoch={epoch:02d} mean_loss={epoch_loss / n_examples:.6f} "
              f"optimizer_steps={optimizer_steps}")

    final_train_nll = mean_train_nll(weights, examples)
    print(f"final_train_nll={final_train_nll:.6f} "
          f"(initial {initial_train_nll:.6f}, steps {optimizer_steps})")
    _log({"train_nll": final_train_nll, "loss": final_train_nll}, step=step_index + 1)
    _finish()

    # Schema and sanity self-checks before writing output.
    assert final_train_nll < initial_train_nll, "training NLL did not decrease"
    for row in weights:
        for value in row:
            assert math.isfinite(value), "non-finite weight after training"
    assert isinstance(optimizer_steps, int) and optimizer_steps > 0

    # Argmax agreement with the most frequent training target per context row.
    counts: list[dict[int, int]] = [{} for _ in range(VOCAB_SIZE)]
    for context, target in examples:
        counts[context][target] = counts[context].get(target, 0) + 1
    argmax_ok = True
    for context in range(VOCAB_SIZE):
        if counts[context]:
            most_frequent = max(counts[context], key=lambda t: (counts[context][t], -t))
            if weights[context].index(max(weights[context])) != most_frequent:
                argmax_ok = False
                print(f"note: context {context} argmax disagrees with most frequent target")
    print(f"argmax_matches_most_frequent_target={argmax_ok}")

    model_out = {
        "format": FORMAT_NAME,
        "vocab_size": VOCAB_SIZE,
        "weights": weights,
        "optimizer_steps": optimizer_steps,
    }
    metrics_out = {
        "seed": SEED,
        "learning_rate": LEARNING_RATE,
        "epochs": EPOCHS,
        "steps": optimizer_steps,
        "initial_train_nll": initial_train_nll,
        "final_train_nll": final_train_nll,
    }
    readme = f"""# Synthetic bigram adaptation

`run.py` adapts the supplied eight-token bigram model to `train.jsonl` using
actual gradient descent on next-token cross entropy, starting from the exact
base weights in `base_model.json`.

- Seed: {SEED} (single `random.Random({SEED})` instance shuffles the 256
  examples before each epoch)
- Learning rate: {LEARNING_RATE} (fixed)
- Epochs: {EPOCHS} (cap 64)
- Update rule: per-example SGD; for context row c and target t the gradient is
  g_j = p_j - 1[j == t] with p = softmax(weights[c]); only row c is updated,
  weights[c][j] -= {LEARNING_RATE} * g_j
- Optimizer steps: {optimizer_steps} = {n_examples} examples x {EPOCHS} epochs

Measured training NLL (mean over train.jsonl):
- initial: {initial_train_nll:.6f}
- final: {final_train_nll:.6f}

Files in this directory:
- `final_model/model.json` - adapted model, same schema as the base model
  (format `synthetic-bigram-v1`, vocab_size 8, 8x8 finite weights, positive
  `optimizer_steps`)
- `train_metrics.json` - seed, learning_rate, epochs, steps, and the two
  measured training NLLs
- `run.py` - byte-for-byte copy of the exact executed source
- `README.md` - this file

Run it with:

    DATA_DIR=<dir with base_model.json, train.jsonl> \\
    OUTPUT_DIR=<dir to write results> python run.py

Python 3 standard library only; no ML packages, no network access, no
training on any data other than train.jsonl.
"""

    with open(os.path.join(output_dir, "final_model", "model.json"), "w", encoding="utf-8") as handle:
        json.dump(model_out, handle, indent=2)
        handle.write("\n")
    with open(os.path.join(output_dir, "train_metrics.json"), "w", encoding="utf-8") as handle:
        json.dump(metrics_out, handle, indent=2)
        handle.write("\n")
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(readme)

    # Copy the exact executed source byte-for-byte into the output directory.
    src = os.path.abspath(__file__)
    dst = os.path.join(output_dir, "run.py")
    shutil.copyfile(src, dst)
    with open(src, "rb") as a, open(dst, "rb") as b:
        assert a.read() == b.read(), "OUTPUT_DIR/run.py is not a byte-for-byte copy"

    for rel in ("final_model/model.json", "train_metrics.json", "README.md", "run.py"):
        path = os.path.join(output_dir, rel)
        assert os.path.isfile(path) and os.path.getsize(path) > 0, f"missing {path}"
        print(f"wrote {path}")
    print("OK")


if __name__ == "__main__":
    main()
