#!/usr/bin/env python3
"""Check causal alignment, normalization and masks against an independent formula."""
import json
import math

import torch
import torch.nn.functional as F
from kali_prefix_sft_recipe import critical_prefix_loss


def main():
    logits = (torch.arange(42, dtype=torch.float32).reshape(1, 7, 6).sin() * 2).requires_grad_()
    labels = torch.tensor([[-100, -100, -100, 1, 2, 3, 4]])
    ordinary = F.cross_entropy(logits[:, :-1].float().reshape(-1, 6), labels[:, 1:].reshape(-1), ignore_index=-100)
    uniform = critical_prefix_loss(logits, labels, 3, 1, 1, 2)
    assert torch.allclose(ordinary, uniform, atol=1e-7)
    weighted = critical_prefix_loss(logits, labels, 3, 8, 1, 2)
    # Label positions3..6 are predicted by logit positions2..5. Position4 gets weight8.
    values = []
    for label_position in range(3, 7):
        xs = logits[0, label_position - 1].detach().tolist()
        target = int(labels[0, label_position])
        values.append(math.log(sum(math.exp(x) for x in xs)) - xs[target])
    expected = (values[0] + 8 * values[1] + values[2] + values[3]) / 11
    assert abs(float(weighted.detach()) - expected) < 1e-6
    weighted.backward()
    assert torch.all(logits.grad[:, :2] == 0) and torch.all(logits.grad[:, 6] == 0)
    assert torch.isfinite(logits.grad).all() and float(logits.grad[:, 3].norm()) > 0
    rejected = 0
    for weight, offset, target in [(0, 1, 2), (2, 1, 2), (float("nan"), 1, 2), (8, 0, 2), (8, 1, 3)]:
        try:
            critical_prefix_loss(logits, labels, 3, weight, offset, target)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError("Invalid intervention accepted")
    assert rejected == 5
    print(json.dumps({"status": "PASS_CRITICAL_PREFIX_CAUSAL_LOSS", "uniform_matches_HF_CE": True, "weighted_matches_independent_scalar_formula": True, "masked_prompt_gradient_zero": True, "invalid_inputs_rejected": rejected, "model_generations": 0, "GPU_allocations": 0}))


if __name__ == "__main__":
    main()
