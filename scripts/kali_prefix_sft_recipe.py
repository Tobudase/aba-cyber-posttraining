"""Bounded TRAIN-only critical-prefix loss intervention; no decoding changes."""
import hashlib
import json
import math
import random

from kali_sft_recipe import train_fixed_sft, validate_recipe


def critical_prefix_loss(logits, labels, prompt_tokens, weight, offset, token_id):
    import torch
    import torch.nn.functional as F

    if weight not in (1, 8) or offset != 1 or type(token_id) is not int:
        raise ValueError("Only the predeclared closing-prefix intervention is supported")
    if logits.ndim != 3 or labels.ndim != 2 or logits.shape[:2] != labels.shape or labels.shape[0] != 1:
        raise ValueError("One complete unpadded example required")
    if not 0 < prompt_tokens < labels.shape[1] - offset:
        raise ValueError("Critical target position is missing")
    if not torch.all(labels[:, :prompt_tokens] == -100) or torch.any(labels[:, prompt_tokens:] < 0):
        raise ValueError("Exact completion mask required")
    if int(labels[0, prompt_tokens + offset]) != token_id:
        raise ValueError("Critical target token differs from frozen structural close")
    shifted = labels[:, 1:]
    losses = F.cross_entropy(logits[:, :-1].float().reshape(-1, logits.shape[-1]), shifted.reshape(-1), reduction="none", ignore_index=-100).reshape_as(shifted)
    weights = (shifted != -100).to(losses.dtype)
    weights[:, prompt_tokens + offset - 1] = weight
    return (losses * weights).sum() / weights.sum()


def train_prefix_sft(model, rows, config, device, progress=None, *, prefix_weight, critical_offset, critical_token_id):
    import torch

    c = validate_recipe(config, rows)
    if prefix_weight not in (1, 8) or critical_offset != 1 or critical_token_id != 151668:
        raise ValueError("Unexpected critical-prefix intervention")
    for row in rows:
        if row["input_ids"][row["prompt_tokens"] + critical_offset] != critical_token_id:
            raise ValueError("Frozen TRAIN target does not contain the critical closing token")
    if prefix_weight == 1:
        receipt = train_fixed_sft(model, rows, config, device, progress)
        receipt.update(critical_prefix_weight=1, critical_prefix_offset=critical_offset, critical_prefix_token_id=critical_token_id, objective="original_HF_uniform_completion_cross_entropy")
        return receipt
    model.train()
    params = {name: value for name, value in model.named_parameters() if value.requires_grad}
    if not params or any("lora_" not in name for name in params):
        raise ValueError("Only LoRA may be updated")
    before = {name: p.detach().cpu().clone() for name, p in params.items()}
    optimizer = torch.optim.AdamW(params.values(), lr=c["learning_rate"], weight_decay=c["weight_decay"], betas=tuple(c["betas"]), eps=c["eps"])
    trace, order = [], []
    for epoch in range(c["epochs"]):
        permutation = list(range(len(rows)))
        random.Random(c["seed"] + epoch).shuffle(permutation)
        for i in permutation:
            row = rows[i]
            ids = torch.tensor([row["input_ids"]], device=device)
            labels = torch.tensor([row["labels"]], device=device)
            optimizer.zero_grad(set_to_none=True)
            output = model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False)
            loss = critical_prefix_loss(output.logits, labels, row["prompt_tokens"], prefix_weight, critical_offset, critical_token_id)
            if not math.isfinite(float(loss.detach())):
                raise ValueError("Nonfinite loss")
            loss.backward()
            grads = [p.grad for p in params.values() if p.grad is not None]
            if not grads:
                raise ValueError("Missing LoRA gradients")
            gn = float(torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(g.detach().float()) for g in grads])))
            if not math.isfinite(gn):
                raise ValueError("Nonfinite gradient norm")
            if c["max_grad_norm"] is not None:
                torch.nn.utils.clip_grad_norm_(params.values(), c["max_grad_norm"], error_if_nonfinite=True)
            optimizer.step()
            step = {"step": len(trace) + 1, "epoch": epoch + 1, "loss": float(loss.detach()), "gradient_norm_before_clip": gn, "supervised_tokens": len(row["input_ids"]) - row["prompt_tokens"]}
            trace.append(step)
            order.append(row["id"])
            if progress:
                progress(step)
    changed = sum(not torch.equal(before[name], p.detach().cpu()) for name, p in params.items())
    if not changed or len(trace) != c["max_optimizer_steps"]:
        raise ValueError("Unexpected update count or no parameter changes")
    return {"effective_optimizer_recipe": c, "optimizer_steps": len(trace), "trainable_parameters": sum(p.numel() for p in params.values()), "changed_tensors": changed, "trace": trace, "epoch_order_sha256": hashlib.sha256(json.dumps(order).encode()).hexdigest(), "TRAIN_presentations": len(order), "supervised_token_presentations": sum(x["supervised_tokens"] for x in trace), "all_gradient_norms_finite": True, "nonzero_gradient_steps": sum(x["gradient_norm_before_clip"] > 0 for x in trace), "DEV_or_validation_gradient_rows": 0, "critical_prefix_weight": prefix_weight, "critical_prefix_offset": critical_offset, "critical_prefix_token_id": critical_token_id, "objective": "completion_cross_entropy_critical_position_reweighted_and_normalized"}
