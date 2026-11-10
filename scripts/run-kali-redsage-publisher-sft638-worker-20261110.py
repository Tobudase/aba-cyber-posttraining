#!/usr/bin/env python3
"""Finite RedSage BF16 LoRA SFT on publisher-verified KaliBench TRAIN only."""

import base64
import concurrent.futures
import gzip
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def main():
    started = time.monotonic()
    protocol = json.loads(Path("/input/protocol.json").read_text())
    assert protocol["status"] == "FROZEN_REDSAGE_PUBLISHER_SFT638_BEFORE_TRAINING"
    assert protocol["official_TEST_rows"] == 0
    assert sha("/input/worker.py") == protocol["worker_sha256"]
    assert sha("/input/kali_publisher_sft_recipe.py") == protocol["recipe_sha256"]
    raw = gzip.decompress(Path("/input/payload.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == protocol["payload_sha256"]
    payload = json.loads(raw)
    rows = payload["train_rows"]
    holdout = payload["holdout"]
    anchors = payload["anchors"]
    assert len(rows) == len({r["id"] for r in rows}) == 638
    assert len(holdout) == len({r["id"] for r in holdout}) == 64
    assert len(anchors) == len({r["id"] for r in anchors}) == 4
    assert not {r["id"] for r in rows} & {r["id"] for r in holdout + anchors}
    assert all(r["split"] == "train" and r["training_eligible"] is True and
               r["official_test"] is False for r in rows)
    assert all(set(r) == {"id", "native_messages"} for r in holdout)

    model_dir = Path("/scratch/model")
    model_dir.mkdir()

    def stage(item):
        name, expected = item
        assert Path(name).name == name
        src, dst = Path("/cache/model") / name, model_dir / name
        h = hashlib.sha256()
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            for block in iter(lambda: incoming.read(8 * 1024**2), b""):
                h.update(block)
                outgoing.write(block)
        assert h.hexdigest() == expected
        print("STAGED " + name, flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(stage, protocol["checkpoint_files"].items()))
    assert sha("/cache/runtime-deps.tar") == protocol["runtime_archive_sha256"]
    deps = Path("/scratch/deps")
    deps.mkdir()
    with tarfile.open("/cache/runtime-deps.tar") as archive:
        assert all(member.isfile() and (deps / member.name).resolve().is_relative_to(deps.resolve())
                   for member in archive.getmembers())
        archive.extractall(deps, filter="data")
    sys.path[:0] = [str(deps), "/input"]

    import torch
    from importlib.metadata import version
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
    from safetensors.torch import load_file
    from kali_publisher_sft_recipe import validate_recipe, train_fixed_sft

    assert {name: version(name) for name in protocol["expected_packages"]} == protocol["expected_packages"]
    assert torch.cuda.is_available()
    gpu = torch.cuda.get_device_name(0)
    assert gpu in protocol["allowed_GPU_models"]
    torch.set_num_threads(2)
    tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True,
                                         trust_remote_code=False, fix_mistral_regex=False)
    tok.padding_side = "left"
    tok.pad_token = tok.eos_token
    assert tok.eos_token_id == 151645
    validate_recipe(protocol["optimizer"], rows)
    torch.manual_seed(protocol["initialization_seed"])
    base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                device_map={"": 0}, torch_dtype=torch.bfloat16, attn_implementation="sdpa")
    base.requires_grad_(False)
    base.enable_input_require_grads()
    model = get_peft_model(base, LoraConfig(**protocol["LoRA_config"]))
    model.eval()

    def infer(batch_rows, arm, anchor=False):
        out = []
        for offset in range(0, len(batch_rows), protocol["batch_size"]):
            batch = batch_rows[offset:offset + protocol["batch_size"]]
            prompts = [tok.apply_chat_template(r["native_messages"], tokenize=False,
                       add_generation_prompt=True) for r in batch]
            assert all(p.endswith("<think>") for p in prompts)
            inputs = tok(prompts, padding=True, add_special_tokens=False,
                         return_tensors="pt").to("cuda")
            torch.manual_seed(protocol["inference_seed"])
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=protocol["max_new_tokens"],
                    do_sample=False, use_cache=True, pad_token_id=tok.eos_token_id,
                    eos_token_id=tok.eos_token_id, temperature=None, top_p=None, top_k=None)
            for row, ids in zip(batch, generated[:, inputs["input_ids"].shape[1]:].tolist()):
                truncated = tok.eos_token_id not in ids
                effective = ids if truncated else ids[:ids.index(tok.eos_token_id)]
                response = tok.decode(effective, skip_special_tokens=False,
                                      clean_up_tokenization_spaces=False)
                if anchor:
                    assert arm == "base"
                    assert hashlib.sha256(response.encode()).hexdigest() == row["expected_sha256"]["base"]
                else:
                    out.append({"id": row["id"], "arm": arm, "response": response,
                                "truncated": truncated, "generated_tokens": len(effective)})
            print("INFER " + arm + " " + str(offset + len(batch)) + "/" + str(len(batch_rows)), flush=True)
        return out

    infer(anchors, "base", anchor=True)
    print("BASE_ANCHORS_PASS", flush=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.config.use_cache = False

    def progress(step):
        if step["step"] == 1 or step["step"] % 32 == 0:
            print("TRAIN " + json.dumps({k: step[k] for k in (
                "step", "loss", "gradient_norm_before_clip")}), flush=True)

    receipt = train_fixed_sft(model, rows, protocol["optimizer"], "cuda", progress)
    assert receipt["optimizer_steps"] == 638 and receipt["nonzero_gradient_steps"] == 638
    outdir = Path("/cache/kali-redsage-publisher-sft638-20261110")
    outdir.mkdir(exist_ok=False)
    model.eval()
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    model.save_pretrained(outdir / "adapter")
    probe = torch.tensor([rows[0]["input_ids"]], device="cuda")
    with torch.inference_mode():
        before = model(input_ids=probe, use_cache=False).logits[:, -1, :].float().cpu()
    state = load_file(str(outdir / "adapter/adapter_model.safetensors"))
    with torch.no_grad():
        for value in model.parameters():
            if value.requires_grad:
                value.zero_()
    set_peft_model_state_dict(model, state, adapter_name="default")
    with torch.inference_mode():
        after = model(input_ids=probe, use_cache=False).logits[:, -1, :].float().cpu()
    delta = float((before - after).abs().max())
    assert delta <= 1e-4
    predictions = infer(holdout, "publisher_sft638")
    packed = base64.b64encode(gzip.compress(json.dumps(predictions, ensure_ascii=False).encode())).decode()
    print("PUBLISHER_SFT638_PREDICTIONS=" + packed, flush=True)
    receipt.update({"status": "COMPLETE_PUBLISHER_SFT638",
                    "adapter_sha256": sha(outdir / "adapter/adapter_model.safetensors"),
                    "adapter_reload_max_logit_delta": delta,
                    "GPU": gpu, "GPU_count": 1,
                    "holdout_predictions": len(predictions),
                    "holdout_truncations": sum(r["truncated"] for r in predictions),
                    "official_TEST_rows": 0,
                    "worker_sha256": sha("/input/worker.py"),
                    "protocol_sha256": sha("/input/protocol.json"),
                    "wall_seconds": round(time.monotonic() - started, 2),
                    "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated()})
    (outdir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    public_receipt = {k: receipt[k] for k in (
        "status", "adapter_sha256", "adapter_reload_max_logit_delta", "GPU", "GPU_count",
        "holdout_predictions", "holdout_truncations", "official_TEST_rows",
        "worker_sha256", "protocol_sha256", "wall_seconds", "peak_cuda_allocated_bytes",
        "optimizer_steps", "nonzero_gradient_steps", "supervised_token_presentations")}
    print("PUBLISHER_SFT638_RECEIPT=" + json.dumps(public_receipt), flush=True)


if __name__ == "__main__":
    main()
